# cogs/music_cog.py

import discord
from discord.ext import commands
import asyncio
import yt_dlp
import random
import re

###################################################
#  Search Filtering Settings
###################################################
SEARCH_SUFFIX = "music lyrics audio"
SEARCH_EXCLUDE = ["interview", "podcast", "trailer"]


def is_url(string: str) -> bool:
    pattern = re.compile(r'^(http|https)://', re.IGNORECASE)
    return bool(pattern.match(string))


###################################################
#   YTDLSource Class
###################################################
class YTDLSource(discord.PCMVolumeTransformer):
    """
    Handles YT-DL extraction and PCM transformation.
    """
    def __init__(self, source, *, data, volume=0.5, raw_info=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title") or "Unknown Title"
        self.url = data.get("url")  # direct stream link
        self.webpage_url = data.get("webpage_url") or ""
        self.thumbnail = data.get("thumbnail") or ""
        self.raw_info = raw_info or data

    @classmethod
    async def from_search_or_url(cls, query, loop=None):
        """If query is a URL, use it. Otherwise, search YouTube (with music bias)."""
        loop = loop or asyncio.get_event_loop()

        if is_url(query):
            search_input = query
        else:
            # Exclude certain words
            cleaned_query = " ".join(
                word for word in query.split()
                if all(x.lower() not in word.lower() for x in SEARCH_EXCLUDE)
            )
            # Append extra terms for music
            cleaned_query = f"{cleaned_query} {SEARCH_SUFFIX}".strip()
            # We'll pull up to 10 search results
            search_input = f"ytsearch10:{cleaned_query}"

        ytdl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'source_address': '0.0.0.0',
        }
        ytdl = yt_dlp.YoutubeDL(ytdl_opts)
        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(search_input, download=False)
        )

        if not data:
            raise ValueError("No data returned from YouTube search.")
        if 'entries' in data:
            entries = [e for e in data['entries'] if e]
            if not entries:
                raise ValueError("No valid entries found.")
            data = entries[0]

        if 'url' not in data:
            raise ValueError("No valid URL found in YouTube data.")

        raw_info = data
        filename = data['url']
        raw_info['current_offset'] = 0  # start at 0s

        return cls(
            discord.FFmpegPCMAudio(filename, options="-loglevel quiet"),
            data=data,
            volume=0.5,
            raw_info=raw_info
        )

    @classmethod
    def create_seek_source(cls, raw_info, offset_seconds=0):
        """Rebuild the FFmpegPCMAudio with -ss <offset_seconds>."""
        if offset_seconds < 0:
            offset_seconds = 0
        new_opts = f"-loglevel quiet -ss {offset_seconds}"
        filename = raw_info['url']
        audio = discord.FFmpegPCMAudio(filename, before_options=new_opts, options="-loglevel quiet")
        new_data = raw_info.copy()
        new_data['current_offset'] = offset_seconds
        return cls(audio, data=new_data, volume=0.5, raw_info=new_data)


