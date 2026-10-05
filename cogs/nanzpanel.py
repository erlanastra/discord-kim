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
    # LOAD PANEL DATA
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

        except (
            json.JSONDecodeError,
            OSError,
        ):

            return {}

    # ============================================================
    # SAVE PANEL DATA
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
    # ANNIVERSARY EMBED
    # ============================================================

    @classmethod
    def create_anniversary_embed(cls):

        embed = discord.Embed(
            title="🎉 nanZ Anniversary Awards 2026",
            description=(
                "**Agustus 2026** menjadi bulan spesial "
                "bagi nanZ.\n\n"
                "Berikut penghargaan untuk para pemenang "
                "dan penerima award Anniversary nanZ."
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
    # EVENT EMBED
    # ============================================================

    @classmethod
    def create_event_embed(cls):

        embed = discord.Embed(
            title="🏆 Event Winner",
            description=(
                "Role penghargaan khusus untuk "
                "para pemenang event nanZ."
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
            text="nanZ Server • Event Winner"
        )

        return embed

    # ============================================================
    # SPECIAL ROLE EMBED
    # ============================================================

    @classmethod
    def create_special_embed(cls):

        embed = discord.Embed(
            title="✦ Special Role",
            description=(
                "Role spesial yang tersedia di **nanZ Server**.\n\n"
                "Setiap role memiliki cara mendapatkan yang berbeda. "
                "Gunakan tombol di bawah untuk melihat panduan claim."
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
            text="nanZ Server • Special Role"
        )

        return embed

    # ============================================================
    # SPECIAL ROLE BUTTONS
    # ============================================================

    class SpecialView(discord.ui.View):

        def __init__(self):

            super().__init__(
                timeout=None
            )

            # ----------------------------------------------------
            # APIPI
            # ----------------------------------------------------

            self.add_item(
                discord.ui.Button(
                    label="Cara Dapat nZ Apipi",
                    style=discord.ButtonStyle.link,
                    url=(
                        "https://discord.com/channels/"
                        "1406557880475320340/"
                        "1555862444054814740"
                    ),
                )
            )

            # ----------------------------------------------------
            # VIP
            # ----------------------------------------------------

            self.add_item(
                discord.ui.Button(
                    label="Cara Dapat VIP",
                    style=discord.ButtonStyle.link,
                    url=(
                        "https://discord.com/channels/"
                        "1406557880475320340/"
                        "1550884157435936908"
                    ),
                )
            )

    # ============================================================
    # EMPTY PERSISTENT VIEW
    # ============================================================

    class EmptyView(discord.ui.View):

        def __init__(self):

            super().__init__(
                timeout=None
            )

    # ============================================================
    # GET PANEL CHANNEL
    # ============================================================

    async def get_panel_channel(self):

        channel = self.bot.get_channel(
            self.PANEL_CHANNEL_ID
        )

        if channel is not None:
            return channel

        try:

            channel = await self.bot.fetch_channel(
                self.PANEL_CHANNEL_ID
            )

            return channel

        except discord.NotFound:

            print(
                "[NanzPanel] Channel panel "
                "tidak ditemukan."
            )

        except discord.Forbidden:

            print(
                "[NanzPanel] Bot tidak memiliki "
                "akses ke channel panel."
            )

        except Exception as error:

            print(
                "[NanzPanel] Gagal mengambil "
                f"channel panel: {error}"
            )

        return None

    # ============================================================
    # SYNC ONE PANEL
    # ============================================================

    async def sync_single_panel(
        self,
        channel,
        data,
        key,
        embed,
        view,
        panel_name,
    ):

        message_id = data.get(key)

        # ========================================================
        # UPDATE EXISTING PANEL
        # ========================================================

        if message_id:

            try:

                message = await channel.fetch_message(
                    int(message_id)
                )

                await message.edit(
                    embed=embed,
                    view=view,
                )

                data[key] = str(message.id)

                print(
                    f"[NanzPanel] {panel_name} "
                    f"di-update "
                    f"(Message ID: {message.id})"
                )

                return message

            except discord.NotFound:

                print(
                    f"[NanzPanel] {panel_name} "
                    "tidak ditemukan. Membuat ulang."
                )

            except ValueError:

                print(
                    f"[NanzPanel] ID {panel_name} "
                    "tidak valid. Membuat ulang."
                )

            except discord.Forbidden:

                print(
                    f"[NanzPanel] Tidak memiliki izin "
                    f"mengedit {panel_name}."
                )

                return None

            except discord.HTTPException as error:

                print(
                    f"[NanzPanel] Gagal update "
                    f"{panel_name}: {error}"
                )

            except Exception as error:

                print(
                    f"[NanzPanel] Error update "
                    f"{panel_name}: {error}"
                )

        # ========================================================
        # CREATE PANEL
        # ========================================================

        try:

            message = await channel.send(
                embed=embed,
                view=view,
            )

            data[key] = str(message.id)

            print(
                f"[NanzPanel] {panel_name} "
                f"berhasil dibuat "
                f"(Message ID: {message.id})"
            )

            return message

        except discord.Forbidden:

            print(
                f"[NanzPanel] Tidak memiliki izin "
                f"mengirim {panel_name}."
            )

        except discord.HTTPException as error:

            print(
                f"[NanzPanel] Discord menolak "
                f"{panel_name}: {error}"
            )

        except Exception as error:

            print(
                f"[NanzPanel] Gagal membuat "
                f"{panel_name}: {error}"
            )

        return None

    # ============================================================
    # SYNC ALL PANELS
    #
    # URUTAN:
    # 1. ANNIVERSARY
    # 2. EVENT
    # 3. SPECIAL
    # ============================================================

    async def sync_panel(self):

        channel = await self.get_panel_channel()

        if channel is None:
            return

        if not isinstance(
            channel,
            discord.TextChannel,
        ):

            print(
                "[NanzPanel] Channel panel bukan "
                "TextChannel."
            )

            return

        # ========================================================
        # LOAD JSON
        # ========================================================

        data = self.load_panel_data()

        # ========================================================
        # 1. ANNIVERSARY
        # ========================================================

        await self.sync_single_panel(
            channel=channel,
            data=data,
            key="anniversary_message_id",
            embed=self.create_anniversary_embed(),
            view=self.EmptyView(),
            panel_name="Anniversary Panel",
        )

        # ========================================================
        # 2. EVENT WINNER
        # ========================================================

        await self.sync_single_panel(
            channel=channel,
            data=data,
            key="event_message_id",
            embed=self.create_event_embed(),
            view=self.EmptyView(),
            panel_name="Event Winner Panel",
        )

        # ========================================================
        # 3. SPECIAL ROLE
        # ========================================================

        await self.sync_single_panel(
            channel=channel,
            data=data,
            key="special_message_id",
            embed=self.create_special_embed(),
            view=self.SpecialView(),
            panel_name="Special Role Panel",
        )

        # ========================================================
        # SAVE DATA
        # ========================================================

        data["channel_id"] = str(
            self.PANEL_CHANNEL_ID
        )

        data["panel_order"] = [
            "anniversary",
            "event",
            "special",
        ]

        self.save_panel_data(
            data
        )

        print(
            "[NanzPanel] Semua panel berhasil "
            "disinkronkan."
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
                "[NanzPanel] Auto sync panel "
                "dibatalkan."
            )

            raise

        except Exception as error:

            print(
                "[NanzPanel] Gagal auto sync panel: "
                f"{error}"
            )

    # ============================================================
    # MANUAL SYNC COMMAND
    # ============================================================

    @commands.command(name="panel")
    @commands.cooldown(
        1,
        5,
        commands.BucketType.user,
    )
    @commands.has_permissions(
        manage_guild=True
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

        await self.sync_panel()

        await ctx.send(
            "✅ Semua panel nanZ berhasil "
            "disinkronkan.",
            delete_after=5,
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

        if isinstance(
            error,
            commands.MissingPermissions,
        ):

            return await ctx.send(
                "❌ Kamu tidak memiliki izin "
                "untuk menggunakan command ini.",
                delete_after=5,
            )

        print(
            f"[NanzPanel] Error command !panel: {error}"
        )


# =================================================================
# SETUP
# =================================================================

async def setup(bot):

    # =============================================================
    # HINDARI COG DUPLIKAT
    # =============================================================

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

    # =============================================================
    # BUAT COG
    # =============================================================

    cog = NanzPanel(bot)

    await bot.add_cog(
        cog
    )

    # =============================================================
    # REGISTER PERSISTENT VIEWS
    # =============================================================

    bot.add_view(
        NanzPanel.SpecialView()
    )

    bot.add_view(
        NanzPanel.EmptyView()
    )

    # =============================================================
    # HINDARI AUTO-SYNC TASK DUPLIKAT
    # =============================================================

    old_task = getattr(
        bot,
        "_nanz_panel_sync_task",
        None,
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

    # =============================================================
    # BUAT AUTO-SYNC TASK
    # =============================================================

    task = asyncio.create_task(
        cog.auto_sync_panel()
    )

    bot._nanz_panel_sync_task = task
    cog.sync_task = task

    # =============================================================
    # LOG
    # =============================================================

    print(
        "[NanzPanel] Cog berhasil dimuat."
    )

    print(
        "[NanzPanel] Urutan panel: "
        "Anniversary → Event → Special Role"
    )

    print(
        "[NanzPanel] Persistent buttons aktif."
    )