import discord
from discord.ext import commands
import os
import asyncio
import json
import uuid
import requests
from dotenv import load_dotenv
from TTS.api import TTS

# ======================
# Load Environment Variables
# ======================
load_dotenv()

TOKEN =  ""
if not TOKEN:
    raise ValueError("No Discord API token found!")

# Hardcode single guild ID
DEFAULT_GUILD_ID = 1234567890  # Modify as needed

# ======================
# Coqui TTS Class
# ======================
class CoquiTTS:
    def __init__(self, model_name="tts_models/en/ljspeech/tacotron2-DDC"):
        print(f"[DEBUG] Loading TTS model: {model_name}")
        try:
            self.tts = TTS(model_name=model_name)
            print("[DEBUG] TTS model loaded successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to load TTS model: {e}")

    def generate_wav(self, text: str, output_file: str):
        try:
            self.tts.tts_to_file(text=text, file_path=output_file)
            print(f"[DEBUG] Generated TTS audio: {output_file}")
        except Exception as e:
            print(f"[ERROR] TTS generation error: {e}")

tts_engine = CoquiTTS()

# ======================
# Bot Setup
# ======================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# Utility Finders
# ======================
def find_channel_by_name(guild: discord.Guild, name: str):
    """
    Search for a channel (text or voice) by exact name (case-insensitive).
    Return the channel if found, otherwise None.
    """
    if not name:
        return None

    name_lower = name.strip().lower()
    for ch in guild.channels:
        if ch.name.lower() == name_lower:
            return ch
    return None

def find_member_by_name(guild: discord.Guild, name: str):
    """
    Search for a member by exact name/nick (case-insensitive).
    Return the member if found, otherwise None.
    """
    if not name:
        return None

    name_lower = name.strip().lower()
    for m in guild.members:
        # Compare with username and nickname
        if m.name.lower() == name_lower or (m.nick and m.nick.lower() == name_lower):
            return m
    return None

