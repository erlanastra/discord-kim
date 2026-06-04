import discord
from discord.ext import commands, tasks
import asyncio

class Voice24(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.voice_channels = {}

        # Start checker
        self.stay_voice.start()

    # ================= COMMAND JOIN =================
    @commands.command(name="join")
    async def join_voice(self, ctx):

        # Cek user ada di vc atau tidak
        if not ctx.author.voice:

            embed = discord.Embed(
                title="❌ Gagal Join",
                description=(
                    "Kamu harus masuk voice channel dulu."
                ),
                color=0xED4245
            )

            return await ctx.send(
                embed=embed
            )

        channel = ctx.author.voice.channel

        try:

            vc = discord.utils.get(
                self.bot.voice_clients,
                guild=ctx.guild
            )

            # Kalau sudah connect
            if vc:

                await vc.move_to(channel)

            else:

                vc = await channel.connect()

            # Simpan vc tujuan
            self.voice_channels[
                ctx.guild.id
            ] = channel.id

            embed = discord.Embed(
                title="🎧 Voice Connected",
                description=(
                    f"Bot berhasil join ke "
                    f"{channel.mention}\n"
                    f">>> Mode 24/7 aktif"
                ),
                color=0x57F287
            )

            await ctx.send(embed=embed)

        except Exception as e:

            embed = discord.Embed(
                title="❌ Error",
                description=str(e),
                color=0xED4245
            )

            await ctx.send(embed=embed)

    # ================= COMMAND LEAVE =================
    @commands.command(name="leave")
    @commands.has_permissions(administrator=True)
    async def leave_voice(self, ctx):

        vc = discord.utils.get(
            self.bot.voice_clients,
            guild=ctx.guild
        )

        if not vc:

            return await ctx.send(
                "Bot tidak berada di voice."
            )

        # Hapus mode 24/7
        self.voice_channels.pop(
            ctx.guild.id,
            None
        )

        await vc.disconnect()

        embed = discord.Embed(
            title="👋 Voice Disconnected",
            description=(
                "Mode 24/7 dimatikan."
            ),
            color=0xED4245
        )

        await ctx.send(embed=embed)

    # ================= AUTO STAY =================
    @tasks.loop(seconds=20)
    async def stay_voice(self):

        await self.bot.wait_until_ready()

        for guild_id, channel_id in list(
            self.voice_channels.items()
        ):

            try:

                guild = self.bot.get_guild(
                    guild_id
                )

                if not guild:
                    continue

                channel = guild.get_channel(
                    channel_id
                )

                if not channel:
                    continue

                vc = discord.utils.get(
                    self.bot.voice_clients,
                    guild=guild
                )

                # Kalau disconnect auto reconnect
                if not vc or not vc.is_connected():

                    await channel.connect()

                    print(
                        f"Reconnected to {channel.name}"
                    )

                # Kalau pindah channel
                elif vc.channel.id != channel.id:

                    await vc.move_to(channel)

            except Exception as e:

                print(
                    f"Voice Stay Error: {e}"
                )

                await asyncio.sleep(5)

    # ================= AUTO RECONNECT =================
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):

        if member.id != self.bot.user.id:
            return

        # Kalau bot disconnect
        if before.channel and not after.channel:

            guild_id = before.channel.guild.id

            if guild_id in self.voice_channels:

                await asyncio.sleep(5)

                try:

                    channel = self.bot.get_channel(
                        self.voice_channels[guild_id]
                    )

                    if channel:

                        await channel.connect()

                        print(
                            "Auto reconnected"
                        )

                except Exception as e:

                    print(
                        f"Reconnect Error: {e}"
                    )

# ================= SETUP =================
async def setup(bot):

    await bot.add_cog(
        Voice24(bot)
    )