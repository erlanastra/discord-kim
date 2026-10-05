import asyncio
import json
import os

import discord
from discord.ext import commands


class NanzPanel(commands.Cog):

    # ============================================================
    # CONFIG
    # ============================================================

    SERVER_ID = 1406557880475320340
    PANEL_CHANNEL_ID = 1556578885225938985
    PANEL_DATA_FILE = "nanz_panel.json"

    # ============================================================
    # ROLE SPECIAL
    # ============================================================

    SPECIAL_ROLES = {
        "nZ Loyalist": {
            "role_id": 1555892286704062529,
            "description": (
                "Gunakan **Server Tag nZ** "
                "untuk mendapatkan role ini."
            ),
        },

        "nZ Apipi": {
            "role_id": 1555862680605167646,
            "description": (
                "Role khusus yang dapat diperoleh "
                "melalui sistem Apipi."
            ),
        },

        "VIP OwO": {
            "role_id": 1528766890296611017,
            "description": (
                "Role VIP yang diperoleh melalui "
                "**donasi OwO**."
            ),
        },

        "VIP Rupiah": {
            "role_id": 1528766033509220572,
            "description": (
                "Role VIP yang diperoleh melalui "
                "**donasi Rupiah**."
            ),
        },
    }

    # ============================================================
    # EVENT WINNER
    # ============================================================

    EVENT_ROLES = {
        "Riddle — Season 1": {
            "role_id": 1514600587772035124,
        },

        "Riddle — Season 2": {
            "role_id": 1517563935321227516,
        },

        "nanZ100 — Season 1": {
            "role_id": 1514922900132593745,
        },
    }

    # ============================================================
    # ANNIVERSARY
    # ============================================================

    ANNIVERSARY_ROLES = {
        "Winner Clip — Agustus 2026": {
            "role_id": 1538539964290170994,
        },

        "Winner Poster — Agustus 2026": {
            "role_id": 1538538863927099482,
        },

        "Winner Sambung Kata — Agustus 2026": {
            "role_id": 1538540210223059084,
        },

        "Winner Mole — Agustus 2026": {
            "role_id": 1538539398302539817,
        },

        "Winner FanArt — Agustus 2026": {
            "role_id": 1538539261865762866,
        },

        "nanZ Award — Most Voice 2026": {
            "role_id": 1538572694860210250,
        },

        "nanZ Award — Most Chatting 2026": {
            "role_id": 1538572820752367756,
        },

        "nanZ Award — Most Girls of the Girls 2026": {
            "role_id": 1538572966734995526,
        },

        "nanZ Award — Most Brain 2026": {
            "role_id": 1538573098016706570,
        },
    }

    # ============================================================
    # INIT
    # ============================================================

    def __init__(self, bot):
        self.bot = bot
        self.sync_task = None

    # ============================================================
    # PANEL DATA
    # ============================================================

    def load_panel_data(self):

        if not os.path.exists(self.PANEL_DATA_FILE):
            return {}

        try:
            with open(
                self.PANEL_DATA_FILE,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return {}

            return data

        except (json.JSONDecodeError, OSError):

            return {}

    # ============================================================

    def save_panel_data(self, data):

        try:
            temp_file = self.PANEL_DATA_FILE + ".tmp"

            with open(
                temp_file,
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    data,
                    file,
                    indent=4,
                    ensure_ascii=False,
                )

            os.replace(
                temp_file,
                self.PANEL_DATA_FILE,
            )

        except Exception as error:

            print(
                "[NanzPanel] Gagal menyimpan "
                f"data panel: {error}"
            )

    # ============================================================
    # CHANNEL URL
    # ============================================================

    @classmethod
    def channel_url(cls, channel_id):

        return (
            "https://discord.com/channels/"
            f"{cls.SERVER_ID}/{channel_id}"
        )

    # ============================================================
    # MAIN PANEL EMBED
    # ============================================================

    @staticmethod
    def create_panel_embed():

        embed = discord.Embed(
            title="✦ Role Special nanZ",
            description=(
                "Kumpulan **role spesial** yang tersedia "
                "di **nanZ Server**.\n\n"
                "Pilih kategori melalui menu di bawah "
                "untuk melihat informasi lengkap setiap role."
            ),
            color=0x5865F2,
        )

        embed.add_field(
            name="✦ Special Role",
            value=(
                "Role khusus yang dapat diperoleh "
                "melalui aktivitas atau kontribusi tertentu."
            ),
            inline=False,
        )

        embed.add_field(
            name="🏆 Event Winner",
            value=(
                "Role penghargaan khusus untuk "
                "para pemenang event nanZ."
            ),
            inline=False,
        )

        embed.add_field(
            name="🎉 nanZ Anniversary 2026",
            value=(
                "Kumpulan award spesial dalam rangka "
                "**Anniversary nanZ — Agustus 2026**."
            ),
            inline=False,
        )

        embed.set_footer(
            text="nanZ Server • Stay Solid!"
        )

        return embed

    # ============================================================
    # SPECIAL EMBED
    # ============================================================

    @classmethod
    def create_special_embed(cls):

        embed = discord.Embed(
            title="✦ Special Role",
            description=(
                "Role spesial yang dapat diperoleh "
                "oleh murid nanZ."
            ),
            color=0x5865F2,
        )

        for name, data in cls.SPECIAL_ROLES.items():

            role = f"<@&{data['role_id']}>"

            embed.add_field(
                name=f"◆ {name}",
                value=(
                    f"{role}\n"
                    f"{data['description']}"
                ),
                inline=False,
            )

        embed.set_footer(
            text="Pilih tombol di bawah untuk melihat panduan."
        )

        return embed

    # ============================================================
    # EVENT EMBED
    # ============================================================

    @classmethod
    def create_event_embed(cls):

        embed = discord.Embed(
            title="🏆 Role Pemenang Event",
            description=(
                "Role penghargaan khusus untuk "
                "pemenang event nanZ."
            ),
            color=0xFEE75C,
        )

        for name, data in cls.EVENT_ROLES.items():

            role = f"<@&{data['role_id']}>"

            embed.add_field(
                name=f"◆ {name}",
                value=role,
                inline=False,
            )

        embed.set_footer(
            text="Role diberikan kepada pemenang event."
        )

        return embed

    # ============================================================
    # ANNIVERSARY EMBED
    # ============================================================

    @classmethod
    def create_anniversary_embed(cls):

        embed = discord.Embed(
            title="🎉 nanZ Anniversary Awards 2026",
            description=(
                "**Agustus 2026** menjadi bulan spesial "
                "bagi nanZ.\n\n"
                "Berikut penghargaan untuk para "
                "pemenang dan penerima award Anniversary nanZ."
            ),
            color=0xED4245,
        )

        for name, data in cls.ANNIVERSARY_ROLES.items():

            role = f"<@&{data['role_id']}>"

            embed.add_field(
                name=f"◆ {name}",
                value=role,
                inline=False,
            )

        embed.set_footer(
            text="nanZ Anniversary 2026 • Stay Solid!"
        )

        return embed

    # ============================================================
    # MAIN PANEL VIEW
    # ============================================================

    class PanelView(discord.ui.View):

        def __init__(self, cog):

            super().__init__(
                timeout=None
            )

            self.cog = cog

            self.add_item(
                NanzPanel.CategorySelect(cog)
            )

    # ============================================================
    # CATEGORY SELECT
    # ============================================================

    class CategorySelect(discord.ui.Select):

        def __init__(self, cog):

            self.cog = cog

            # IMPORTANT:
            # Gunakan emoji Unicode standar.
            # Emoji seperti "✦" pada SelectOption sebelumnya
            # dapat ditolak Discord sebagai Invalid emoji.
            options = [

                discord.SelectOption(
                    label="Role Special",
                    description="Lihat role special nanZ",
                    emoji="⭐",
                    value="special",
                ),

                discord.SelectOption(
                    label="Event Winner",
                    description="Lihat role pemenang event",
                    emoji="🏆",
                    value="event",
                ),

                discord.SelectOption(
                    label="Anniversary 2026",
                    description="Lihat award Anniversary nanZ",
                    emoji="🎉",
                    value="anniversary",
                ),
            ]

            super().__init__(
                placeholder="Pilih kategori role...",
                options=options,
                custom_id="nanz_panel_category",
            )

        async def callback(
            self,
            interaction: discord.Interaction,
        ):

            value = self.values[0]

            if value == "special":

                embed = self.cog.create_special_embed()
                view = NanzPanel.SpecialView()

            elif value == "event":

                embed = self.cog.create_event_embed()
                view = NanzPanel.BackView()

            else:

                embed = self.cog.create_anniversary_embed()
                view = NanzPanel.BackView()

            await interaction.response.edit_message(
                embed=embed,
                view=view,
            )

    # ============================================================
    # SPECIAL VIEW
    # ============================================================

    class SpecialView(discord.ui.View):

        def __init__(self):

            super().__init__(
                timeout=None
            )

            self.add_item(
                discord.ui.Button(
                    label="Cara Dapat nZ Apipi",
                    emoji="⭐",
                    style=discord.ButtonStyle.link,
                    url=(
                        "https://discord.com/channels/"
                        "1406557880475320340/"
                        "1555862444054814740"
                    ),
                )
            )

            self.add_item(
                discord.ui.Button(
                    label="Cara Dapat VIP",
                    emoji="💎",
                    style=discord.ButtonStyle.link,
                    url=(
                        "https://discord.com/channels/"
                        "1406557880475320340/"
                        "1550884157435936908"
                    ),
                )
            )

            self.add_item(
                NanzPanel.BackButton()
            )

    # ============================================================
    # BACK VIEW
    # ============================================================

    class BackView(discord.ui.View):

        def __init__(self):

            super().__init__(
                timeout=None
            )

            self.add_item(
                NanzPanel.BackButton()
            )

    # ============================================================
    # BACK BUTTON
    # ============================================================

    class BackButton(discord.ui.Button):

        def __init__(self):

            super().__init__(
                label="Kembali",
                emoji="↩️",
                style=discord.ButtonStyle.secondary,
                custom_id="nanz_panel_back",
            )

        async def callback(
            self,
            interaction: discord.Interaction,
        ):

            cog = interaction.client.get_cog(
                "NanzPanel"
            )

            if cog is None:

                return await interaction.response.send_message(
                    "❌ Sistem panel sedang tidak tersedia.",
                    ephemeral=True,
                )

            embed = cog.create_panel_embed()
            view = NanzPanel.PanelView(cog)

            await interaction.response.edit_message(
                embed=embed,
                view=view,
            )

    # ============================================================
    # SYNC PANEL
    # ============================================================

    async def sync_panel(self):

        channel = self.bot.get_channel(
            self.PANEL_CHANNEL_ID
        )

        # --------------------------------------------------------
        # FALLBACK FETCH CHANNEL
        # --------------------------------------------------------

        if channel is None:

            try:

                channel = await self.bot.fetch_channel(
                    self.PANEL_CHANNEL_ID
                )

            except discord.NotFound:

                print(
                    "[NanzPanel] Channel panel tidak ditemukan."
                )

                return

            except discord.Forbidden:

                print(
                    "[NanzPanel] Bot tidak memiliki akses "
                    "ke channel panel."
                )

                return

            except Exception as error:

                print(
                    "[NanzPanel] Gagal mengambil channel: "
                    f"{error}"
                )

                return

        # --------------------------------------------------------
        # VALIDASI CHANNEL
        # --------------------------------------------------------

        if not isinstance(
            channel,
            (
                discord.TextChannel,
                discord.Thread,
            ),
        ):

            print(
                "[NanzPanel] Channel panel bukan "
                "TextChannel/Thread."
            )

            return

        # --------------------------------------------------------
        # SIAPKAN PANEL
        # --------------------------------------------------------

        embed = self.create_panel_embed()
        view = self.PanelView(self)

        data = self.load_panel_data()

        message_id = data.get(
            "panel_message_id"
        )

        # --------------------------------------------------------
        # UPDATE PANEL LAMA
        # --------------------------------------------------------

        if message_id:

            try:

                message = await channel.fetch_message(
                    int(message_id)
                )

                await message.edit(
                    embed=embed,
                    view=view,
                )

                self.save_panel_data({
                    "panel_message_id": str(message.id),
                    "channel_id": str(channel.id),
                })

                print(
                    "[NanzPanel] Panel berhasil di-update "
                    f"(Message ID: {message.id})"
                )

                return

            except discord.NotFound:

                print(
                    "[NanzPanel] Panel lama tidak ditemukan. "
                    "Membuat panel baru."
                )

            except discord.Forbidden:

                print(
                    "[NanzPanel] Bot tidak memiliki izin "
                    "untuk mengedit panel."
                )

                return

            except ValueError:

                print(
                    "[NanzPanel] Message ID pada JSON tidak valid. "
                    "Membuat panel baru."
                )

            except discord.HTTPException as error:

                print(
                    "[NanzPanel] Gagal update panel: "
                    f"{error}"
                )

                # Jangan langsung return.
                # Jika panel lama bermasalah, coba buat baru.

            except Exception as error:

                print(
                    "[NanzPanel] Error saat update panel: "
                    f"{error}"
                )

        # --------------------------------------------------------
        # BUAT PANEL BARU
        # --------------------------------------------------------

        try:

            message = await channel.send(
                embed=embed,
                view=view,
            )

            self.save_panel_data({
                "panel_message_id": str(message.id),
                "channel_id": str(channel.id),
            })

            print(
                "[NanzPanel] Panel baru berhasil dibuat "
                f"(Message ID: {message.id})"
            )

        except discord.Forbidden:

            print(
                "[NanzPanel] Bot tidak memiliki izin "
                "untuk mengirim pesan di channel panel."
            )

        except discord.HTTPException as error:

            print(
                "[NanzPanel] Discord menolak panel: "
                f"{error}"
            )

        except Exception as error:

            print(
                "[NanzPanel] Gagal mengirim panel: "
                f"{error}"
            )

    # ============================================================
    # AUTO SYNC
    # ============================================================

    async def auto_sync_panel(self):

        try:

            await self.bot.wait_until_ready()

            await asyncio.sleep(2)

            await self.sync_panel()

            print(
                "[NanzPanel] Auto sync panel "
                "berhasil dijalankan."
            )

        except asyncio.CancelledError:

            print(
                "[NanzPanel] Auto sync panel dibatalkan."
            )

            raise

        except Exception as error:

            print(
                "[NanzPanel] Gagal auto sync panel: "
                f"{error}"
            )

    # ============================================================
    # MANUAL COMMAND
    # ============================================================

    @commands.command(name="panel")
    @commands.cooldown(
        1,
        5,
        commands.BucketType.user,
    )
    async def panel(self, ctx):

        if ctx.guild is None:

            embed = discord.Embed(
                title="❌ Tidak Bisa Digunakan",
                description=(
                    "Command ini hanya bisa digunakan "
                    "di dalam server."
                ),
                color=0xED4245,
            )

            return await ctx.send(
                embed=embed
            )

        embed = self.create_panel_embed()
        view = self.PanelView(self)

        await ctx.send(
            embed=embed,
            view=view,
        )

    # ============================================================
    # COMMAND ERROR
    # ============================================================

    @panel.error
    async def panel_error(
        self,
        ctx,
        error,
    ):

        if isinstance(
            error,
            commands.CommandOnCooldown,
        ):
            return

        print(
            f"[NanzPanel] Error command !panel: {error}"
        )


# =================================================================
# SETUP
# =================================================================

async def setup(bot):

    # -------------------------------------------------------------
    # HINDARI COG DUPLIKAT
    # -------------------------------------------------------------

    old_cog = bot.get_cog(
        "NanzPanel"
    )

    if old_cog is not None:

        try:
            await bot.remove_cog(
                "NanzPanel"
            )

        except Exception:
            pass

    # -------------------------------------------------------------
    # BUAT COG
    # -------------------------------------------------------------

    cog = NanzPanel(bot)

    await bot.add_cog(cog)

    # -------------------------------------------------------------
    # REGISTER PERSISTENT VIEWS
    # -------------------------------------------------------------

    # Panel utama
    bot.add_view(
        NanzPanel.PanelView(cog)
    )

    # Halaman Special Role
    bot.add_view(
        NanzPanel.SpecialView()
    )

    # Halaman Event / Anniversary
    bot.add_view(
        NanzPanel.BackView()
    )

    # -------------------------------------------------------------
    # HINDARI AUTO-SYNC TASK DUPLIKAT
    # -------------------------------------------------------------

    old_task = getattr(
        bot,
        "_nanz_panel_sync_task",
        None
    )

    if old_task is not None:

        if not old_task.done():

            old_task.cancel()

            try:
                await old_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    # -------------------------------------------------------------
    # BUAT TASK BARU
    # -------------------------------------------------------------

    task = asyncio.create_task(
        cog.auto_sync_panel()
    )

    bot._nanz_panel_sync_task = task
    cog.sync_task = task

    # -------------------------------------------------------------
    # LOG
    # -------------------------------------------------------------

    print(
        "[NanzPanel] Cog berhasil dimuat. "
        "Auto sync panel dijadwalkan."
    )