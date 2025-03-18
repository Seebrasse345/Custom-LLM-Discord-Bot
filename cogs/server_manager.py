# cogs/server_manager.py

import discord
from discord.ext import commands
import json

DEFAULT_GUILD_ID = 745769392767500322  # Replace with your guild ID

def find_channel_by_name(guild, name: str):
    if not name:
        return None
    name_lower = name.strip().lower()
    for ch in guild.channels:
        if ch.name.lower() == name_lower:
            return ch
    return None

def find_member_by_name(guild, name: str):
    if not name:
        return None
    name_lower = name.strip().lower()
    for m in guild.members:
        if m.name.lower() == name_lower or (m.nick and m.nick.lower() == name_lower):
            return m
    return None

class DiscordServerManager:
    def __init__(self, bot):
        self.bot = bot

    # Example tool calls (implement your actual tools here)
    async def change_channel_name(self, channel_id=None, channel_name=None, new_name=None):
        if not new_name:
            return "[ERROR] Missing 'new_name'."

        guild = self.bot.get_guild(DEFAULT_GUILD_ID)
        if not guild:
            return f"[ERROR] Guild {DEFAULT_GUILD_ID} not found."

        channel = None
        if channel_id:
            channel = guild.get_channel(channel_id)
        if not channel and channel_name:
            channel = find_channel_by_name(guild, channel_name)
        if not channel:
            return "[ERROR] Channel not found."

        try:
            old_name = channel.name
            await channel.edit(name=new_name)
            return f"Channel '{old_name}' renamed to '{new_name}'."
        except Exception as e:
            return f"[ERROR] Failed to rename channel: {e}"

    # Add more tool methods as needed...

    async def handle_tool_call(self, tool_call: dict):
        tool_name = tool_call.get("tool_name")
        params = tool_call.get("parameters", {})

        try:
            if tool_name == "change_channel_name":
                return await self.change_channel_name(**params)
            # Add more tool handling as needed...
            else:
                return f"[ERROR] Tool not recognized: '{tool_name}'."
        except Exception as e:
            return f"[ERROR] {str(e)}"

    async def handle_tool_calls(self, tool_calls: list):
        results = []
        for call in tool_calls:
            result = await self.handle_tool_call(call)
            results.append(result)
        return results

class ServerManagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.manager = DiscordServerManager(bot)

    @commands.command(name="list_tools")
    async def list_tools(self, ctx):
        tools = [
            "change_channel_name",
            # Add other tools here...
        ]
        await ctx.send(f"Available tools: {', '.join(tools)}")

    @commands.command(name="manual_tool")
    async def manual_tool(self, ctx, *, tool_call_json: str):
        """
        Manually execute tool calls by JSON input.
        Example:
          {"tool_name": "change_channel_name", "parameters": {"channel_id": 12345, "new_name": "new-channel"}}
        """
        try:
            parsed = json.loads(tool_call_json)
            if isinstance(parsed, dict) and "tool_name" in parsed:
                result = await self.manager.handle_tool_call(parsed)
                await ctx.send(f"[Manual Tool Result]\n{result}")
            elif isinstance(parsed, list):
                results = await self.manager.handle_tool_calls(parsed)
                for idx, r in enumerate(results):
                    await ctx.send(f"[Manual Tool Result #{idx+1}]\n{r}")
            else:
                await ctx.send("Invalid JSON. Must be a single object or an array of objects.")
        except json.JSONDecodeError:
            await ctx.send("Invalid JSON.")
        except Exception as e:
            await ctx.send(f"[ERROR] {str(e)}")

    ###################################
    # 10 NEW DIRECT SERVER MANAGEMENT COMMANDS (NO TOOLS)
    ###################################

    # 1) CLEAR: delete last <amount> messages in current channel
    @commands.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def clear_channel_messages(self, ctx, amount: int):
        """
        Usage: !clear <amount>
        Deletes the last <amount> messages in the current text channel.
        """
        if amount < 1:
            await ctx.send("[ERROR] Amount must be >= 1.")
            return
        deleted = await ctx.channel.purge(limit=amount+1)  # +1 to include the command message itself
        await ctx.send(f"Cleared {len(deleted)-1} messages.", delete_after=5)  # ephemeral notice

    # 2) BAN: Ban a user by mention or ID
    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban_user(self, ctx, user: discord.User, *, reason=None):
        """
        Usage: !ban @user [reason...]
        Bans the user from the server.
        """
        try:
            await ctx.guild.ban(user, reason=reason)
            await ctx.send(f"Banned {user.name} (ID: {user.id}). Reason: {reason}")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 3) UNBAN: Unban a user by ID
    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban_user(self, ctx, user_id: int):
        """
        Usage: !unban <user_id>
        Unbans the user from the server by their ID.
        """
        try:
            banned_users = await ctx.guild.bans()
            for ban_entry in banned_users:
                if ban_entry.user.id == user_id:
                    await ctx.guild.unban(ban_entry.user)
                    await ctx.send(f"Unbanned {ban_entry.user.name} (ID: {ban_entry.user.id}).")
                    return
            await ctx.send("User not found in bans.")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 4) LOCKCHANNEL: set channel read-only for @everyone
    @commands.command(name="lockchannel")
    @commands.has_permissions(manage_channels=True)
    async def lock_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Usage: !lockchannel [#channelMention or channelID]
        Makes the channel read-only for @everyone.
        """
        if channel is None:
            channel = ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        try:
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(f"Locked channel {channel.mention}.")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 5) UNLOCKCHANNEL: revert read-only for @everyone
    @commands.command(name="unlockchannel")
    @commands.has_permissions(manage_channels=True)
    async def unlock_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Usage: !unlockchannel [#channelMention or channelID]
        Allows @everyone to send messages again.
        """
        if channel is None:
            channel = ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        try:
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(f"Unlocked channel {channel.mention}.")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 6) MOVE: Move a user to another voice channel
    @commands.command(name="move")
    @commands.has_permissions(move_members=True)
    async def move_user(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        """
        Usage: !move @user #voiceChannel
        Move a user to the specified voice channel.
        """
        if not member.voice:
            await ctx.send("The user is not in a voice channel.")
            return
        try:
            await member.move_to(channel)
            await ctx.send(f"Moved {member.mention} to {channel.name}.")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 7) GIVEROLE: Assign a role to a user
    @commands.command(name="giverole")
    @commands.has_permissions(manage_roles=True)
    async def give_role(self, ctx, member: discord.Member, role: discord.Role):
        """
        Usage: !giverole @user @role
        Gives the user the specified role.
        """
        try:
            await member.add_roles(role)
            await ctx.send(f"Gave role '{role.name}' to {member.mention}.")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 8) REMOVEROLE: Remove a role from a user
    @commands.command(name="removerole")
    @commands.has_permissions(manage_roles=True)
    async def remove_role(self, ctx, member: discord.Member, role: discord.Role):
        """
        Usage: !removerole @user @role
        Removes the specified role from the user.
        """
        try:
            await member.remove_roles(role)
            await ctx.send(f"Removed role '{role.name}' from {member.mention}.")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 9) PIN: Pin a specific message by ID in the current channel
    @commands.command(name="pin")
    @commands.has_permissions(manage_messages=True)
    async def pin_message(self, ctx, message_id: int):
        """
        Usage: !pin <message_id>
        Pins the specified message in the current channel.
        """
        try:
            msg = await ctx.channel.fetch_message(message_id)
            await msg.pin()
            await ctx.send(f"Pinned message ID: {message_id}")
        except discord.NotFound:
            await ctx.send("[ERROR] Message not found.")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 10) UNPIN: Unpin a specific message by ID
    @commands.command(name="unpin")
    @commands.has_permissions(manage_messages=True)
    async def unpin_message(self, ctx, message_id: int):
        """
        Usage: !unpin <message_id>
        Unpins the specified message in the current channel.
        """
        try:
            msg = await ctx.channel.fetch_message(message_id)
            await msg.unpin()
            await ctx.send(f"Unpinned message ID: {message_id}")
        except discord.NotFound:
            await ctx.send("[ERROR] Message not found.")
        except Exception as e:
            await ctx.send(f"[ERROR] {e}")

    # 11) WORDFINDER: Find all messages from a user containing a specific word in the current channel
    @commands.command(name="wordfinder")
    async def wordfinder(self, ctx, member: discord.Member, word: str):
        """
        Usage: !wordfinder @user <word>
        Finds all messages from the specified user containing the specified word in the current channel.
        """
        messages = []
        async for message in ctx.channel.history(limit=None):
            if message.author == member and word.lower() in message.content.lower():
                messages.append(message)

        if messages:
            response = "\n".join([f"{msg.created_at}: {msg.content}" for msg in messages])
            await ctx.send(f"Messages from {member.mention} containing '{word}':\n{response}")
        else:
            await ctx.send(f"No messages from {member.mention} containing '{word}' found.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerManagerCog(bot))
