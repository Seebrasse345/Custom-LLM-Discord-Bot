# cogs/voice_tts_manager.py

import discord
from discord.ext import commands
import asyncio
import os
import uuid

from .tts_engine import tts_engine
from .conversation_manager import private_sessions, save_session

class VoiceTTSManagerCog(commands.Cog):
    """
    Manages TTS reading in voice channels for server 'bot-chat' channel messages.
    **Private DMs are never read aloud.**
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {}  # Maps guild_id -> VoiceClient (connected instance)
        self.tts_queues = {}     # Maps guild_id -> asyncio.Queue of wav_path

    async def join_voice(self, ctx: commands.Context):
        """
        Joins the author's current voice channel.
        Returns the VoiceClient or None if cannot join.
        """
        guild = ctx.guild
        if not guild:
            await ctx.send("[ERROR] Not in a guild.")
            return None

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("[ERROR] You are not in a voice channel.")
            return None

        voice_channel = ctx.author.voice.channel
        if not voice_channel:
            await ctx.send("[ERROR] voice channel not found.")
            return None

        voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
        if voice_client and voice_client.is_connected():
            # Already connected, maybe move
            if voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
        else:
            voice_client = await voice_channel.connect()

        return voice_client

    async def leave_voice(self, guild_id: int):
        """
        Disconnect from voice if connected for a particular guild.
        """
        vc = self.voice_clients.get(guild_id)
        if vc and vc.is_connected():
            await vc.disconnect(force=True)
        self.voice_clients.pop(guild_id, None)
        self.tts_queues.pop(guild_id, None)

    async def queue_tts_for_guild(self, guild_id: int, text: str):
        """
        Called from conversation_manager after a new assistant message is generated in 'bot-chat'.
        We generate TTS audio, push it into the guild's TTS queue.
        If not currently playing, begin playback.
        """
        if guild_id not in self.tts_queues:
            # Create a queue and a playback task
            self.tts_queues[guild_id] = asyncio.Queue()
            asyncio.create_task(self._playback_worker(guild_id))

        # Generate TTS .wav
        wav_path = f"tts_{uuid.uuid4()}.wav"
        try:
            await asyncio.to_thread(tts_engine.generate_wav, text, wav_path)
        except Exception as e:
            print(f"[ERROR] TTS generation failed: {e}")
            return

        # Enqueue
        await self.tts_queues[guild_id].put(wav_path)

    async def _playback_worker(self, guild_id: int):
        """
        Continuously runs for each guild_id that has a queue.
        Plays TTS files in sequence.
        """
        while True:
            if guild_id not in self.tts_queues:
                return  # guild canceled or voice mode turned off
            queue = self.tts_queues[guild_id]
            try:
                wav_path = await queue.get()  # block until there's an item
            except asyncio.CancelledError:
                return

            # Check if still connected
            vc = self.voice_clients.get(guild_id)
            if not vc or not vc.is_connected():
                # voice mode turned off or we got disconnected
                # cleanup leftover items
                queue.task_done()
                if os.path.exists(wav_path):
                    os.remove(wav_path)
                continue

            audio_source = discord.FFmpegPCMAudio(wav_path, options="-loglevel quiet")
            vc.play(audio_source)

            # Wait until playback finishes
            while vc.is_playing():
                await asyncio.sleep(0.5)

            # Cleanup
            queue.task_done()
            if os.path.exists(wav_path):
                os.remove(wav_path)

    @commands.command(name="voicemode")
    async def voicemode(self, ctx: commands.Context, mode: str):
        """
        Usage: !voicemode on/off
        If on, the bot joins 'bot-chat' voice channel and reads out messages via TTS.
        If off, it disconnects.
        """
        guild = ctx.guild
        if not guild:
            await ctx.send("[ERROR] Not in a guild.")
            return

        mode = mode.lower()
        if mode == "on":
            # Turn on voice mode
            vc = await self.join_voice(ctx)
            if not vc:
                return  # cannot join
            self.voice_clients[guild.id] = vc
            # Set a flag in guild data if needed
            await ctx.send("Voice mode is now ON. I'll read messages in 'bot-chat' via TTS.")
        elif mode == "off":
            # Turn off voice mode
            await self.leave_voice(guild.id)
            await ctx.send("Voice mode is now OFF. Disconnected from voice.")
        else:
            await ctx.send("Usage: !voicemode on/off")

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceTTSManagerCog(bot))
