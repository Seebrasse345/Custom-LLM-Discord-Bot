import discord
from discord.ext import commands
import os
import asyncio
import json
import uuid
import tempfile
import requests
from dotenv import load_dotenv
from TTS.api import TTS

# ======================
# Load Environment Variables
# ======================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("No Discord API token found in environment variables!")

# ======================
# Coqui TTS Class
# ======================
class CoquiTTS:
    def __init__(self, model_name="tts_models/en/ljspeech/tacotron2-DDC"):
        """
        Initialize and load the TTS model.
        """
        self.model_name = model_name
        print(f"Loading TTS model: {self.model_name}")
        self.tts = TTS(model_name=self.model_name)
        print("TTS model loaded successfully.")

    def generate_wav(self, text: str, output_file: str):
        """
        Generate TTS audio and write to output_file.
        This should be called in a non-blocking manner (e.g., via asyncio.to_thread).
        """
        self.tts.tts_to_file(text=text, file_path=output_file)

tts_engine = CoquiTTS()

# ======================
# DiscordServerManager Class
# ======================
class DiscordServerManager:
    def __init__(self, bot):
        self.bot = bot

    async def change_channel_name(self, guild_id, channel_id, new_name):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return "Guild not found."

        channel = guild.get_channel(channel_id)
        if not channel:
            return "Channel not found."

        try:
            await channel.edit(name=new_name)
            print(f"Channel {channel_id} name changed to {new_name} in guild {guild_id}")
            return f"Channel name changed to {new_name}."
        except Exception as e:
            print(f"Error changing channel name: {e}")
            return f"Failed to change channel name: {str(e)}"

    async def change_nickname(self, guild_id, user_id, new_nickname):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return "Guild not found."

        member = guild.get_member(user_id)
        if not member:
            return "Member not found."

        try:
            await member.edit(nick=new_nickname)
            print(f"Nickname for user {user_id} changed to {new_nickname} in guild {guild_id}")
            return f"Nickname changed to {new_nickname}."
        except Exception as e:
            print(f"Error changing nickname: {e}")
            return f"Failed to change nickname: {str(e)}"

    async def change_text_channel_topic(self, guild_id, channel_id, new_topic):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return "Guild not found."

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return "Text channel not found."

        try:
            await channel.edit(topic=new_topic)
            print(f"Channel {channel_id} topic changed to {new_topic} in guild {guild_id}")
            return f"Channel topic changed to: {new_topic}."
        except Exception as e:
            print(f"Error changing channel topic: {e}")
            return f"Failed to change channel topic: {str(e)}"

    async def get_guilds(self):
        try:
            guilds = [guild for guild in self.bot.guilds]
            print(f"Retrieved guilds: {[guild.name for guild in guilds]}")
            return guilds
        except Exception as e:
            print(f"Error retrieving guilds: {e}")
            return f"Failed to retrieve guilds: {str(e)}"

    async def get_guild_members(self, guild_id):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return "Guild not found."

        try:
            members = [member for member in guild.members]
            print(f"Retrieved members in guild {guild_id}: {[member.name for member in members]}")
            return members
        except Exception as e:
            print(f"Error retrieving members: {e}")
            return f"Failed to retrieve members: {str(e)}"

    async def get_channels(self, guild_id):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return "Guild not found."

        try:
            channels = [channel for channel in guild.channels]
            print(f"Retrieved channels in guild {guild_id}: {[channel.name for channel in channels]}")
            return channels
        except Exception as e:
            print(f"Error retrieving channels: {e}")
            return f"Failed to retrieve channels: {str(e)}"

    async def handle_tool_call(self, tool_call):
        tool_name = tool_call.get("tool_name")
        parameters = tool_call.get("parameters", {})

        try:
            if tool_name == "change_channel_name":
                return await self.change_channel_name(
                    parameters["guild_id"],
                    parameters["channel_id"],
                    parameters["new_name"]
                )
            elif tool_name == "change_nickname":
                return await self.change_nickname(
                    parameters["guild_id"],
                    parameters["user_id"],
                    parameters["new_nickname"]
                )
            elif tool_name == "change_text_channel_topic":
                return await self.change_text_channel_topic(
                    parameters["guild_id"],
                    parameters["channel_id"],
                    parameters["new_topic"]
                )
            elif tool_name == "get_guilds":
                guilds = await self.get_guilds()
                return [guild.name for guild in guilds]
            elif tool_name == "get_guild_members":
                members = await self.get_guild_members(parameters["guild_id"])
                return [member.name for member in members]
            elif tool_name == "get_channels":
                channels = await self.get_channels(parameters["guild_id"])
                return [channel.name for channel in channels]
            else:
                return "Tool not recognized."
        except KeyError as e:
            print(f"Missing parameter in tool call: {e}")
            return f"Missing parameter: {str(e)}"
        except Exception as e:
            print(f"Error executing tool call: {e}")
            return f"Error executing tool: {str(e)}"

# ======================
# Bot Setup
# ======================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
server_manager = DiscordServerManager(bot)

# ======================
# LLM Call Function
# ======================
def call_local_llm(messages):
    """
    Call your local LM Studio server at http://localhost:1234.
    Adjust the 'model' field as needed.
    """
    url = "http://127.0.0.1:1234/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "llm-model",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 100,
        "min_tokens": 10,
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status()
        data = response.json()
        print(f"LLM Response: {data}")
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error calling local LLM: {e}")
        return "Sorry, I'm having trouble thinking right now."

# ======================
# Command: Execute Tool
# ======================
@bot.command()
async def execute_tool(ctx, *, tool_call_json: str):
    """
    Execute a tool call based on JSON input.
    Example:
    !execute_tool {"tool_name": "change_channel_name", "parameters": {"guild_id": 123, "channel_id": 456, "new_name": "new-channel"}}
    """
    try:
        tool_call = json.loads(tool_call_json)

        # Call LLM if message field exists
        if "message" in tool_call:
            llm_response = call_local_llm([{"role": "system", "content": "Process this tool call."}, {"role": "user", "content": tool_call["message"]}])
            await ctx.send(f"LLM Response: {llm_response}")

        result = await server_manager.handle_tool_call(tool_call)
        await ctx.send(f"Result: {result}")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format")
        await ctx.send("Invalid JSON format.")
    except Exception as e:
        print(f"Error executing tool: {e}")
        await ctx.send(f"Error: {str(e)}")

# ======================
# Run the Bot
# ======================
if __name__ == "__main__":
    try:
        print("Starting bot...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")