# ======================
# DiscordServerManager
# ======================
class DiscordServerManager:
    def __init__(self, bot):
        self.bot = bot

    # ----------- SINGLE-ACTION TOOLS -----------
    async def change_channel_name(self, channel_id=None, channel_name=None, new_name=None):
        """
        Rename a channel. Use either channel_id or channel_name (if channel_id is invalid or not provided).
        """
        if not new_name:
            return "[ERROR] Missing required 'new_name'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        channel = None
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel is None:
                print(f"[DEBUG] channel_id={channel_id} not found. Fallback to channel_name={channel_name}.")
        if not channel and channel_name:
            channel = find_channel_by_name(guild, channel_name)

        if not channel:
            return f"[ERROR] Channel not found. channel_id={channel_id}, channel_name={channel_name}"

        try:
            old_name = channel.name
            await channel.edit(name=new_name)
            return f"Channel '{old_name}' renamed to '{new_name}'."
        except Exception as e:
            return f"[ERROR] Failed to rename channel: {e}"

    async def change_nickname(self, user_id=None, user_name=None, new_nickname=None):
        """
        Change a member's nickname. Use either user_id or user_name (if user_id is invalid or not provided).
        """
        if not new_nickname:
            return "[ERROR] Missing required 'new_nickname'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        member = None
        if user_id:
            member = guild.get_member(user_id)
            if member is None:
                print(f"[DEBUG] user_id={user_id} not found. Fallback to user_name={user_name}.")
        if not member and user_name:
            member = find_member_by_name(guild, user_name)

        if not member:
            return f"[ERROR] Member not found. user_id={user_id}, user_name={user_name}"

        try:
            old_name = member.display_name
            await member.edit(nick=new_nickname)
            return f"Nickname for '{old_name}' changed to '{new_nickname}'."
        except Exception as e:
            return f"[ERROR] Failed to change nickname: {e}"

    async def change_text_channel_topic(self, channel_id=None, channel_name=None, new_topic=None):
        """
        Change the topic of a text channel. Use either channel_id or channel_name (if channel_id is invalid or not provided).
        """
        if not new_topic:
            return "[ERROR] Missing required 'new_topic'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        channel = None
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel is None:
                print(f"[DEBUG] channel_id={channel_id} not found. Fallback to channel_name={channel_name}.")
        if not channel and channel_name:
            channel = find_channel_by_name(guild, channel_name)

        if not channel or not isinstance(channel, discord.TextChannel):
            return f"[ERROR] Text channel not found. channel_id={channel_id}, channel_name={channel_name}"

        try:
            old_topic = channel.topic
            await channel.edit(topic=new_topic)
            return f"Channel topic updated from '{old_topic}' to '{new_topic}'."
        except Exception as e:
            return f"[ERROR] Failed to change channel topic: {e}"

    async def get_guilds(self):
        """
        Return the list of guild names the bot is in.
        """
        try:
            return [g.name for g in self.bot.guilds]
        except Exception as e:
            return f"[ERROR] Failed to retrieve guilds: {e}"

    async def get_guild_members(self):
        """
        Return a list of (member_id, member_name) from the default guild.
        """
        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        try:
            return [(m.id, m.name) for m in guild.members]
        except Exception as e:
            return f"[ERROR] Failed to retrieve members: {e}"

    async def get_channels(self):
        """
        Return a list of (channel_id, channel_name) from the default guild.
        """
        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        try:
            return [(ch.id, ch.name) for ch in guild.channels]
        except Exception as e:
            return f"[ERROR] Failed to retrieve channels: {e}"

    async def create_role(self, role_name=None):
        """
        Create a new role in the default guild.
        """
        if not role_name:
            return "[ERROR] Missing required 'role_name'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        try:
            new_role = await guild.create_role(name=role_name)
            return f"Role '{role_name}' created (ID: {new_role.id})."
        except Exception as e:
            return f"[ERROR] Failed to create role: {e}"

    async def tts_speak(self, text=None):
        """
        Generate a TTS audio file using the Coqui TTS engine.
        """
        if not text:
            return "[ERROR] Missing required 'text'."

        output_path = f"{uuid.uuid4()}.wav"
        try:
            await asyncio.to_thread(tts_engine.generate_wav, text, output_path)
            return f"TTS audio generated for '{text}', saved as {output_path}."
        except Exception as e:
            return f"[ERROR] Failed to generate TTS: {e}"

    async def voicemode(self, user_id=None, user_name=None, mode=None):
        """
        Mute/Unmute/Deafen/Undeafen a user in voice channels.
        """
        if not mode:
            return "[ERROR] Missing required 'mode'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        member = None
        if user_id:
            member = guild.get_member(user_id)
            if member is None:
                print(f"[DEBUG] user_id={user_id} not found. Fallback to user_name={user_name}.")
        if not member and user_name:
            member = find_member_by_name(guild, user_name)

        if not member:
            return f"[ERROR] Member not found. user_id={user_id}, user_name={user_name}"

        try:
            m = mode.lower()
            if m == "mute":
                await member.edit(mute=True)
                return f"User '{member.display_name}' muted."
            elif m == "unmute":
                await member.edit(mute=False)
                return f"User '{member.display_name}' unmuted."
            elif m == "deafen":
                await member.edit(deafen=True)
                return f"User '{member.display_name}' deafened."
            elif m == "undeafen":
                await member.edit(deafen=False)
                return f"User '{member.display_name}' undeafened."
            else:
                return f"[ERROR] Invalid voicemode: '{mode}'. Options: mute, unmute, deafen, undeafen."
        except Exception as e:
            return f"[ERROR] Failed to change voice mode: {e}"

    async def create_text_channel(self, channel_name=None):
        """
        Create a text channel in the default guild.
        """
        if not channel_name:
            return "[ERROR] Missing required 'channel_name'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        try:
            new_ch = await guild.create_text_channel(name=channel_name)
            return f"Created text channel '{channel_name}' (ID: {new_ch.id})."
        except Exception as e:
            return f"[ERROR] Failed to create text channel: {e}"

    async def create_voice_channel(self, channel_name=None):
        """
        Create a voice channel in the default guild.
        """
        if not channel_name:
            return "[ERROR] Missing required 'channel_name'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        try:
            new_ch = await guild.create_voice_channel(name=channel_name)
            return f"Created voice channel '{channel_name}' (ID: {new_ch.id})."
        except Exception as e:
            return f"[ERROR] Failed to create voice channel: {e}"

    async def delete_channel(self, channel_id=None, channel_name=None):
        """
        Delete a channel (by ID or name) in the default guild.
        """
        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        channel = None
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel is None:
                print(f"[DEBUG] channel_id={channel_id} not found. Fallback to channel_name={channel_name}.")
        if not channel and channel_name:
            channel = find_channel_by_name(guild, channel_name)

        if not channel:
            return f"[ERROR] Channel not found. channel_id={channel_id}, channel_name={channel_name}"

        try:
            old_name = channel.name
            await channel.delete()
            return f"Deleted channel '{old_name}'."
        except Exception as e:
            return f"[ERROR] Failed to delete channel: {e}"

    async def kick_member(self, user_id=None, user_name=None, reason=None):
        """
        Kick a member from the default guild. Provide reason if needed.
        """
        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        member = None
        if user_id:
            member = guild.get_member(user_id)
            if member is None:
                print(f"[DEBUG] user_id={user_id} not found. Fallback to user_name={user_name}.")
        if not member and user_name:
            member = find_member_by_name(guild, user_name)

        if not member:
            return f"[ERROR] Member not found. user_id={user_id}, user_name={user_name}"

        try:
            await member.kick(reason=reason)
            return f"User '{member.display_name}' was kicked. Reason: {reason if reason else 'No reason provided.'}"
        except Exception as e:
            return f"[ERROR] Failed to kick member: {e}"

    # ----------- BULK-ACTION TOOLS -----------
    async def mass_change_nickname(self, new_nickname=None):
        """
        Change everyone's nickname in the guild to 'new_nickname'.
        Use with caution (requires appropriate permissions).
        """
        if not new_nickname:
            return "[ERROR] Missing required 'new_nickname'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        errors = []
        success_count = 0
        for member in guild.members:
            # Skip bot accounts or server owner if you prefer
            if member.bot:
                continue
            try:
                old_name = member.display_name
                await member.edit(nick=new_nickname)
                success_count += 1
            except Exception as e:
                errors.append(f"Failed to change {member.display_name}: {e}")

        report = (f"Changed {success_count} members' nicknames to '{new_nickname}'.\n"
                  + ("\n".join(errors) if errors else "No errors."))
        return report

    async def mass_send_message(self, text=None, times=1):
        """
        Send the same message multiple times (in the same channel).
        Use with caution to avoid spam or hitting rate limits.
        """
        if not text:
            return "[ERROR] Missing required 'text'."
        if times <= 0:
            return "[ERROR] 'times' must be greater than 0."

        # For demonstration, we only send up to 10 messages to avoid spam
        capped_times = min(times, 10)

        # This requires a context or channel object. 
        # If you're directly controlling from on_message, you might store the channel or pass it in.
        # Here we just return a string describing the action, or you can adapt it to actually send.
        try:
            # Return a message describing that we'd send them,
            # or implement an actual sending logic if you want.
            return f"Would send '{text}' {capped_times} times. (Capped at 10 to avoid spam.)"
        except Exception as e:
            return f"[ERROR] Failed to send repeated messages: {e}"

    # ======================
    # Core Single Tool Call
    # ======================
    async def handle_tool_call(self, tool_call: dict):
        """
        Handle a single tool call. Example:
          {
            "tool_name": "change_channel_name",
            "parameters": {
              "channel_id": 123456789012345678,
              "channel_name": "general",
              "new_name": "chat"
            }
          }
        """
        tool_name = tool_call.get("tool_name")
        params = tool_call.get("parameters", {})

        print(f"[DEBUG] handle_tool_call invoked with tool_name='{tool_name}' and params={params}")

        try:
            if tool_name == "change_channel_name":
                return await self.change_channel_name(
                    channel_id=params.get("channel_id"),
                    channel_name=params.get("channel_name"),
                    new_name=params.get("new_name")
                )

            elif tool_name == "change_nickname":
                return await self.change_nickname(
                    user_id=params.get("user_id"),
                    user_name=params.get("user_name"),
                    new_nickname=params.get("new_nickname")
                )

            elif tool_name == "change_text_channel_topic":
                return await self.change_text_channel_topic(
                    channel_id=params.get("channel_id"),
                    channel_name=params.get("channel_name"),
                    new_topic=params.get("new_topic")
                )

            elif tool_name == "get_guilds":
                return await self.get_guilds()

            elif tool_name == "get_guild_members":
                return await self.get_guild_members()

            elif tool_name == "get_channels":
                return await self.get_channels()

            elif tool_name == "create_role":
                return await self.create_role(role_name=params.get("role_name"))

            elif tool_name == "tts_speak":
                return await self.tts_speak(text=params.get("text"))

            elif tool_name == "voicemode":
                return await self.voicemode(
                    user_id=params.get("user_id"),
                    user_name=params.get("user_name"),
                    mode=params.get("mode")
                )

            elif tool_name == "create_text_channel":
                return await self.create_text_channel(channel_name=params.get("channel_name"))

            elif tool_name == "create_voice_channel":
                return await self.create_voice_channel(channel_name=params.get("channel_name"))

            elif tool_name == "delete_channel":
                return await self.delete_channel(
                    channel_id=params.get("channel_id"),
                    channel_name=params.get("channel_name")
                )

            elif tool_name == "kick_member":
                return await self.kick_member(
                    user_id=params.get("user_id"),
                    user_name=params.get("user_name"),
                    reason=params.get("reason")
                )

            # Newly added
            elif tool_name == "mass_change_nickname":
                return await self.mass_change_nickname(new_nickname=params.get("new_nickname"))

            elif tool_name == "mass_send_message":
                return await self.mass_send_message(
                    text=params.get("text"),
                    times=params.get("times", 1)
                )

            else:
                return f"[ERROR] Tool not recognized: '{tool_name}'."

        except KeyError as e:
            return f"[ERROR] Missing parameter: {str(e)}"
        except Exception as e:
            return f"[ERROR] Error executing tool: {str(e)}"

    # ======================
    # Handle Multiple Tool Calls
    # ======================
    async def handle_tool_calls(self, tool_calls: list):
        results = []
        for call in tool_calls:
            print(f"[DEBUG] Processing tool call: {call}")
            result = await self.handle_tool_call(call)
            results.append(result)
        return results



