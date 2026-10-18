from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands
from discord.ui import Modal, TextInput, View

from database import db


# ============================================================
# CONFIG
# ============================================================

MEMBER_PANEL_CHANNEL_ID = 1561291520185733180
MOD_LOG_CHANNEL_ID = 1513404867140390922
DATA_MEMBER_CHANNEL_ID = 1486981828798709930

# Same path used by autoreply.py
TOXIC_DB_PATH = "data/toxic_moderation.json"

# Keep the log scan bounded so the interaction doesn't run indefinitely.
MANUAL_WARN_LOG_SCAN_LIMIT = 5000
APPROVED_DATA_SCAN_LIMIT = 1500

# Staff roles used by the existing warn.py / verification setup.
STAFF_ROLE_IDS = {
    1555556260269527151,  # MOD
    1467360501745844446,  # PEMBINA
    1427276194876751902,  # OSIS
}

PANEL_MARKER = "nanz_member_control_panel_v1"
PANEL_CUSTOM_ID = "nanz_member_control:search"


def is_staff(member: discord.Member) -> bool:
    return (
        member.guild_permissions.administrator
        or any(role.id in STAFF_ROLE_IDS for role in getattr(member, "roles", []))
    )


def clip(value, limit: int = 900) -> str:
    text = str(value if value not in (None, "") else "Tidak tersedia")
    text = discord.utils.escape_markdown(text)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def field_value(embed: discord.Embed, field_name: str) -> Optional[str]:
    wanted = field_name.casefold().strip()
    for field in embed.fields:
        if field.name.casefold().strip() == wanted:
            return field.value
    return None


def extract_user_id(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"\b\d{15,22}\b", text)
    return int(match.group(0)) if match else None


def parse_member_data_embed(embed: discord.Embed, user_id: int) -> Optional[dict]:
    """Parse the existing 'Data Member Baru' embed without modifying it."""
    if (embed.title or "").casefold() != "data member baru":
        return None

    user_field = field_value(embed, "User") or ""
    if extract_user_id(user_field) != user_id:
        return None

    return {
        "nama": field_value(embed, "Nama"),
        "asal": field_value(embed, "Asal"),
        "umur": field_value(embed, "Umur"),
        "gender": field_value(embed, "Gender"),
        "medsos": field_value(embed, "Medsos"),
        "followers": field_value(embed, "Followers"),
        "profile_url": field_value(embed, "Profile"),
    }


class MemberSearchModal(Modal, title="Cari Member nanZ"):
    member_query = TextInput(
        label="Username, display name, atau ID Discord",
        placeholder="Contoh: kim atau 123456789012345678",
        min_length=2,
        max_length=100,
        required=True,
    )

    def __init__(self, cog: "MemberControl"):
        super().__init__(timeout=180)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "Kamu tidak memiliki izin untuk menggunakan Member Control.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True, thinking=True)
        query = self.member_query.value.strip()
        matches = self.cog.find_members(interaction.guild, query)

        if not matches:
            # For numeric IDs, still show DB records for members who have left.
            if query.isdigit() and 15 <= len(query) <= 22:
                try:
                    await self.cog.show_profile(interaction, int(query), None)
                    return
                except Exception as exc:
                    print(f"[MEMBER CONTROL] Gagal mencari ID {query}: {exc}")

            return await interaction.followup.send(
                "Member tidak ditemukan di cache server. Coba gunakan ID Discord "
                "jika member sudah keluar dari server.",
                ephemeral=True,
            )

        if len(matches) == 1:
            await self.cog.show_profile(interaction, matches[0].id, matches[0])
            return

        view = MemberChoiceView(self.cog, matches[:25])
        embed = discord.Embed(
            title="Hasil Pencarian Member",
            description=(
                f"Ditemukan **{len(matches)}** member yang cocok. "
                "Pilih member yang benar di menu berikut."
            ),
            color=0x5865F2,
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class MemberChoiceSelect(discord.ui.Select):
    def __init__(self, cog: "MemberControl", members: list[discord.Member]):
        self.cog = cog
        options = []
        for member in members[:25]:
            label = f"{member.display_name}"[:100]
            description = f"@{member.name} • ID {member.id}"[:100]
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(member.id),
                )
            )
        super().__init__(
            placeholder="Pilih member yang ingin dilihat",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="nanz_member_control:choose_result",
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "Kamu tidak memiliki izin.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = int(self.values[0])
        member = interaction.guild.get_member(user_id)
        await self.cog.show_profile(interaction, user_id, member)


class MemberChoiceView(View):
    def __init__(self, cog: "MemberControl", members: list[discord.Member]):
        super().__init__(timeout=180)
        self.add_item(MemberChoiceSelect(cog, members))


class MemberControlPanel(View):
    def __init__(self, cog: "MemberControl"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Cari Member",
        emoji="🔎",
        style=discord.ButtonStyle.primary,
        custom_id=PANEL_CUSTOM_ID,
    )
    async def search_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "Kamu tidak memiliki izin untuk menggunakan panel ini.",
                ephemeral=True,
            )
        await interaction.response.send_modal(MemberSearchModal(self.cog))