###################################################
#   Main Music Cog
###################################################
class MusicCog(commands.Cog):
    """
    A music cog that uses only YouTube-based logic (via yt_dlp).
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Queue: {guild_id: [(title, YTDLSource), (title, YTDLSource), ...]}
        self.song_queue = {}
        # Playback state: {guild_id: bool}
        self.is_playing = {}
        # Track "Now Playing" message for each guild
        self.nowplaying_message = {}  # guild_id -> discord.Message or None

    def get_queue(self, guild_id: int):
        if guild_id not in self.song_queue:
            self.song_queue[guild_id] = []
        return self.song_queue[guild_id]

    async def ensure_voice(self, ctx: commands.Context):
        user = ctx.author
        if not user.voice or not user.voice.channel:
            await ctx.send("You must be in a voice channel first!")
            return None

        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if not voice_client or not voice_client.is_connected():
            voice_client = await user.voice.channel.connect()
        else:
            if voice_client.channel != user.voice.channel:
                await voice_client.move_to(user.voice.channel)
        return voice_client

    async def play_next(self, guild_id: int, voice_client: discord.VoiceClient):
        """Plays next song or stops if queue empty."""
        queue = self.get_queue(guild_id)
        if not queue:
            self.is_playing[guild_id] = False
            await self.update_nowplaying_embed(guild_id, voice_client, ended=True)
            return

        title, source = queue.pop(0)
        self.is_playing[guild_id] = True

        async def _after_track():
            # Sleep a bit to ensure we don't skip instantly
            await asyncio.sleep(1)
            await self.play_next(guild_id, voice_client)

        def after_play(err):
            if err:
                print(f"[ERROR] Audio playback error: {err}")
                # We won't forcibly skip the track on error,
                # but once the track "ends", we eventually go to the next.
            # Next track logic
            asyncio.run_coroutine_threadsafe(_after_track(), self.bot.loop)

        voice_client.play(source, after=after_play)
        print(f"[DEBUG] Now playing: {title}")
        await self.update_nowplaying_embed(guild_id, voice_client, current_source=source)

    async def update_nowplaying_embed(self, guild_id: int, voice_client: discord.VoiceClient, *, ended=False, current_source=None):
        """Updates the Now Playing embed in the stored message."""
        if guild_id not in self.nowplaying_message or not self.nowplaying_message[guild_id]:
            return
        msg = self.nowplaying_message[guild_id]

        if ended or not current_source:
            embed = discord.Embed(
                title="Now Playing",
                description="No track is currently playing.",
                color=discord.Color.red()
            )
            await msg.edit(embed=embed, view=None)
            return

        title = current_source.title
        url = current_source.webpage_url
        thumb = current_source.thumbnail

        embed = discord.Embed(
            title="Now Playing",
            description=f"[**{title}**]({url})",
            color=discord.Color.blue()
        )
        if thumb:
            embed.set_thumbnail(url=thumb)
        embed.set_footer(text="Use the buttons below to control playback.")

        view = MusicControlView(
            music_cog=self,
            guild_id=guild_id,
            voice_client=voice_client
        )
        await msg.edit(embed=embed, view=view)

    ###################################################
    #  BASIC MUSIC COMMANDS
    ###################################################
    @commands.command(name="play")
    async def play_command(self, ctx: commands.Context, *, query: str):
        """!play <song name or URL>."""
        voice_client = await self.ensure_voice(ctx)
        if not voice_client:
            return

        msg = await ctx.send(f"Searching for: **{query}**...")
        try:
            source = await YTDLSource.from_search_or_url(query)
        except Exception as e:
            await msg.edit(content=f"⚠️ **Error:** {e}")
            return

        q = self.get_queue(ctx.guild.id)
        q.append((source.title, source))
        await msg.edit(content=f"✅ **Added to queue:** {source.title}")

        if not self.is_playing.get(ctx.guild.id):
            await self.play_next(ctx.guild.id, voice_client)

    @commands.command(name="skip")
    async def skip_command(self, ctx: commands.Context):
        """Skip the current track."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            await ctx.send("⏭ **Skipped the track**")
        else:
            await ctx.send("No track is currently playing or paused.")

    @commands.command(name="queue")
    async def queue_command(self, ctx: commands.Context):
        """Show the upcoming queue."""
        q = self.get_queue(ctx.guild.id)
        if not q:
            await ctx.send("The queue is empty.")
        else:
            desc = "\n".join(f"**-** {title}" for (title, _) in q)
            await ctx.send(f"**Current queue:**\n{desc}")

    @commands.command(name="stop")
    async def stop_command(self, ctx: commands.Context):
        """Stop & clear queue."""
        guild_id = ctx.guild.id
        q = self.get_queue(guild_id)
        q.clear()
        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        self.is_playing[guild_id] = False
        await ctx.send("⏹ **Stopped playback and cleared the queue**")

    @commands.command(name="leave")
    async def leave_command(self, ctx: commands.Context):
        """Leave the voice channel."""
        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if vc and vc.is_connected():
            await vc.disconnect()
            self.is_playing[ctx.guild.id] = False
            await ctx.send("👋 **Left the voice channel**")
        else:
            await ctx.send("I'm not connected to any voice channel.")

    ###################################################
    #  NOW PLAYING UI
    ###################################################
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_command(self, ctx: commands.Context):
        """
        Show an embed with playback controls 
        (Pause, Resume, Skip, Stop, Queue, Fwd, Rew, Leave).
        """
        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if not vc:
            await ctx.send("I'm not connected to any voice channel.")
            return

        if not (vc.is_playing() or vc.is_paused()):
            await ctx.send("No track is currently playing.")
            return

        current_source = None
        if isinstance(vc.source, YTDLSource):
            current_source = vc.source

        embed = discord.Embed(
            title="Now Playing",
            color=discord.Color.blue()
        )
        if current_source:
            title = current_source.title
            url = current_source.webpage_url
            thumb = current_source.thumbnail
            embed.description = f"[**{title}**]({url})"
            if thumb:
                embed.set_thumbnail(url=thumb)
        else:
            embed.description = "Unknown Track"
        embed.set_footer(text="Use the buttons below to control playback.")

        view = MusicControlView(
            music_cog=self,
            guild_id=ctx.guild.id,
            voice_client=vc
        )

        old_msg = self.nowplaying_message.get(ctx.guild.id)
        if old_msg:
            try:
                await old_msg.delete()
            except:
                pass

        np_msg = await ctx.send(embed=embed, view=view)
        self.nowplaying_message[ctx.guild.id] = np_msg

    ###################################################
    #  REMIX COMMAND (YouTube-based)
    ###################################################
    @commands.command(name="remix")
    async def remix_command(self, ctx: commands.Context, *, artists: str):
        """
        !remix <artist1>, <artist2>, ... up to 5
        Gathers multiple tracks, shuffles them, queues them,
        then auto-sends nowplaying panel.
        """
        artist_list = [a.strip() for a in artists.split(",") if a.strip()]
        if len(artist_list) < 1:
            await ctx.send("⚠️ **Provide at least 1 artist.**")
            return
        if len(artist_list) > 5:
            await ctx.send("⚠️ **Max 5 artists allowed.**")
            return

        vc = await self.ensure_voice(ctx)
        if not vc:
            return

        msg = await ctx.send("Gathering tracks from YouTube. Please wait...")

        results_per_artist = 10
        track_entries = []
        for artist in artist_list:
            cleaned_artist = " ".join(
                w for w in artist.split()
                if all(x.lower() not in w.lower() for x in SEARCH_EXCLUDE)
            )
            full_search = f"{cleaned_artist} {SEARCH_SUFFIX}"
            search_str = f"ytsearch{results_per_artist}:{full_search}"

            ytdl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'ignoreerrors': True,
                'no_warnings': True,
                'source_address': '0.0.0.0',
            }
            ytdl = yt_dlp.YoutubeDL(ytdl_opts)
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ytdl.extract_info(search_str, download=False)
                )
                if data and 'entries' in data:
                    for entry in data['entries']:
                        if entry:
                            track_entries.append(entry)
            except Exception as e:
                print(f"[WARN] Could not fetch YouTube for '{artist}': {e}")

        if not track_entries:
            await msg.edit(content="⚠️ **No results found for these artists.**")
            return

        random.shuffle(track_entries)
        track_entries = track_entries[:50]

        tasks = []
        guild_id = ctx.guild.id
        for entry in track_entries:
            if not entry.get('webpage_url'):
                continue
            track_url = entry['webpage_url']
            tasks.append(asyncio.create_task(self.fetch_and_queue(track_url, guild_id)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        queued_count = sum(1 for r in results if not isinstance(r, Exception))

        await msg.edit(content=f"✅ **Queued {queued_count} tracks** from {', '.join(artist_list)}.")

        if not self.is_playing.get(ctx.guild.id):
            await self.play_next(ctx.guild.id, vc)

        await self.nowplaying_command(ctx)

    async def fetch_and_queue(self, query: str, guild_id: int):
        """Search YT (or direct link) and append track to queue."""
        try:
            source = await YTDLSource.from_search_or_url(query)
            self.get_queue(guild_id).append((source.title, source))
        except Exception as e:
            return e
        return True


###################################################
#   Music Control View
###################################################
class MusicControlView(discord.ui.View):
    """
    UI with Pause, Resume, Skip, Stop, Queue, Fwd, Rew, Leave.
    We'll do `defer_update()` to keep the embed intact, 
    then send ephemeral feedback so the user knows it worked.
    """
    def __init__(self, music_cog: MusicCog, guild_id: int, voice_client: discord.VoiceClient, *, timeout=300):
        super().__init__(timeout=timeout)
        self.music_cog = music_cog
        self.guild_id = guild_id
        self.voice_client = voice_client

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.blurple)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer_update()
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            # ephemeral feedback
            await interaction.followup.send("⏸ Paused.", ephemeral=True)
            await self.music_cog.update_nowplaying_embed(self.guild_id, self.voice_client)
        else:
            await interaction.followup.send("No track playing to pause.", ephemeral=True)

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.green)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer_update()
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            await interaction.followup.send("▶️ Resumed.", ephemeral=True)
            await self.music_cog.update_nowplaying_embed(self.guild_id, self.voice_client)
        else:
            await interaction.followup.send("No track paused to resume.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.red)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer_update()
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
            await interaction.followup.send("⏭ Skipped.", ephemeral=True)
        else:
            await interaction.followup.send("Nothing to skip.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer_update()
        q = self.music_cog.get_queue(self.guild_id)
        q.clear()
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        self.music_cog.is_playing[self.guild_id] = False
        await self.music_cog.update_nowplaying_embed(self.guild_id, self.voice_client, ended=True)
        await interaction.followup.send("⏹ Stopped & cleared queue.", ephemeral=True)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.gray)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer_update()
        q = self.music_cog.get_queue(self.guild_id)
        if not q:
            text = "The queue is empty."
        else:
            desc = "\n".join(f"**-** {title}" for (title, _) in q)
            text = f"**Current queue:**\n{desc}"
        await interaction.followup.send(text, ephemeral=True)

    @discord.ui.button(label="<< Rewind 10s", style=discord.ButtonStyle.gray)
    async def rewind_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer_update()
        await self._seek(interaction, -10)

    @discord.ui.button(label="Forward 10s >>", style=discord.ButtonStyle.gray)
    async def forward_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer_update()
        await self._seek(interaction, 10)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.gray)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer_update()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.music_cog.is_playing[self.guild_id] = False
            await self.music_cog.update_nowplaying_embed(self.guild_id, self.voice_client, ended=True)
            await interaction.followup.send("👋 Left the voice channel.", ephemeral=True)
        else:
            await interaction.followup.send("Not currently connected.", ephemeral=True)

    async def _seek(self, interaction: discord.Interaction, offset: int):
        if not self.voice_client or (not self.voice_client.is_playing() and not self.voice_client.is_paused()):
            await interaction.followup.send("No active track to seek.", ephemeral=True)
            return

        current_source = self.voice_client.source
        if not (isinstance(current_source, YTDLSource) and current_source.raw_info):
            await interaction.followup.send("Cannot seek this track.", ephemeral=True)
            return

        raw_info = current_source.raw_info
        current_offset = raw_info.get('current_offset', 0)
        new_offset = current_offset + offset
        if new_offset < 0:
            new_offset = 0

        try:
            new_source = YTDLSource.create_seek_source(raw_info, offset_seconds=new_offset)
        except Exception as e:
            await interaction.followup.send(f"Seek error: {e}", ephemeral=True)
            return

        self.voice_client.stop()
        self.voice_client.play(new_source)
        await self.music_cog.update_nowplaying_embed(self.guild_id, self.voice_client, current_source=new_source)
        if offset > 0:
            await interaction.followup.send(f"⏩ Forwarded 10s (now at ~{new_offset}s).", ephemeral=True)
        else:
            await interaction.followup.send(f"⏪ Rewound 10s (now at ~{new_offset}s).", ephemeral=True)


###################################################
#   Setup function
###################################################
async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