server_manager = DiscordServerManager(bot)

# ======================
# Updated JSON Schema
# ======================
ASSISTANT_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "The message content to be sent back to the user."
        },
        "tool_calls": {
            "type": ["array", "null"],
            "description": "An optional array of tool calls to perform multiple actions.",
            "items": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "The name of the tool to be called."
                    },
                    "parameters": {
                        "type": "object",
                        "description": "A dictionary of parameters required by the tool.",
                        "additionalProperties": True
                    }
                },
                "required": ["tool_name", "parameters"]
            }
        }
    },
    "required": ["message"],
    "additionalProperties": False
}
def load_system_prompt():
    """
    Loads the system prompt from the system_prompt.txt file.
    """
    try:
        with open("system_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError("System prompt file (system_prompt.txt) not found.")

def validate_response_schema(response_json: dict):
    """
    Validate the shape of the JSON response from the LLM.
    """
    if not isinstance(response_json, dict):
        return "[ERROR] Top-level JSON is not an object."

    if "message" not in response_json:
        return "[ERROR] Missing 'message' field."

    if not isinstance(response_json["message"], str):
        return "[ERROR] 'message' must be a string."

    # 'tool_calls' can be null or an array
    if "tool_calls" in response_json and response_json["tool_calls"] is not None:
        if not isinstance(response_json["tool_calls"], list):
            return "[ERROR] 'tool_calls' must be an array or null."
        for idx, call_item in enumerate(response_json["tool_calls"]):
            if "tool_name" not in call_item:
                return f"[ERROR] Missing 'tool_name' in tool_calls[{idx}]."
            if "parameters" not in call_item:
                return f"[ERROR] Missing 'parameters' in tool_calls[{idx}]."
            if not isinstance(call_item["parameters"], dict):
                return f"[ERROR] 'tool_calls[{idx}].parameters' must be an object."

    return None

# ======================
# LLM Call
# ======================
import aiohttp
import json

import aiohttp
import json

import aiohttp
import json

async def call_local_llm(messages):
    """
    Calls the LM Studio server with the specified messages and retrieves the response.
    """
    url = "http://localhost:1234/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "model": "qwen2.5-14b-instruct",  # Ensure this matches the model you're using
        "messages": messages,
        "temperature": 0.8,
        "top_k": 40,
        "top_p": 0.95
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=120) as response:
                if response.status != 200:
                    return {
                        "message": f"Error: Received status code {response.status} from LM Studio.",
                        "tool_calls": []
                    }

                response_data = await response.json()

                # Extract and parse the nested JSON from 'choices[0]["message"]["content"]'
                raw_content = response_data["choices"][0]["message"]["content"]
                parsed_content = json.loads(raw_content)

                return parsed_content

        except aiohttp.ClientError as e:
            return {
                "message": f"Error calling LM Studio: {str(e)}",
                "tool_calls": []
            }
        except (KeyError, json.JSONDecodeError) as e:
            return {
                "message": f"Error parsing LM Studio response: {str(e)}",
                "tool_calls": []
            }