class MemberControl(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._panel_lock = __import__("asyncio").Lock()

    async def cog_load(self):
        # Persistent custom_id view; old panel remains usable after restart.
        self.bot.add_view(MemberControlPanel(self))
        print("[MEMBER CONTROL] Persistent panel view registered.")

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.ensure_panel()
        except Exception as exc:
            print(f"[MEMBER CONTROL] Gagal memastikan panel: {exc}")

    def find_members(self, guild: discord.Guild, query: str) -> list[discord.Member]:
        query_cf = query.casefold()
        if query.isdigit():
            exact_id = guild.get_member(int(query))
            if exact_id:
                return [exact_id]
            return []

        members = list(guild.members)
        exact = [
            m for m in members
            if m.name.casefold() == query_cf
            or m.display_name.casefold() == query_cf
            or str(m).casefold() == query_cf
        ]
        if exact:
            return sorted(exact, key=lambda m: (m.display_name.casefold(), m.id))

        partial = [
            m for m in members
            if query_cf in m.name.casefold()
            or query_cf in m.display_name.casefold()
            or query_cf in str(m).casefold()
        ]
        return sorted(partial, key=lambda m: (m.display_name.casefold(), m.id))

    async def ensure_panel(self):
        async with self._panel_lock:
            channel = self.bot.get_channel(MEMBER_PANEL_CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(MEMBER_PANEL_CHANNEL_ID)

            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                print("[MEMBER CONTROL] Channel panel bukan text channel.")
                return

            # Reuse an existing bot panel; don't send a duplicate on every restart.
            async for message in channel.history(limit=100):
                if message.author.id != self.bot.user.id:
                    continue
                if any(PANEL_MARKER in (embed.footer.text or "") for embed in message.embeds):
                    try:
                        await message.edit(view=MemberControlPanel(self))
                    except discord.HTTPException:
                        pass
                    return

            embed = discord.Embed(
                title="nanZ • Member Control",
                description=(
                    "Gunakan panel ini untuk mencari profil dan riwayat member.\n\n"
                    "• Cari dengan username, display name, atau ID Discord\n"
                    "• Lihat status verifikasi dan data yang tersimpan\n"
                    "• Periksa warning otomatis dan warn manual yang bisa ditemukan\n\n"
                    "Akses dibatasi untuk staff yang berwenang."
                ),
                color=0x5865F2,
            )
            embed.set_footer(text=PANEL_MARKER)
            await channel.send(embed=embed, view=MemberControlPanel(self))

    async def _get_verification_rows(self, guild_id: int, user_id: int) -> list[dict]:
        return await db.fetchall(
            """
            SELECT *
            FROM nanz_verification_applications
            WHERE guild_id=%s AND user_id=%s
            ORDER BY id DESC
            LIMIT 100
            """,
            guild_id,
            user_id,
        )

    async def _get_active_verification(self, guild_id: int, user_id: int):
        return await db.fetchone(
            """
            SELECT current_app_id, status, updated_at
            FROM nanz_verification_active
            WHERE guild_id=%s AND user_id=%s
            LIMIT 1
            """,
            guild_id,
            user_id,
        )

    def _read_toxic_record(self, guild_id: int, user_id: int) -> dict:
        try:
            with open(TOXIC_DB_PATH, "r", encoding="utf-8") as file:
                data = json.load(file)
            key = f"{guild_id}:{user_id}"
            return (data.get("members") or {}).get(key, {}) or {}
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[MEMBER CONTROL] Gagal membaca toxic JSON: {exc}")
            return {}

    async def _read_manual_warns(self, guild: discord.Guild, user_id: int) -> tuple[list[dict], bool]:
        """Read existing WARN LOG messages; history completeness depends on Discord logs."""
        channel = guild.get_channel(MOD_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(MOD_LOG_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return [], False

        results = []
        scanned = 0
        try:
            async for message in channel.history(
                limit=MANUAL_WARN_LOG_SCAN_LIMIT,
                oldest_first=False,
            ):
                scanned += 1
                for embed in message.embeds:
                    if (embed.title or "").casefold().strip() != "warn log":
                        continue
                    target_id = extract_user_id(field_value(embed, "TARGET MEMBER"))
                    if target_id != user_id:
                        continue
                    results.append({
                        "at": message.created_at,
                        "moderator": field_value(embed, "MODERATOR"),
                        "reason": field_value(embed, "REASON"),
                        "case": field_value(embed, "CASE"),
                    })
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[MEMBER CONTROL] Gagal membaca warn logs: {exc}")
            return results, False

        # False means older records may exist beyond this scan window.
        complete = scanned < MANUAL_WARN_LOG_SCAN_LIMIT
        return results, complete

    async def _read_approved_data(self, guild: discord.Guild, user_id: int) -> Optional[dict]:
        channel = guild.get_channel(DATA_MEMBER_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(DATA_MEMBER_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None

        try:
            async for message in channel.history(
                limit=APPROVED_DATA_SCAN_LIMIT,
                oldest_first=False,
            ):
                for embed in message.embeds:
                    data = parse_member_data_embed(embed, user_id)
                    if data:
                        data["_message_at"] = message.created_at
                        return data
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[MEMBER CONTROL] Gagal membaca data member lama: {exc}")
        return None

    async def show_profile(
        self,
        interaction: discord.Interaction,
        user_id: int,
        member: Optional[discord.Member],
    ):
        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send(
                "Fitur ini hanya dapat digunakan di server.", ephemeral=True
            )

        # Acknowledge the search first; this can involve multiple database/channel reads.
        try:
            verify_rows = await self._get_verification_rows(guild.id, user_id)
            active = await self._get_active_verification(guild.id, user_id)
        except Exception as exc:
            print(f"[MEMBER CONTROL] Query database gagal: {exc}")
            return await interaction.followup.send(
                "Database belum bisa dibaca. Pastikan koneksi `database.db` aktif "
                "dan tabel verifikasi sudah tersedia.",
                ephemeral=True,
            )

        user_obj = member
        if user_obj is None:
            try:
                user_obj = await self.bot.fetch_user(user_id)
            except (discord.NotFound, discord.HTTPException):
                user_obj = None

        toxic_record = self._read_toxic_record(guild.id, user_id)
        toxic_history = toxic_record.get("history") or []
        toxic_warnings = sum(1 for item in toxic_history if item.get("action") == "warning")
        toxic_timeouts = sum(1 for item in toxic_history if item.get("action") == "timeout")
        manual_warns, manual_complete = await self._read_manual_warns(guild, user_id)

        # Approved applications clear PII fields from SQL. Recover from the existing
        # approved-member archive channel if its original embed still exists.
        archived_data = None
        if verify_rows and not any(
            row.get("nama") or row.get("asal") or row.get("medsos")
            for row in verify_rows
        ):
            archived_data = await self._read_approved_data(guild, user_id)

        display_name = (
            member.display_name if member else
            (user_obj.name if user_obj else f"ID {user_id}")
        )
        username = (
            f"@{member.name}" if member else
            (f"@{user_obj.name}" if user_obj else "Tidak ditemukan")
        )

        embed = discord.Embed(
            title=f"Profil Member • {display_name}"[:256],
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        if member:
            embed.set_thumbnail(url=member.display_avatar.url)
        elif user_obj:
            embed.set_thumbnail(url=user_obj.display_avatar.url)
        embed.add_field(name="Username", value=clip(username, 200), inline=True)
        embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)
        embed.add_field(
            name="Status Server",
            value=("🟢 Masih di server" if member else "⚪ Tidak ada di server / sudah keluar"),
            inline=True,
        )

        if member:
            joined = discord.utils.format_dt(member.joined_at, style="F") if member.joined_at else "Tidak tersedia"
            role_names = [role.mention for role in member.roles if role.id != guild.id]
            roles_text = ", ".join(role_names) if role_names else "Tidak ada role"
            embed.add_field(name="Bergabung di Server", value=joined, inline=False)
            embed.add_field(name=f"Role Saat Ini ({len(role_names)})", value=clip(roles_text, 900), inline=False)

        # Verification status and history.
        current_status = active.get("status") if active else "BELUM ADA DATA"
        embed.add_field(
            name="Status Verifikasi Saat Ini",
            value=clip(current_status),
            inline=True,
        )
        embed.add_field(
            name="Jumlah Pengajuan Tersimpan",
            value=str(len(verify_rows)),
            inline=True,
        )

        if verify_rows:
            lines = []
            for row in verify_rows[:8]:
                status = row.get("status", "UNKNOWN")
                app_id = row.get("id", "?")
                created = row.get("created_at")
                date_text = created.strftime("%d-%m-%Y %H:%M") if hasattr(created, "strftime") else str(created or "tanggal tidak tersedia")
                lines.append(f"• `#{app_id}` — **{clip(status, 50)}** — {date_text}")
            embed.add_field(
                name="Riwayat Verifikasi (terbaru)",
                value=clip("\n".join(lines), 1000),
                inline=False,
            )

            row_with_data = next(
                (row for row in verify_rows if row.get("nama") or row.get("asal") or row.get("medsos")),
                None,
            )
            data = row_with_data or archived_data
            if data:
                embed.add_field(
                    name="Data Verifikasi",
                    value=clip(
                        f"**Nama:** {data.get('nama') or 'Tidak tersedia'}\n"
                        f"**Asal:** {data.get('asal') or 'Tidak tersedia'}\n"
                        f"**Umur:** {data.get('umur') or 'Tidak tersedia'}\n"
                        f"**Gender:** {data.get('gender') or 'Tidak tersedia'}\n"
                        f"**Medsos:** {data.get('medsos') or 'Tidak tersedia'}\n"
                        f"**Followers:** {data.get('followers') or 'Tidak tersedia'}\n"
                        f"**Link profil:** {data.get('profile_url') or 'Tidak tersedia'}",
                        1000,
                    ),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Data Verifikasi",
                    value=(
                        "Sebagian data pribadi tidak ditemukan di kolom database atau "
                        "arsip channel. Kode verifikasi lama mengosongkan beberapa kolom "
                        "setelah approve."
                    ),
                    inline=False,
                )
        else:
            embed.add_field(
                name="Riwayat Verifikasi",
                value="Tidak ditemukan pengajuan di tabel verifikasi yang ada.",
                inline=False,
            )

        # Moderation stats.
        toxic_active = toxic_record.get("warnings", 0)
        toxic_violations = toxic_record.get("violations", 0)
        embed.add_field(
            name="Warning Otomatis (riwayat lokal)",
            value=(
                f"**Warning tersimpan:** {toxic_warnings}\n"
                f"**Timeout tersimpan:** {toxic_timeouts}\n"
                f"**Warning aktif saat ini:** {toxic_active}\n"
                f"**Counter pelanggaran saat ini:** {toxic_violations}\n"
                f"**Entri history terbaca:** {len(toxic_history)}"
            ),
            inline=True,
        )

        manual_count_text = str(len(manual_warns))
        if not manual_complete:
            manual_count_text += " (minimal; scan log dibatasi)"
        embed.add_field(
            name="Warn Manual Staff",
            value=(
                f"**Warn ditemukan:** {manual_count_text}\n"
                + (
                    "\n".join(
                        f"• {item['at'].strftime('%d-%m-%Y')} — "
                        f"{clip(item.get('reason') or 'Alasan tidak tersedia', 120)}"
                        for item in manual_warns[:5]
                    )
                    if manual_warns else "Tidak ditemukan warn manual di log yang terbaca."
                )
            ),
            inline=True,
        )

        embed.set_footer(
            text=(
                "Data dibaca dari DB verifikasi, JSON toxic moderation, "
                "dan channel log yang sudah ada. Statistik dapat terbatas oleh retensi sumber."
            )
        )

        # Keep detailed data ephemeral so member personal information isn't exposed publicly.
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberControl(bot))