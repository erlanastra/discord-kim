import discord
from discord.ext import commands
import re


class ArcaneRank(commands.Cog):
    """
    Sistem Rank nanZ berdasarkan level Arcane.

    Arcane mengirim level-up message ke channel tertentu.
    NanZ membaca member + level dari message tersebut,
    lalu memberikan Rank sesuai rentang level.
    """

    # =========================================================
    # CONFIG
    # =========================================================

    ARCANE_LEVELUP_CHANNEL_ID = 1554778972313624618

    # =========================================================
    # ROLE RANK NANZ
    # =========================================================

    RANK_1_ROLE_ID = 1554785497497206835
    RANK_2_ROLE_ID = 1554785385073344622
    RANK_3_ROLE_ID = 1554785266089197650
    RANK_4_ROLE_ID = 1554785158735863889
    RANK_5_ROLE_ID = 1554784932084056104

    # Semua role rank yang dikelola oleh sistem
    RANK_ROLE_IDS = {
        RANK_1_ROLE_ID,
        RANK_2_ROLE_ID,
        RANK_3_ROLE_ID,
        RANK_4_ROLE_ID,
        RANK_5_ROLE_ID,
    }

    def __init__(self, bot):
        self.bot = bot

    # =========================================================
    # GET RANK ROLE BERDASARKAN LEVEL
    # =========================================================

    def get_rank_role_id(self, level: int):

        if 1 <= level <= 20:
            return self.RANK_5_ROLE_ID

        elif 21 <= level <= 40:
            return self.RANK_4_ROLE_ID

        elif 41 <= level <= 60:
            return self.RANK_3_ROLE_ID

        elif 61 <= level <= 80:
            return self.RANK_2_ROLE_ID

        elif 81 <= level <= 100:
            return self.RANK_1_ROLE_ID

        return None

    # =========================================================
    # EXTRACT LEVEL DARI MESSAGE ARCANE
    # =========================================================

    def extract_level(self, content: str):

        if not content:
            return None

        # Prioritas utama:
        # mencari pola seperti:
        # level **41**
        # level 41
        #
        # Case insensitive agar aman terhadap variasi huruf.
        match = re.search(
            r"\blevel\b\s*\*{0,2}\s*(\d+)",
            content,
            re.IGNORECASE
        )

        if match:
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None

        # Fallback:
        # Jika format Arcane sedikit berbeda tetapi tetap
        # mengandung kata "level" dan angka setelahnya.
        match = re.search(
            r"\blevel\b[^\d]{0,20}(\d+)",
            content,
            re.IGNORECASE
        )

        if match:
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None

        return None

    # =========================================================
    # FIND MEMBER DARI MENTION
    # =========================================================

    async def get_member_from_message(self, message: discord.Message):

        # Cara paling aman:
        # Arcane menggunakan {user.mention}
        if message.mentions:
            member = message.mentions[0]

            if isinstance(member, discord.Member):
                return member

        # Fallback jika mention tidak berhasil ter-resolve
        # tetapi message memiliki mention format <@USER_ID>
        match = re.search(
            r"<@!?(\d+)>",
            message.content or ""
        )

        if match:
            try:
                user_id = int(match.group(1))
            except ValueError:
                return None

            guild = message.guild

            if guild is None:
                return None

            member = guild.get_member(user_id)

            if member:
                return member

            try:
                return await guild.fetch_member(user_id)
            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):
                return None

        return None

    # =========================================================
    # ON MESSAGE
    # =========================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # =====================================================
        # HANYA CHANNEL ARCANE LEVEL-UP
        # =====================================================

        if message.channel.id != self.ARCANE_LEVELUP_CHANNEL_ID:
            return

        # Harus berasal dari guild
        if message.guild is None:
            return

        # =====================================================
        # CARI MEMBER
        # =====================================================

        member = await self.get_member_from_message(message)

        if member is None:
            print(
                "[ArcaneRank] Tidak dapat menemukan member "
                f"dari message {message.id}"
            )
            return

        # =====================================================
        # AMBIL LEVEL
        # =====================================================

        level = self.extract_level(message.content)

        if level is None:
            print(
                "[ArcaneRank] Tidak dapat membaca level "
                f"dari message {message.id}: {message.content!r}"
            )
            return

        # =====================================================
        # CEK RENTANG LEVEL
        # =====================================================

        rank_role_id = self.get_rank_role_id(level)

        # Level di luar sistem Rank nanZ
        if rank_role_id is None:
            print(
                f"[ArcaneRank] {member} mencapai level {level}, "
                "tetapi tidak ada Rank nanZ untuk level tersebut."
            )
            return

        # =====================================================
        # AMBIL ROLE RANK BARU
        # =====================================================

        new_role = message.guild.get_role(rank_role_id)

        if new_role is None:
            print(
                "[ArcaneRank] Role tidak ditemukan: "
                f"{rank_role_id}"
            )
            return

        # =====================================================
        # CEK APAKAH SUDAH MEMILIKI RANK YANG SESUAI
        # =====================================================

        if new_role in member.roles:

            print(
                f"[ArcaneRank] {member} sudah memiliki "
                f"{new_role.name} pada level {level}."
            )

            # Tetap bersihkan rank lain jika ada
            # untuk memastikan hanya satu Rank nanZ.
            other_rank_roles = [
                role
                for role in member.roles
                if role.id in self.RANK_ROLE_IDS
                and role.id != new_role.id
            ]

            if other_rank_roles:

                try:
                    await member.remove_roles(
                        *other_rank_roles,
                        reason=(
                            f"NanZ Arcane Rank cleanup "
                            f"(Level {level})"
                        )
                    )

                    print(
                        f"[ArcaneRank] Membersihkan "
                        f"{len(other_rank_roles)} role rank lama "
                        f"dari {member}."
                    )

                except discord.Forbidden:
                    print(
                        "[ArcaneRank] Tidak memiliki permission "
                        f"untuk membersihkan rank {member}."
                    )

                except discord.HTTPException as e:
                    print(
                        "[ArcaneRank] Gagal membersihkan "
                        f"rank {member}: {e}"
                    )

            return

        # =====================================================
        # CARI ROLE RANK LAMA
        # =====================================================

        old_rank_roles = [
            role
            for role in member.roles
            if role.id in self.RANK_ROLE_IDS
            and role.id != new_role.id
        ]

        # =====================================================
        # HAPUS RANK LAMA
        # =====================================================

        if old_rank_roles:

            try:
                await member.remove_roles(
                    *old_rank_roles,
                    reason=(
                        f"NanZ Arcane Rank update "
                        f"(Level {level})"
                    )
                )

            except discord.Forbidden:
                print(
                    "[ArcaneRank] Tidak memiliki permission "
                    f"untuk menghapus rank lama dari {member}."
                )
                return

            except discord.HTTPException as e:
                print(
                    "[ArcaneRank] Gagal menghapus rank lama "
                    f"dari {member}: {e}"
                )
                return

        # =====================================================
        # TAMBAHKAN RANK BARU
        # =====================================================

        try:

            await member.add_roles(
                new_role,
                reason=(
                    f"NanZ Arcane Rank "
                    f"(Level {level})"
                )
            )

            print(
                f"[ArcaneRank] {member} → "
                f"Level {level} → {new_role.name}"
            )

        except discord.Forbidden:
            print(
                "[ArcaneRank] Tidak memiliki permission "
                f"untuk memberikan {new_role.name} "
                f"kepada {member}."
            )

        except discord.HTTPException as e:
            print(
                "[ArcaneRank] Gagal memberikan "
                f"{new_role.name} kepada {member}: {e}"
            )

        except Exception as e:
            print(
                "[ArcaneRank] Error tidak terduga: "
                f"{e}"
            )


# =============================================================
# SETUP COG
# =============================================================

async def setup(bot):
    await bot.add_cog(ArcaneRank(bot))