# ======================
# Enhanced System Prompt
# ======================
with open("system_prompt.txt", "r",encoding="utf-8") as f:
    system_prompt_txt = f.read()
SYSTEM_PROMPT = (f"{system_prompt_txt}\n\n"
    "You can manage a Discord server (guild_id=745769392767500322) by calling specialized tools. "
    "You can respond to user messages or use the tools as needed.\n\n"
    "Remember previous information and use the conversation context to make changes as needed. "
    "If the user wants to do bulk actions (e.g., changing everyone's nickname), you can do so by calling a dedicated tool "
    "(e.g., 'mass_change_nickname') or by generating multiple calls. You can also send repeated messages, but be cautious "
    "about spam. In short, you are free to issue multiple commands in a single response by populating the 'tool_calls' array with multiple entries.\n\n"

    "## Tools:\n"
    "1) change_channel_name\n"
    "   - parameters: { \"channel_id\": number, \"channel_name\": string, \"new_name\": string }\n"
    "2) change_nickname\n"
    "   - parameters: { \"user_id\": number, \"user_name\": string, \"new_nickname\": string }\n"
    "3) change_text_channel_topic\n"
    "   - parameters: { \"channel_id\": number, \"channel_name\": string, \"new_topic\": string }\n"
    "4) get_guilds\n"
    "   - parameters: { }\n"
    "5) get_guild_members\n"
    "   - parameters: { }\n"
    "6) get_channels\n"
    "   - parameters: { }\n"
    "7) create_role\n"
    "   - parameters: { \"role_name\": string }\n"
    "8) tts_speak\n"
    "   - parameters: { \"text\": string }\n"
    "9) voicemode\n"
    "   - parameters: { \"user_id\": number, \"user_name\": string, \"mode\": string } (mute, unmute, deafen, undeafen)\n"
    "10) create_text_channel\n"
    "    - parameters: { \"channel_name\": string }\n"
    "11) create_voice_channel\n"
    "    - parameters: { \"channel_name\": string }\n"
    "12) delete_channel\n"
    "    - parameters: { \"channel_id\": number, \"channel_name\": string }\n"
    "13) kick_member\n"
    "    - parameters: { \"user_id\": number, \"user_name\": string, \"reason\": string }\n"
    "14) mass_change_nickname\n"
    "    - parameters: { \"new_nickname\": string }\n"
    "15) mass_send_message\n"
    "    - parameters: { \"text\": string, \"times\": number }\n\n"

    "When you respond, ALWAYS produce valid JSON with this shape:\n"
    "{\n"
    "  \"message\": \"...\",\n"
    "  \"tool_calls\": [\n"
    "    {\n"
    "      \"tool_name\": \"...\",\n"
    "      \"parameters\": {\n"
    "         ...\n"
    "      }\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "No extra keys.\n"
    "You can call multiple tools by providing multiple objects in the 'tool_calls' array.\n"
    "Use 'mass_change_nickname' to change everyone's nickname at once if desired.\n"
    "Use 'mass_send_message' to send repeated messages, but consider rate limits.\n"
)

