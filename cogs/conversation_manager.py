# cogs/conversation_manager.py

import discord
from discord.ext import commands
import json
import os
import re

from .llm_utils import call_local_llm

# In-memory storage for private DM sessions
private_sessions = {}

# Define paths relative to the script location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FOLDER = os.path.join(BASE_DIR, "dm_sessions")  # Folder to store session files
IMAGE_FOLDER = os.path.join(BASE_DIR, "images")         # Folder to store image files

def load_prompt(file_path: str):
    try:
        prompt_path = os.path.join(BASE_DIR, file_path)
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[ERROR] '{file_path}' not found.")
        return ""

def ensure_dm_folder():
    if not os.path.exists(SESSION_FOLDER):
        os.makedirs(SESSION_FOLDER, exist_ok=True)

def ensure_image_folder():
    if not os.path.exists(IMAGE_FOLDER):
        os.makedirs(IMAGE_FOLDER, exist_ok=True)
        print(f"[INFO] Created '{IMAGE_FOLDER}/' directory for storing images.")

def session_file_path(user_id: int) -> str:
    return os.path.join(SESSION_FOLDER, f"session_{user_id}.json")

def load_all_sessions_on_start():
    """
    Load all sessions from 'dm_sessions' folder into private_sessions.
    This is called once at bot startup to ensure continuity.
    """
    ensure_dm_folder()
    for fname in os.listdir(SESSION_FOLDER):
        if not fname.startswith("session_") or not fname.endswith(".json"):
            continue
        fullpath = os.path.join(SESSION_FOLDER, fname)
        try:
            with open(fullpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            user_id_str = fname.replace("session_", "").replace(".json", "")
            user_id = int(user_id_str)
            private_sessions[user_id] = data
            print(f"[DEBUG] Loaded DM session from {fname}")
        except Exception as e:
            print(f"[ERROR] Loading session file {fname}: {e}")

def save_session(user_id: int):
    """
    Save the given user's session data to a .json file.
    """
    ensure_dm_folder()
    data = private_sessions[user_id]
    path = session_file_path(user_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Could not save session for user {user_id}: {e}")

class ConversationManagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.system_prompt_main = load_prompt("system_prompt.txt")
        self.system_prompt_dm = load_prompt("system_prompt2.txt")
        self.system_prompt_whisper = load_prompt("system_prompt_whisper.txt")
        
        # Ensure the images folder exists
        ensure_image_folder()

        # On cog load, load all previous sessions from disk
        load_all_sessions_on_start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        # Check if it's a command
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return  # Let commands handle it

        # If in DM
        if isinstance(message.channel, discord.DMChannel):
            user_id = message.author.id
            # If user is in private_sessions, handle. Otherwise, do nothing.
            if user_id in private_sessions:
                await self.handle_private_dm(message)
            return

        # If in a guild channel, only respond in "bot-chat"
        if not message.guild:
            return
        if message.channel.name != "bot-chat":
            return

        # Normal message in "bot-chat" => call LLM with system_prompt_main
        user_content = message.content.strip()
        if not user_content:
            return  # empty message

        messages = [
            {"role": "system", "content": self.system_prompt_main},
            {"role": "user", "content": user_content}
        ]
        response = await call_local_llm(messages)
        if not isinstance(response, dict) or "message" not in response:
            await message.channel.send("[ERROR] LLM responded invalid JSON.")
            return

        reply_text = response["message"].strip() or "Done"
        await message.channel.send(reply_text)

        # Handle tool calls if any
        tool_calls = response.get("tool_calls", [])
        if tool_calls:
            server_cog = self.bot.get_cog("ServerManagerCog")
            if server_cog:
                results = await server_cog.manager.handle_tool_calls(tool_calls)
                for r in results:
                    await message.channel.send(f"[Tool result]\n{r}")

    @commands.command(name="talkto")
    async def talkto(self, ctx: commands.Context, member_id: int):
        """
        Initiates a private DM conversation with user <member_id>.
        If a session already exists, it continues automatically.
        """
        guild = ctx.guild
        if not guild:
            await ctx.send("[ERROR] Not in a valid guild context.")
            return

        member = guild.get_member(member_id)
        if not member:
            await ctx.send("[ERROR] Member not found.")
            return

        dm_channel = await member.create_dm()
        user_id = member.id

        # If there's an existing session loaded, great; otherwise create one
        if user_id not in private_sessions:
            private_sessions[user_id] = {
                "user_name": member.name,
                "messages": [],
                "voice_mode_on": False
            }
            save_session(user_id)
            print(f"[DEBUG] Created a new DM session for user {user_id}")

        await dm_channel.send(f"Hello {member.name}! We can talk privately anytime.")
        await ctx.send(f"Initiated private conversation with {member.name}.")

    async def handle_private_dm(self, message: discord.Message):
        """
        Handle user DM in a persistent session.
        """
        user_id = message.author.id
        session_data = private_sessions[user_id]
        user_content = message.content.strip()
        if not user_content:
            await message.channel.send("Ok, got it.")
            return

        dynamic_dm_prompt = (
            f"{self.system_prompt_dm}\n"
            f"You are currently talking privately to user: {session_data['user_name']}\n"
            "They may say anything. You can only respond with JSON: { \"message\": \"...\" }"
        )

        conv_history = session_data["messages"]
        full_messages = [{"role": "system", "content": dynamic_dm_prompt}] + conv_history
        full_messages.append({"role": "user", "content": user_content})

        response = await call_local_llm(
            messages=full_messages,
            model_override="llm-model"
        )
        if not isinstance(response, dict) or "message" not in response:
            await message.channel.send("[ERROR] Invalid or no 'message' in LLM response.")
            return

        assistant_msg = response["message"].strip()

        # Append to conversation
        conv_history.append({"role": "user", "content": user_content})
        conv_history.append({"role": "assistant", "content": assistant_msg})

        # Save updated session
        save_session(user_id)

        await message.channel.send(assistant_msg)

    #######################################
    #          NEW: !whisper command
    #######################################
    @commands.command(name="whisper")
    async def whisper_command(self, ctx: commands.Context, *, content: str):
        """
        Usage: !whisper [your prompt] id:<user_id>
        Example: !whisper what's the weather today? id:9201492914019

        This uses a special system prompt (system_prompt_whisper.txt) and
        the same model override used for DM conversations. The resulting
        output is sent to the designated user's DM, and the conversation is
        stored in that user's private session context.
        """
        # Try to find "id:<user_id>" in content
        pattern = r"id\s*:\s*(\d+)"
        match = re.search(pattern, content)
        if not match:
            await ctx.send("[ERROR] You must specify 'id:<user_id>' somewhere in the whisper content.")
            return

        # Extract user ID from the matched group
        target_user_id_str = match.group(1)
        try:
            target_user_id = int(target_user_id_str)
        except ValueError:
            await ctx.send("[ERROR] Invalid user ID format.")
            return

        # Extract the prompt (removing "id:XXXX")
        # We'll just remove that part from 'content'
        prompt_text = re.sub(pattern, "", content).strip()
        if not prompt_text:
            await ctx.send("[ERROR] Please provide a prompt (text to whisper).")
            return

        # Attempt to get the guild from either context or fallback
        # If in DMs, we assume a default guild (or a known static server).
        # If in a server, we can use ctx.guild.
        guild = None
        if ctx.guild:
            guild = ctx.guild
        else:
            # Fallback to a known server ID if you have one
            # Example: DEFAULT_GUILD_ID = 745769392767500322
            fallback_guild_id = 745769392767500322  # Replace with your actual guild ID
            guild = self.bot.get_guild(fallback_guild_id)

        if not guild:
            await ctx.send("[ERROR] Could not locate a valid guild.")
            return

        member = guild.get_member(target_user_id)
        if not member:
            await ctx.send("[ERROR] Target user not found in the guild.")
            return

        # Create or load their session
        if target_user_id not in private_sessions:
            private_sessions[target_user_id] = {
                "user_name": member.name,
                "messages": [],
                "voice_mode_on": False
            }
            save_session(target_user_id)
            print(f"[DEBUG] Created a new DM session for user {target_user_id}")

        session_data = private_sessions[target_user_id]
        dm_channel = await member.create_dm()

        # Build the LLM messages with system_prompt_whisper
        dynamic_whisper_prompt = (
            f"{self.system_prompt_whisper}\n"
            f"This is a one-time whisper from '{ctx.author.name}' to '{session_data['user_name']}'.\n"
            "You must respond with JSON: { \"message\": \"...\" }, no additional keys.\n"
        )
        conv_history = session_data["messages"]

        # We'll treat the 'whisper' as a user message in the target user's conversation
        # so it shows up in their DM context
        full_messages = [{"role": "system", "content": dynamic_whisper_prompt}] + conv_history
        full_messages.append({
            "role": "user",
            "content": prompt_text
        })

        # Call the LLM with the same model override as DM conversations
        response = await call_local_llm(
            messages=full_messages,
            model_override="l3.2-rogue-creative-instruct-uncensored-abliterated-7b"
        )
        if not isinstance(response, dict) or "message" not in response:
            await ctx.send("[ERROR] Invalid or no 'message' in LLM whisper response.")
            return

        whisper_reply = response["message"].strip()

        # Store this conversation in the target user's session
        conv_history.append({"role": "user", "content": f"Whisper from {ctx.author.name}: {prompt_text}"})
        conv_history.append({"role": "assistant", "content": whisper_reply})
        save_session(target_user_id)

        # DM the resulting output to the target user
        try:
            await dm_channel.send(whisper_reply)
            await ctx.send(f"Whisper sent to {member.name}.")
        except discord.Forbidden:
            await ctx.send(f"[ERROR] Cannot send DM to {member.name}. They might have DMs disabled.")
        except Exception as e:
            await ctx.send(f"[ERROR] Failed to send whisper: {e}")

    #######################################
    #          NEW: !photo command
    #######################################
    @commands.command(name="photo")
    async def photo_command(self, ctx: commands.Context, *, content: str):
        """
        Usage: !photo <filename> id:<user_id>
        Example: !photo img9124.png id:406399487641255938

        This command sends the specified image to the designated user's DM.
        The image must be located in the 'images/' directory.
        The action is stored in the user's private session for continuity.
        """
        # Regex to extract filename and id
        pattern = r"^(?P<filename>[^\s]+)\s+id\s*:\s*(?P<user_id>\d+)$"
        match = re.match(pattern, content.strip())
        if not match:
            await ctx.send("[ERROR] Invalid command format. Use: !photo <filename> id:<user_id>")
            return

        filename = match.group("filename")
        user_id_str = match.group("user_id")
        try:
            target_user_id = int(user_id_str)
        except ValueError:
            await ctx.send("[ERROR] Invalid user ID format.")
            return

        # Construct the full path to the image
        image_path = os.path.join(IMAGE_FOLDER, filename)

        # Check if the file exists
        if not os.path.isfile(image_path):
            await ctx.send(f"[ERROR] File '{filename}' not found in '{IMAGE_FOLDER}/' directory.")
            return

        # Attempt to get the guild from context or fallback
        guild = None
        if ctx.guild:
            guild = ctx.guild
        else:
            # Fallback to a known guild ID if you have one
            fallback_guild_id = 745769392767500322  # Replace with your actual guild ID
            guild = self.bot.get_guild(fallback_guild_id)

        if not guild:
            await ctx.send("[ERROR] Could not locate a valid guild.")
            return

        member = guild.get_member(target_user_id)
        if not member:
            await ctx.send("[ERROR] Target user not found in the guild.")
            return

        # Create or load their session
        if target_user_id not in private_sessions:
            private_sessions[target_user_id] = {
                "user_name": member.name,
                "messages": [],
                "voice_mode_on": False
            }
            save_session(target_user_id)
            print(f"[DEBUG] Created a new DM session for user {target_user_id}")

        session_data = private_sessions[target_user_id]
        dm_channel = await member.create_dm()

        # Prepare the message to send
        try:
            file = discord.File(image_path)
        except Exception as e:
            await ctx.send(f"[ERROR] Failed to load the image file: {e}")
            return

        # Send the image to the user's DM
        try:
            await dm_channel.send(file=file)
            await ctx.send(f"Image '{filename}' sent to {member.name}.")
        except discord.Forbidden:
            await ctx.send(f"[ERROR] Cannot send DM to {member.name}. They might have DMs disabled.")
            return
        except Exception as e:
            await ctx.send(f"[ERROR] Failed to send image: {e}")
            return

        # Append to conversation context
        conv_history = session_data["messages"]
        conv_history.append({"role": "user", "content": f"Sent photo '{filename}' to {member.name}."})
        conv_history.append({"role": "assistant", "content": f"Photo '{filename}' has been sent to you."})
        save_session(target_user_id)

async def setup(bot: commands.Bot):
    await bot.add_cog(ConversationManagerCog(bot))