messages = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    user_content = message.content.strip()
    if not user_content:
        await message.channel.send("Done")  # Respond with "Done" if the user's message is empty
        return

    # Load the system prompt
    try:
        system_prompt = load_system_prompt()
    except FileNotFoundError as e:
        await message.channel.send(f"[ERROR] {str(e)}")
        return

    # Prepare the system and user messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    # Call the LLM asynchronously
    assistant_reply_json = await call_local_llm(messages)

    # Validate the LLM's response
    if not isinstance(assistant_reply_json, dict) or "message" not in assistant_reply_json:
        await message.channel.send("[ERROR] Invalid response from assistant.")
        return

    # Check if the assistant's message is empty
    reply_message = assistant_reply_json["message"].strip()
    if not reply_message:
        reply_message = "Done"  # Default response for empty messages

    # Send the assistant's message to the channel
    await message.channel.send(reply_message)

    # Process tool calls if present
    tool_calls = assistant_reply_json.get("tool_calls", [])
    if tool_calls:
        results = await server_manager.handle_tool_calls(tool_calls)
        for result in results:
            await message.channel.send(f"[Tool result]\n{result}")




# ======================
# Additional Commands
# ======================
@bot.command(name="list_tools")
async def list_tools(ctx):
    """Lists the available tools for the model."""
    tools = [
        "change_channel_name",
        "change_nickname",
        "change_text_channel_topic",
        "get_guilds",
        "get_guild_members",
        "get_channels",
        "create_role",
        "tts_speak",
        "voicemode",
        "create_text_channel",
        "create_voice_channel",
        "delete_channel",
        "kick_member",
        "mass_change_nickname",
        "mass_send_message"
    ]
    await ctx.send(f"Available tools: {', '.join(tools)}")

@bot.command(name="manual_tool")
async def manual_tool(ctx, *, tool_call_json: str):
    """
    Manually execute a single or multiple tool calls by providing valid JSON.
    Examples:
    - Single:
      {"tool_name": "change_nickname", "parameters": {"user_id": 12345, "new_nickname": "NewName"}}
    - Multiple:
      [
        {"tool_name": "get_guild_members", "parameters": {}},
        {"tool_name": "mass_change_nickname", "parameters": {"new_nickname": "Everyone"}}
      ]
    """
    try:
        parsed = json.loads(tool_call_json)

        if isinstance(parsed, dict) and "tool_name" in parsed:
            # Single tool call
            result = await server_manager.handle_tool_call(parsed)
            await ctx.send(f"[Manual Tool Result]\n{result}")
        elif isinstance(parsed, list):
            # Multiple tool calls
            results = await server_manager.handle_tool_calls(parsed)
            for idx, r in enumerate(results):
                await ctx.send(f"[Manual Tool Result #{idx+1}]\n{r}")
        else:
            await ctx.send("Invalid JSON format. Provide an object (with 'tool_name') or an array of such objects.")
    except json.JSONDecodeError:
        await ctx.send("Invalid JSON.")
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# ======================
# Run the Bot
# ======================
if __name__ == "__main__":
    try:
        print("[DEBUG] Starting bot...")
        bot.run(
            TOKEN,
        )
    except Exception as e:
        print(f"[ERROR] Bot run error: {e}")
