import asyncio

import discord

from discord.ext import commands, tasks

from database import db

import uuid

import requests

import re





# =========================================================

# CONFIG

# =========================================================



VERIF_CHANNEL_ID = 1486913580161962054



# Channel khusus data verifikasi untuk Approve / Deny

DATA_VERIF_CHANNEL_ID = 1508683781698224241



# Channel engagement / divisi yang menangani verifikasi

ENGAGEMENT_CHANNEL_ID = 1555582479321272402



# Role engagement yang ditag pada setiap notif verifikasi

ENGAGEMENT_ROLE_ID = 1518252236134809681



# Channel penyimpanan data member setelah APPROVE

DATA_MEMBER_CHANNEL_ID = 1486981828798709930



# ROLE MEMBER

MEMBER_ROLE_ID = 1453095603008442510



# ROLE SISWA / SISWI

SISWA_ROLE_ID = 1453246082405503036

SISWI_ROLE_ID = 1453246187636396032



# ROLE UMUR

AGE_15_18_ROLE_ID = 1545088940413943829

AGE_19_22_ROLE_ID = 1545089256270078043

AGE_23_PLUS_ROLE_ID = 1545089354765049936



# ROLE NON VERIF

NONVERIF_ROLE_ID = 1504467138440597604



# Voice verifikasi nanZ

VOICE_VERIF_CHANNEL_IDS = [

    1518251174149750906,

    1523340570607616010,

    1486913650374738030,

]


# =========================================================
# VERIFICATION DATABASE LAYER (MariaDB nanZ yang sudah ada)
# =========================================================

VERIFY_TABLE = "nanz_verification_applications"
VERIFY_ACTIVE_TABLE = "nanz_verification_active"

async def setup_verification_database():
    """Membuat tabel yang diperlukan jika belum ada; tidak menghapus data lama."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_verification_applications (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            guild_id BIGINT UNSIGNED NOT NULL,
            user_id BIGINT UNSIGNED NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'MENGISI_DATA',
            claim_token VARCHAR(64) NULL,
            decision_token VARCHAR(64) NULL,
            decision_by BIGINT UNSIGNED NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            last_reminder_at DATETIME NULL,
            next_reminder_at DATETIME NULL,
            reminder_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
            reminder_blocked TINYINT(1) NOT NULL DEFAULT 0,
            reminder_claim VARCHAR(64) NULL,
            staff_message_id BIGINT UNSIGNED NULL,
            staff_channel_id BIGINT UNSIGNED NULL,
            voice_notice_claim VARCHAR(64) NULL,
            voice_notice_sent TINYINT(1) NOT NULL DEFAULT 0,
            voice_channel_id BIGINT UNSIGNED NULL,
            nama VARCHAR(100) NULL,
            asal VARCHAR(150) NULL,
            umur VARCHAR(16) NULL,
            gender VARCHAR(8) NULL,
            medsos VARCHAR(255) NULL,
            followers VARCHAR(80) NULL,
            profile_url VARCHAR(500) NULL,
            INDEX idx_verify_due (status, next_reminder_at, reminder_blocked),
            INDEX idx_verify_member (guild_id, user_id, id),
            UNIQUE KEY uq_verify_claim_token (claim_token)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_verification_active (
            guild_id BIGINT UNSIGNED NOT NULL,
            user_id BIGINT UNSIGNED NOT NULL,
            current_app_id BIGINT UNSIGNED NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'IDLE',
            claim_token VARCHAR(64) NULL,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id),
            INDEX idx_verify_active_status (status, updated_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    # MariaDB-safe additive migration for installations that ran an earlier draft.
    await db.execute("ALTER TABLE nanz_verification_applications ADD COLUMN IF NOT EXISTS reminder_claim VARCHAR(64) NULL")
    # Older versions stopped reminders after three total messages. Resume those
    # pending applications under the new recurring schedule (about every 8 hours).
    await db.execute("""
        UPDATE nanz_verification_applications
        SET reminder_blocked=0, reminder_count=0,
            next_reminder_at=DATE_ADD(NOW(), INTERVAL 8 HOUR)
        WHERE status IN ('MENUNGGU_VOICE','MENUNGGU_STAFF')
          AND reminder_blocked=1 AND reminder_count >= 3
    """)

    # Recover claims abandoned by a crash before an application row was created.
    await db.execute("""
        UPDATE nanz_verification_active
        SET status='FAILED', claim_token=NULL
        WHERE status='PROCESSING'
          AND current_app_id IS NULL
          AND updated_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE)
    """)
    # Recover a staff decision interrupted by a process restart. Role operations are
    # idempotent, so a retried approval safely verifies the final role state again.
    await db.execute("""
        UPDATE nanz_verification_applications
        SET status='MENUNGGU_STAFF', decision_token=NULL
        WHERE status='APPROVING'
          AND updated_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE)
    """)
    await db.execute("""
        UPDATE nanz_verification_active a
        JOIN nanz_verification_applications v ON v.id=a.current_app_id
        SET a.status='MENUNGGU_STAFF'
        WHERE v.status='MENUNGGU_STAFF' AND a.status NOT IN ('DISETUJUI','DENIED')
    """)
    # A denial was already claimed before the process stopped; finalize it rather than
    # reopening an application that staff explicitly rejected.
    await db.execute("""
        UPDATE nanz_verification_applications
        SET status='DITOLAK', decision_token=NULL, reminder_blocked=1, next_reminder_at=NULL
        WHERE status='DENYING'
          AND updated_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE)
    """)
    await db.execute("""
        UPDATE nanz_verification_active a
        JOIN nanz_verification_applications v ON v.id=a.current_app_id
        SET a.status='DENIED', a.claim_token=NULL
        WHERE v.status='DITOLAK'
    """)

async def claim_new_application(guild_id: int, user_id: int):
    """
    Izinkan member mengajukan ulang kapan saja.
    Hanya pengiriman yang sedang berjalan yang mengunci submit bersamaan.
    Pengajuan lama yang belum selesai ditandai KEDALUWARSA, bukan dihapus.
    """
    await db.execute(
        "INSERT IGNORE INTO nanz_verification_active (guild_id,user_id,status) VALUES (%s,%s,'IDLE')",
        guild_id, user_id
    )
    token = uuid.uuid4().hex
    # Status PROCESSING hanya dipakai sebagai lock sementara untuk submit bersamaan.
    await db.execute("""
        UPDATE nanz_verification_active
        SET status='PROCESSING', claim_token=%s, current_app_id=NULL
        WHERE guild_id=%s AND user_id=%s AND status <> 'PROCESSING'
    """, token, guild_id, user_id)
    row = await db.fetchone(
        "SELECT status, claim_token FROM nanz_verification_active WHERE guild_id=%s AND user_id=%s LIMIT 1",
        guild_id, user_id
    )
    if not row or row.get("claim_token") != token or row.get("status") != "PROCESSING":
        return None

    # Pengajuan pending sebelumnya menjadi kedaluwarsa. Riwayat tetap tersimpan,
    # reminder dihentikan, dan tombol lama tidak bisa mengambil keputusan lagi.
    await db.execute("""
        UPDATE nanz_verification_applications
        SET status='KEDALUWARSA', reminder_blocked=1,
            next_reminder_at=NULL, reminder_claim=NULL,
            decision_token=NULL
        WHERE guild_id=%s AND user_id=%s
          AND status IN ('MENGISI_DATA','MENUNGGU_VOICE','MENUNGGU_STAFF',
                         'APPROVING','DENYING','APPROVAL_FAILED','NOTIFICATION_FAILED')
    """, guild_id, user_id)
    return token

async def create_application(guild_id, user_id, token, nama, asal, umur, gender, medsos, followers, link):
    await db.execute("""
        INSERT INTO nanz_verification_applications
        (guild_id,user_id,status,claim_token,next_reminder_at,reminder_count,reminder_blocked,
         nama,asal,umur,gender,medsos,followers,profile_url)
        VALUES (%s,%s,'MENUNGGU_VOICE',%s,DATE_ADD(NOW(), INTERVAL 8 HOUR),0,0,%s,%s,%s,%s,%s,%s,%s)
    """, guild_id, user_id, token, nama, asal, umur, gender, medsos, followers, link)
    row = await db.fetchone(
        "SELECT id FROM nanz_verification_applications WHERE claim_token=%s LIMIT 1", token
    )
    if not row:
        raise RuntimeError('Application row tidak ditemukan setelah INSERT')
    app_id = int(row['id'])
    await db.execute("""
        UPDATE nanz_verification_active
        SET current_app_id=%s,status='MENUNGGU_VOICE',claim_token=NULL
        WHERE guild_id=%s AND user_id=%s AND claim_token=%s
    """, app_id, guild_id, user_id, token)
    return app_id

async def fail_submission(guild_id, user_id, token, app_id=None):
    try:
        if app_id:
            await db.execute("UPDATE nanz_verification_applications SET status='NOTIFICATION_FAILED', reminder_blocked=1 WHERE id=%s AND status='MENUNGGU_VOICE'", app_id)
        await db.execute("""
            UPDATE nanz_verification_active SET status='NOTIFICATION_FAILED',claim_token=NULL
            WHERE guild_id=%s AND user_id=%s AND (claim_token=%s OR current_app_id=%s)
        """, guild_id, user_id, token, app_id or 0)
    except Exception as exc:
        print(f"[VERIFY][DB] Gagal menandai submission gagal token={token}: {exc}")

async def resolve_application(interaction, app_id, user_id):
    """Cocokkan tombol dengan pesan dan pengajuan yang tepat, termasuk pesan lama."""
    if interaction.channel_id != DATA_VERIF_CHANNEL_ID:
        return None
    guild_id = interaction.guild.id
    if app_id:
        row = await db.fetchone(
            "SELECT * FROM nanz_verification_applications WHERE id=%s AND guild_id=%s AND user_id=%s LIMIT 1",
            int(app_id), guild_id, int(user_id)
        )
        if not row:
            return None
        msg_id = row.get('staff_message_id')
        if msg_id and int(msg_id) != int(interaction.message.id):
            return None
        return row
    # Legacy messages without application ID are allowed only if their exact message ID
    # is mapped to the currently active application. Otherwise fail closed (stale buttons).
    active = await db.fetchone(
        "SELECT current_app_id FROM nanz_verification_active WHERE guild_id=%s AND user_id=%s LIMIT 1",
        guild_id, int(user_id)
    )
    if not active or not active.get('current_app_id'):
        return None
    row = await db.fetchone(
        "SELECT * FROM nanz_verification_applications WHERE id=%s AND staff_message_id=%s LIMIT 1",
        int(active['current_app_id']), int(interaction.message.id)
    )
    return row

async def claim_decision(interaction, app_row, decision_status):
    token = uuid.uuid4().hex
    await db.execute("""
        UPDATE nanz_verification_applications
        SET status=%s,decision_token=%s,decision_by=%s
        WHERE id=%s AND guild_id=%s AND user_id=%s
          AND status IN ('MENUNGGU_VOICE','MENUNGGU_STAFF','APPROVAL_FAILED')
    """, decision_status, token, interaction.user.id, app_row['id'], interaction.guild.id, app_row['user_id'])
    row = await db.fetchone(
        "SELECT status,decision_token FROM nanz_verification_applications WHERE id=%s LIMIT 1",
        app_row['id']
    )
    return bool(row and row.get('status') == decision_status and row.get('decision_token') == token), token

async def release_approval_for_retry(app_id, guild_id, user_id, token):
    await db.execute("""
        UPDATE nanz_verification_applications SET status='MENUNGGU_STAFF',decision_token=NULL
        WHERE id=%s AND status='APPROVING' AND decision_token=%s
    """, app_id, token)
    await db.execute("""
        UPDATE nanz_verification_active SET status='MENUNGGU_STAFF'
        WHERE guild_id=%s AND user_id=%s AND current_app_id=%s
    """, guild_id, user_id, app_id)

async def finalize_approval(app_id, guild_id, user_id, token):
    await db.execute("""
        UPDATE nanz_verification_applications
        SET status='DISETUJUI',decision_token=NULL,reminder_blocked=1,next_reminder_at=NULL,
            nama=NULL,asal=NULL,umur=NULL,gender=NULL,medsos=NULL,followers=NULL,profile_url=NULL
        WHERE id=%s AND status='APPROVING' AND decision_token=%s
    """, app_id, token)
    row = await db.fetchone("SELECT status FROM nanz_verification_applications WHERE id=%s LIMIT 1", app_id)
    if not row or row.get('status') != 'DISETUJUI':
        raise RuntimeError(f"Status aplikasi {app_id} gagal disimpan sebagai DISETUJUI")
    await db.execute("""
        UPDATE nanz_verification_active SET status='DISETUJUI',claim_token=NULL
        WHERE guild_id=%s AND user_id=%s AND current_app_id=%s
    """, guild_id, user_id, app_id)

async def finalize_denial(app_id, guild_id, user_id, token):
    await db.execute("""
        UPDATE nanz_verification_applications
        SET status='DITOLAK',decision_token=NULL,reminder_blocked=1,next_reminder_at=NULL,decision_token=NULL
        WHERE id=%s AND status='DENYING' AND decision_token=%s
    """, app_id, token)
    row = await db.fetchone("SELECT status FROM nanz_verification_applications WHERE id=%s LIMIT 1", app_id)
    if not row or row.get('status') != 'DITOLAK':
        raise RuntimeError(f"Status aplikasi {app_id} gagal disimpan sebagai DITOLAK")
    await db.execute("""
        UPDATE nanz_verification_active SET status='DENIED',claim_token=NULL
        WHERE guild_id=%s AND user_id=%s AND current_app_id=%s
    """, guild_id, user_id, app_id)

async def mark_voice_arrival(bot, member, target):
    active = await db.fetchone(
        "SELECT current_app_id,status FROM nanz_verification_active WHERE guild_id=%s AND user_id=%s LIMIT 1",
        member.guild.id, member.id
    )
    if not active or not active.get('current_app_id') or active.get('status') not in ('MENUNGGU_VOICE','MENUNGGU_STAFF'):
        return
    app_id = int(active['current_app_id'])
    token = uuid.uuid4().hex
    await db.execute("""
        UPDATE nanz_verification_applications
        SET voice_notice_claim=%s,voice_channel_id=%s,status='MENUNGGU_STAFF',
            next_reminder_at=DATE_ADD(NOW(), INTERVAL 8 HOUR)
        WHERE id=%s AND status IN ('MENUNGGU_VOICE','MENUNGGU_STAFF') AND voice_notice_claim IS NULL
    """, token, target.id, app_id)
    row = await db.fetchone(
        "SELECT voice_notice_claim,voice_notice_sent FROM nanz_verification_applications WHERE id=%s LIMIT 1", app_id
    )
    if not row or row.get('voice_notice_claim') != token or row.get('voice_notice_sent'):
        return
    channel = bot.get_channel(ENGAGEMENT_CHANNEL_ID)
    if channel is None:
        # Do not leave voice_notice_claim permanently locked if the channel is
        # unavailable during startup/cache warm-up; a later voice event can retry.
        await db.execute(
            "UPDATE nanz_verification_applications "
            "SET voice_notice_claim=NULL WHERE id=%s AND voice_notice_claim=%s AND voice_notice_sent=0",
            app_id, token
        )
        print(f"[VERIFY][app={app_id}][MENUNGGU_STAFF] Engagement channel tidak ditemukan; claim dilepas untuk retry")
        return
    embed = discord.Embed(
        title='Member Menunggu Verifikasi Voice',
        description=f'{NANZ_ARROW_BLUE} {member.mention} sudah masuk ke **{target.name}**.\n{NANZ_ARROW_PURPLE} Staff dapat masuk ke voice tersebut untuk melakukan konfirmasi data.',
        color=0x5865F2,
    )
    embed.add_field(name='Member', value=f'{member.mention}\n`{member.id}`', inline=True)
    embed.add_field(name='Voice Verifikasi', value=f'<#{target.id}>', inline=True)
    embed.add_field(name='Application ID', value=str(app_id), inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    try:
        await channel.send(
            content=f'<@&{ENGAGEMENT_ROLE_ID}>', embed=embed,
            view=StaffVoiceNoticeView(member.guild.id, target.id),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )
        await db.execute("UPDATE nanz_verification_applications SET voice_notice_sent=1 WHERE id=%s AND voice_notice_claim=%s", app_id, token)
    except Exception as exc:
        # Release only this attempt's claim so the next valid voice event can retry.
        # If Discord accepted the message but the DB write failed, a duplicate is
        # possible; this is preferable to permanently losing the staff notification.
        try:
            await db.execute(
                "UPDATE nanz_verification_applications "
                "SET voice_notice_claim=NULL WHERE id=%s AND voice_notice_claim=%s AND voice_notice_sent=0",
                app_id, token
            )
        except Exception as release_exc:
            print(f"[VERIFY][app={app_id}][MENUNGGU_STAFF] Gagal melepas claim voice notice: {release_exc}")
        print(f"[VERIFY][app={app_id}][MENUNGGU_STAFF] Gagal kirim voice notice: {exc}")




# Emoji custom nanZ

NANZ_ARROW_BLUE = "<a:arrowblue:1512787254312042496>"

NANZ_ARROW_PURPLE = "<a:arrowpurple:1512787191234035803>"

NANZ_LINK = "<a:link:1553688245769085099>"

NANZ_GEAR = "<a:settings:1553688352564183051>"

NANZ_QUESTION = "<a:question:1553688505929044000>"





# =========================================================

# SAFE INTERACTION HELPERS

# =========================================================



async def safe_followup(

    interaction: discord.Interaction,

    content=None,

    *,

    embed=None,

    embeds=None,

    view=None,

    ephemeral=False,

):

    """

    Mengirim followup dengan aman.



    Jika interaction sudah expired / Unknown interaction,

    error ditangani agar tidak menghasilkan traceback besar.

    """



    try:

        return await interaction.followup.send(

            content=content,

            embed=embed,

            embeds=embeds,

            view=view,

            ephemeral=ephemeral,

        )



    except discord.NotFound as e:

        if getattr(e, "code", None) == 10062:

            print(

                "[VERIFY] Interaction sudah expired "

                "saat mengirim followup."

            )

            return None



        print(

            f"[VERIFY] Followup NotFound: {e}"

        )

        return None



    except discord.HTTPException as e:

        print(

            f"[VERIFY] Gagal mengirim followup: {e}"

        )

        return None



    except Exception as e:

        print(

            f"[VERIFY] Error followup: {e}"

        )

        return None





async def safe_defer(

    interaction: discord.Interaction,

    *,

    ephemeral=True,

):

    """

    Memberikan acknowledgement ke Discord secepat mungkin.



    Return:

        True  = berhasil defer

        False = interaction sudah tidak valid

    """



    try:



        if interaction.response.is_done():

            return True



        await interaction.response.defer(

            ephemeral=ephemeral

        )



        return True



    except discord.NotFound as e:



        if getattr(e, "code", None) == 10062:

            print(

                "[VERIFY] Interaction sudah expired "

                "sebelum defer."

            )

            return False



        print(

            f"[VERIFY] Interaction NotFound saat defer: {e}"

        )

        return False



    except discord.HTTPException as e:



        print(

            f"[VERIFY] HTTP error saat defer: {e}"

        )

        return False



    except Exception as e:



        print(

            f"[VERIFY] Error saat defer: {e}"

        )

        return False





async def safe_response_send(

    interaction: discord.Interaction,

    content=None,

    *,

    embed=None,

    view=None,

    ephemeral=False,

):

    """

    Response pertama jika interaction belum di-response.

    Jika sudah di-response/defer, otomatis menggunakan followup.

    """



    try:



        if interaction.response.is_done():



            return await safe_followup(

                interaction,

                content=content,

                embed=embed,

                view=view,

                ephemeral=ephemeral,

            )



        return await interaction.response.send_message(

            content=content,

            embed=embed,

            view=view,

            ephemeral=ephemeral,

        )



    except discord.NotFound as e:



        if getattr(e, "code", None) == 10062:



            print(

                "[VERIFY] Interaction expired "

                "saat mengirim response."

            )



            return None



        print(

            f"[VERIFY] Response NotFound: {e}"

        )

        return None



    except discord.HTTPException as e:



        print(

            f"[VERIFY] HTTP error response: {e}"

        )

        return None



    except Exception as e:



        print(

            f"[VERIFY] Error response: {e}"

        )

        return None





# =========================================================

# GENERAL HELPERS

# =========================================================



def channel_url(

    guild_id: int,

    channel_id: int

) -> str:



    return (

        f"https://discord.com/channels/"

        f"{guild_id}/{channel_id}"

    )





def get_instagram_followers(username):



    try:



        url = (

            f"https://www.instagram.com/"

            f"{username}/"

        )



        headers = {

            "User-Agent": "Mozilla/5.0"

        }



        res = requests.get(

            url,

            headers=headers,

            timeout=10

        )



        if res.status_code != 200:

            return "Tidak ditemukan"



        match = re.search(

            r'"edge_followed_by":{"count":(\d+)}',

            res.text,

        )



        if match:

            return (

                f"{int(match.group(1)):,}"

            )



        return "Hidden"



    except Exception:



        return "Error"





def get_tiktok_followers(username):



    try:



        url = (

            f"https://www.tiktok.com/"

            f"@{username}"

        )



        headers = {

            "User-Agent": "Mozilla/5.0"

        }



        res = requests.get(

            url,

            headers=headers,

            timeout=10

        )



        if res.status_code != 200:

            return "Tidak ditemukan"



        match = re.search(

            r'"followerCount":(\d+)',

            res.text

        )



        if match:

            return (

                f"{int(match.group(1)):,}"

            )



        return "Hidden"



    except Exception:



        return "Error"





async def get_social_followers(

    platform,

    username

):

    """

    Jalankan request blocking di executor

    supaya event loop Discord tidak ikut terblokir.



    Python 3.8 compatible.

    """



    loop = asyncio.get_running_loop()



    if platform == "IG":



        return await loop.run_in_executor(

            None,

            get_instagram_followers,

            username

        )



    if platform == "TikTok":



        return await loop.run_in_executor(

            None,

            get_tiktok_followers,

            username

        )



    return "Tidak dicek"





def get_verif_voice_channels(guild):



    channels = []



    for channel_id in VOICE_VERIF_CHANNEL_IDS:



        channel = guild.get_channel(

            channel_id

        )



        if isinstance(

            channel,

            (

                discord.VoiceChannel,

                discord.StageChannel,

            ),

        ):

            channels.append(channel)



    return channels





def choose_verif_voice(

    guild,

    member

):

    """

    Prioritas:

    - voice yang tidak ditempati member lain

    - kalau semua berisi, kembali ke voice pertama

    """



    channels = get_verif_voice_channels(

        guild

    )



    if not channels:

        return None



    for channel in channels:



        others = [

            m

            for m in channel.members

            if m.id != member.id

        ]



        if not others:

            return channel



    return channels[0]





# =========================================================

# VOICE JOIN VIEW

# =========================================================



class VoiceJoinLinkView(discord.ui.View):



    def __init__(

        self,

        guild_id,

        channel_id,

        timeout=None

    ):



        super().__init__(

            timeout=timeout

        )



        self.add_item(

            discord.ui.Button(

                label="Join Voice Verif",

                style=discord.ButtonStyle.link,

                url=channel_url(

                    guild_id,

                    channel_id

                ),

            )

        )





# =========================================================

# STAFF VOICE NOTICE

# =========================================================



class StaffVoiceNoticeView(

    discord.ui.View

):



    def __init__(

        self,

        guild_id,

        channel_id

    ):



        super().__init__(

            timeout=None

        )



        self.add_item(

            discord.ui.Button(

                label="Masuk Voice",

                style=discord.ButtonStyle.link,

                url=channel_url(

                    guild_id,

                    channel_id

                ),

            )

        )





# =========================================================

# MEMBER VOICE HANDLER

# =========================================================



async def send_voice_notice(

    interaction,

    target

):



    guild = interaction.guild

    member = interaction.user



    engagement = interaction.client.get_channel(

        ENGAGEMENT_CHANNEL_ID

    )



    if not engagement:

        print(

            "[VERIFY] Engagement channel "

            "tidak ditemukan."

        )

        return



    embed = discord.Embed(

        title="Member Menunggu Verifikasi Voice",

        description=(

            f"{NANZ_ARROW_BLUE} "

            f"{member.mention} sudah masuk ke "

            f"**{target.name}**.\n"

            f"{NANZ_ARROW_PURPLE} Staff dapat masuk "

            f"ke voice tersebut untuk melakukan "

            f"konfirmasi data."

        ),

        color=0x5865F2,

    )



    embed.add_field(

        name="Member",

        value=(

            f"{member.mention}\n"

            f"`{member.id}`"

        ),

        inline=True,

    )



    embed.add_field(

        name="Voice Verifikasi",

        value=f"<#{target.id}>",

        inline=True,

    )



    embed.set_thumbnail(

        url=member.display_avatar.url

    )



    try:



        await engagement.send(

            content=(

                f"<@&{ENGAGEMENT_ROLE_ID}>"

            ),

            embed=embed,

            view=StaffVoiceNoticeView(

                guild.id,

                target.id,

            ),

            allowed_mentions=discord.AllowedMentions(

                users=True,

                roles=True,

            ),

        )



    except discord.HTTPException as e:



        print(

            f"[VERIFY] Gagal mengirim "

            f"voice notice: {e}"

        )





async def handle_voice_verif(

    interaction

):



    # =====================================================

    # ACKNOWLEDGE SECEPAT MUNGKIN

    # =====================================================



    if not await safe_defer(

        interaction,

        ephemeral=True

    ):

        return



    guild = interaction.guild

    member = interaction.user



    if (

        guild is None

        or not isinstance(

            member,

            discord.Member

        )

    ):



        await safe_followup(

            interaction,

            (

                "Fitur ini hanya dapat digunakan "

                "di dalam server."

            ),

            ephemeral=True,

        )

        return



    target = choose_verif_voice(

        guild,

        member

    )



    if target is None:



        await safe_followup(

            interaction,

            (

                "Voice verifikasi tidak ditemukan. "

                "Hubungi staff."

            ),

            ephemeral=True,

        )

        return



    # =====================================================
    # MEMBER SUDAH ADA DI VOICE
    # =====================================================

    current_voice = getattr(member, "voice", None)
    current_channel = getattr(current_voice, "channel", None)
    if current_channel is not None:
        # If already in a verification room, do not move them to another
        # room (or try to move them to the same room). Explicitly reconcile
        # the application state in case the original voice event happened
        # before the application was created or was otherwise missed.
        if current_channel.id in VOICE_VERIF_CHANNEL_IDS:
            try:
                await mark_voice_arrival(
                    interaction.client,
                    member,
                    current_channel,
                )
            except Exception as exc:
                print(
                    f"[VERIFY][user={member.id}][MENUNGGU_STAFF] "
                    f"Re-check voice dari tombol gagal: {exc}"
                )
            await safe_followup(
                interaction,
                (
                    f"{NANZ_ARROW_BLUE} Kamu sudah berada di "
                    f"**{current_channel.name}**. Jika pengajuanmu sudah terkirim, "
                    "staff akan mendapat notifikasi dan melakukan konfirmasi."
                ),
                ephemeral=True,
            )
            return

        try:
            await member.move_to(
                target,
                reason="nanZ Verification Voice",
            )
        except discord.Forbidden:
            await safe_followup(
                interaction,
                "Bot tidak memiliki izin untuk memindahkan kamu ke voice verifikasi.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            print(f"[VERIFY][user={member.id}] move voice gagal: {exc}")
            await safe_followup(
                interaction,
                "Gagal memindahkan kamu ke voice verifikasi. Coba lagi.",
                ephemeral=True,
            )
            return

        # The voice-state event will usually handle this too. Calling it here
        # covers delayed/missed events; its DB claim prevents duplicate notices.
        try:
            await mark_voice_arrival(interaction.client, member, target)
        except Exception as exc:
            print(
                f"[VERIFY][user={member.id}][MENUNGGU_STAFF] "
                f"Re-check voice setelah dipindahkan gagal: {exc}"
            )

        await safe_followup(
            interaction,
            (
                f"{NANZ_ARROW_BLUE} Kamu sudah diarahkan ke **{target.name}**. "
                "Silakan tunggu staff melakukan konfirmasi data."
            ),
            ephemeral=True,
        )
        return

    # =====================================================

    # MEMBER BELUM BERADA DI VOICE

    # =====================================================



    view = VoiceJoinLinkView(

        guild.id,

        target.id,

    )



    await safe_followup(

        interaction,

        (

            f"{NANZ_ARROW_BLUE} "

            "Kamu belum berada di voice.\n"

            f"Klik tombol **Join Voice Verif** "

            f"di bawah untuk masuk ke "

            f"**{target.name}**."

        ),

        view=view,

        ephemeral=True,

    )





# =========================================================

# VERIFY MODAL

# =========================================================



class VerifyModal(

    discord.ui.Modal,

    title="Form Verifikasi",

):



    nama = discord.ui.TextInput(

        label="Nama",

        placeholder=(

            "Nama yang ingin digunakan di server"

        ),

        max_length=50,

    )



    asal = discord.ui.TextInput(

        label="Asal",

        placeholder="Kota / daerah asal",

        max_length=100,

    )



    username = discord.ui.TextInput(

        label="Username Medsos",

        placeholder="username atau @username",

        max_length=100,

    )



    def __init__(

        self,

        bot,

        platform,

        umur,

        gender,

    ):



        super().__init__()



        self.bot = bot

        self.platform = platform

        self.umur = umur

        self.gender = gender



    async def on_submit(

        self,

        interaction: discord.Interaction,

    ):



        # =====================================================

        # ACKNOWLEDGE SECEPAT MUNGKIN

        # =====================================================



        if not await safe_defer(

            interaction,

            ephemeral=True

        ):

            return



        # =====================================================

        # VALIDASI USERNAME

        # =====================================================



        raw_username = self.username.value.strip()
        # Simpan username tanpa @ agar format input @username dan username sama-sama valid.
        # @ hanya diperlakukan sebagai awalan; username akhir disimpan dalam format konsisten.
        username_clean = raw_username.lstrip("@").strip()

        if not username_clean or not re.fullmatch(r'[A-Za-z0-9._]{1,30}', username_clean):



            await safe_followup(

                interaction,

                (

                    f"{NANZ_QUESTION} "

                    "Username tidak valid. Gunakan huruf, angka, titik, atau garis bawah."

                ),

                ephemeral=True,

            )

            return



        guild = interaction.guild
        if guild is None:
            await safe_followup(interaction, "Form verifikasi hanya bisa dikirim di dalam server.", ephemeral=True)
            return

        try:
            claim_token = await claim_new_application(guild.id, interaction.user.id)
        except Exception as exc:
            print(f"[VERIFY][user={interaction.user.id}][MENGISI_DATA] Database gagal saat claim: {exc}")
            await safe_followup(interaction, "Database verifikasi sedang bermasalah. Data belum dikirim; coba lagi nanti.", ephemeral=True)
            return

        if not claim_token:
            await safe_followup(
                interaction,
                "Kamu sudah memiliki pengajuan verifikasi yang sedang diproses atau sudah disetujui. Jangan kirim ulang. Jika pengajuanmu ditolak, kamu bisa mengisi kembali.",
                ephemeral=True,
            )
            return

        app_id = None

        medsos_final = (

            f"{self.platform} | "

            f"@{username_clean}"

        )



        followers = "Tidak dicek"

        link = ""



        # =====================================================

        # CEK FOLLOWERS

        # =====================================================



        if self.platform == "IG":



            followers = (

                await get_social_followers(

                    "IG",

                    username_clean

                )

            )



            link = (

                "https://instagram.com/"

                f"{username_clean}"

            )



        elif self.platform == "TikTok":



            followers = (

                await get_social_followers(

                    "TikTok",

                    username_clean

                )

            )



            link = (

                "https://tiktok.com/@"

                f"{username_clean}"

            )



        # =====================================================

        # DATA LENGKAP + APPROVE/DENY

        # =====================================================



        verif_channel = (

            interaction.client.get_channel(

                DATA_VERIF_CHANNEL_ID

            )

        )



        if verif_channel:



            embed = discord.Embed(

                title="Data Verifikasi Baru",

                description=(

                    f"{NANZ_ARROW_BLUE} "

                    f"{interaction.user.mention} "

                    "telah mengirim data verifikasi.\n"

                    f"{NANZ_GEAR} Silakan lakukan "

                    "**Approve** atau **Deny** "

                    "setelah melakukan konfirmasi."

                ),

                color=0x5865F2,

            )



            embed.add_field(

                name="Member",

                value=(

                    f"{interaction.user.mention}\n"

                    f"`{interaction.user.id}`"

                ),

                inline=False,

            )



            embed.add_field(

                name="Nama",

                value=self.nama.value,

                inline=True,

            )



            embed.add_field(

                name="Asal",

                value=self.asal.value,

                inline=True,

            )



            embed.add_field(

                name="Umur",

                value=self.umur,

                inline=True,

            )



            embed.add_field(

                name="Gender",

                value=(

                    "Siswa"

                    if self.gender == "L"

                    else "Siswi"

                ),

                inline=True,

            )



            embed.add_field(

                name="Medsos",

                value=medsos_final,

                inline=False,

            )



            embed.add_field(

                name="Followers",

                value=followers,

                inline=True,

            )



            if link:



                embed.add_field(

                    name="Profile",

                    value=(

                        f"{NANZ_LINK} "

                        f"[Buka Profile]({link})"

                    ),

                    inline=False,

                )



            embed.set_thumbnail(

                url=interaction.user.display_avatar.url

            )



            try:
                app_id = await create_application(
                    guild.id, interaction.user.id, claim_token,
                    self.nama.value.strip(), self.asal.value.strip(), self.umur,
                    self.gender, medsos_final, followers, link
                )
            except Exception as exc:
                print(f"[VERIFY][user={interaction.user.id}][MENGISI_DATA] Gagal menyimpan pengajuan ke DB: {exc}")
                await fail_submission(guild.id, interaction.user.id, claim_token)
                await safe_followup(interaction, "Data belum berhasil disimpan. Silakan coba lagi beberapa saat lagi.", ephemeral=True)
                return

            embed.add_field(name="Application ID", value=str(app_id), inline=True)

            view = VerifyView(

                self.bot,

                interaction.user.id,

                self.nama.value,

                self.asal.value,

                self.umur,

                self.gender,

                medsos_final,

                followers,

                link,

                app_id,

            )



            try:
                staff_message = await verif_channel.send(
                    content=(
                        "**Verifikasi baru:** "
                        f"{interaction.user.mention}"
                    ),
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            except Exception as e:
                print(f"[VERIFY][app={app_id}][MENUNGGU_VOICE] Gagal mengirim data verifikasi ke staff: {e}")
                await fail_submission(guild.id, interaction.user.id, claim_token, app_id)
                await safe_followup(interaction, "Data tersimpan, tetapi notifikasi staff gagal dikirim. Hubungi staff atau coba lagi nanti.", ephemeral=True)
                return

            # If Discord accepted the message but the DB update fails, keep the application
            # pending. The embedded Application ID still allows safe processing without
            # staff_message_id, and we avoid inviting a duplicate submission.
            try:
                await db.execute(
                    "UPDATE nanz_verification_applications SET staff_message_id=%s,staff_channel_id=%s WHERE id=%s",
                    staff_message.id, verif_channel.id, app_id
                )
            except Exception as e:
                print(f"[VERIFY][app={app_id}][MENUNGGU_VOICE] Pesan staff terkirim tetapi message ID gagal disimpan: {e}")



        else:
            print(f"[VERIFY][user={interaction.user.id}][MENGISI_DATA] DATA_VERIF_CHANNEL tidak ditemukan.")
            await fail_submission(guild.id, interaction.user.id, claim_token, app_id)
            await safe_followup(interaction, "Channel verifikasi staff tidak ditemukan. Hubungi admin.", ephemeral=True)
            return

        # =====================================================
        # RECONCILE VOICE STATE AFTER APPLICATION CREATION
        # =====================================================
        # The member may have joined a verification voice channel before
        # submitting this form. In that case on_voice_state_update already
        # fired while no pending application existed, so it could not notify
        # staff. Re-check the member's current voice state now that the
        # application and staff message exist. mark_voice_arrival uses a DB
        # claim token, so this is safe if the voice event runs at the same time.
        current_voice = getattr(interaction.user, "voice", None)
        current_channel = getattr(current_voice, "channel", None)
        if current_channel and current_channel.id in VOICE_VERIF_CHANNEL_IDS:
            try:
                await mark_voice_arrival(
                    self.bot,
                    interaction.user,
                    current_channel,
                )
            except Exception as exc:
                print(
                    f"[VERIFY][user={interaction.user.id}][MENUNGGU_STAFF] "
                    f"Re-check voice setelah submit gagal: {exc}"
                )

        # =====================================================

        # NOTIF ENGAGEMENT

        # =====================================================



        engagement = (

            interaction.client.get_channel(

                ENGAGEMENT_CHANNEL_ID

            )

        )



        if engagement:



            notice = discord.Embed(

                title="Member Mengisi Data Verifikasi",

                description=(

                    f"{NANZ_ARROW_BLUE} "

                    f"{interaction.user.mention} "

                    "telah mengirim data verifikasi.\n"

                    f"{NANZ_GEAR} Data lengkap dan tombol "

                    "**Approve/Deny** ada di "

                    f"<#{DATA_VERIF_CHANNEL_ID}>."

                ),

                color=0x5865F2,

            )



            notice.add_field(

                name="Member",

                value=(

                    f"{interaction.user.mention}\n"

                    f"`{interaction.user.id}`"

                ),

                inline=False,

            )



            notice.set_thumbnail(

                url=interaction.user.display_avatar.url

            )



            try:



                await engagement.send(

                    content=(

                        f"<@&{ENGAGEMENT_ROLE_ID}>"

                    ),

                    embed=notice,

                    allowed_mentions=discord.AllowedMentions(

                        users=True,

                        roles=True,

                    ),

                )



            except discord.HTTPException as e:



                print(

                    f"[VERIFY] Gagal mengirim "

                    f"engagement notice: {e}"

                )



        # =====================================================

        # RESPONSE KE MEMBER

        # =====================================================



        view = VoiceVerifyButtonView(

            self.bot

        )



        await safe_followup(

            interaction,

            (

                "✅ **Data verifikasi berhasil dikirim!**\n\n"

                "Langkah berikutnya wajib dilakukan:\n"

                "1. Tekan tombol **Join Voice Verif** di bawah.\n"

                "2. Masuk ke voice yang diarahkan dan tunggu staff.\n"

                "3. Staff akan mengonfirmasi data kamu sebelum menyetujui verifikasi.\n\n"

                "Pengajuanmu tetap tercatat selama menunggu. Jangan submit ulang; bot akan mengingatkan lewat DM "
                "setiap sekitar 8 jam (maksimal 3 kali sehari) sampai pengajuan diproses."

            ),

            view=view,

            ephemeral=True,

        )





# =========================================================

# SELECT PLATFORM

# =========================================================



class PlatformSelect(

    discord.ui.Select

):



    def __init__(self):



        options = [



            discord.SelectOption(

                label="Instagram",

                value="IG",

            ),



            discord.SelectOption(

                label="TikTok",

                value="TikTok",

            ),



        ]



        super().__init__(

            placeholder="Pilih platform medsos",

            options=options,

            custom_id="verify_platform_select",

        )



    async def callback(

        self,

        interaction: discord.Interaction,

    ):



        self.view.set_selection(interaction.user.id, "platform", self.values[0])



        await safe_response_send(

            interaction,

            (

                f"Platform dipilih: "

                f"**{self.values[0]}**."

            ),

            ephemeral=True,

        )





# =========================================================

# SELECT UMUR

# =========================================================



class AgeSelect(

    discord.ui.Select

):



    def __init__(self):



        options = [



            discord.SelectOption(

                label="15–18 Tahun",

                value="15-18",

            ),



            discord.SelectOption(

                label="19–22 Tahun",

                value="19-22",

            ),



            discord.SelectOption(

                label="23+ Tahun",

                value="23+",

            ),



        ]



        super().__init__(

            placeholder="Pilih rentang umur",

            options=options,

            custom_id="verify_age_select",

        )



    async def callback(

        self,

        interaction: discord.Interaction,

    ):



        self.view.set_selection(interaction.user.id, "umur", self.values[0])



        await safe_response_send(

            interaction,

            (

                f"Rentang umur dipilih: "

                f"**{self.values[0]}**."

            ),

            ephemeral=True,

        )





# =========================================================

# SELECT GENDER

# =========================================================



class GenderSelect(

    discord.ui.Select

):



    def __init__(self):



        options = [



            discord.SelectOption(

                label="Siswa",

                value="L",

                description=(

                    "Pilih jika kamu laki-laki"

                ),

            ),



            discord.SelectOption(

                label="Siswi",

                value="P",

                description=(

                    "Pilih jika kamu perempuan"

                ),

            ),



        ]



        super().__init__(

            placeholder="Pilih gender",

            options=options,

            custom_id="verify_gender_select",

        )



    async def callback(

        self,

        interaction: discord.Interaction,

    ):



        self.view.set_selection(interaction.user.id, "gender", self.values[0])



        await safe_response_send(

            interaction,

            (

                "Gender berhasil dipilih."

            ),

            ephemeral=True,

        )





# =========================================================

# VERIFY DATA PANEL

# =========================================================



class VerifyButton(

    discord.ui.View

):



    def __init__(self, bot):



        super().__init__(

            timeout=None

        )



        self.bot = bot

        # Pilihan per pengguna agar panel bersama tidak mencampur data member.
        self.selections = {}

        self.add_item(

            PlatformSelect()

        )



        self.add_item(

            AgeSelect()

        )



        self.add_item(

            GenderSelect()

        )



    def set_selection(self, user_id, key, value):
        self.selections.setdefault(int(user_id), {})[key] = value

    def get_user_selection(self, user_id):
        return self.selections.get(int(user_id), {})

    @discord.ui.button(

        label="Lanjut Isi Data",

        style=discord.ButtonStyle.primary,

        custom_id="verify_continue_button",

    )

    async def lanjut(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button,

    ):



        selections = self.get_user_selection(interaction.user.id)

        if not selections.get("platform"):



            await safe_response_send(

                interaction,

                (

                    "Pilih platform medsos "

                    "terlebih dahulu."

                ),

                ephemeral=True,

            )

            return



        if not selections.get("umur"):



            await safe_response_send(

                interaction,

                (

                    "Pilih rentang umur "

                    "terlebih dahulu."

                ),

                ephemeral=True,

            )

            return



        if not selections.get("gender"):



            await safe_response_send(

                interaction,

                (

                    "Pilih gender "

                    "terlebih dahulu."

                ),

                ephemeral=True,

            )

            return



        try:



            await interaction.response.send_modal(

                VerifyModal(

                    self.bot,

                    selections["platform"],

                    selections["umur"],

                    selections["gender"],

                )

            )



        except discord.NotFound as e:



            if getattr(e, "code", None) == 10062:



                print(

                    "[VERIFY] Interaction expired "

                    "saat membuka modal."

                )



            else:



                print(

                    f"[VERIFY] Error membuka modal: {e}"

                )



        except discord.HTTPException as e:



            print(

                f"[VERIFY] HTTP error membuka modal: {e}"

            )





# =========================================================

# BUTTON VOICE SETELAH DATA TERKIRIM

# =========================================================



class VoiceVerifyButtonView(

    discord.ui.View

):



    def __init__(self, bot):



        super().__init__(

            timeout=None

        )



        self.bot = bot



    @discord.ui.button(

        label="Join Voice Verif",

        style=discord.ButtonStyle.primary,

        custom_id="verify_join_voice_after_submit",

    )

    async def join_voice(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button,

    ):



        await handle_voice_verif(

            interaction

        )





# =========================================================

# APPROVE / DENY

# =========================================================



class VerifyView(

    discord.ui.View

):



    def __init__(

        self,

        bot,

        user_id=None,

        nama=None,

        asal=None,

        umur=None,

        gender=None,

        medsos=None,

        followers=None,

        link=None,
        application_id=None,

    ):



        super().__init__(

            timeout=None

        )



        self.bot = bot



        self.user_id = user_id

        self.nama = nama

        self.asal = asal

        self.umur = umur

        self.gender = gender

        self.medsos = medsos

        self.followers = followers

        self.link = link
        self.application_id = application_id



    # =====================================================

    # LOAD DATA DARI EMBED

    # =====================================================



    def _load_from_message(

        self,

        message

    ):



        if (

            not message

            or not message.embeds

        ):

            return False



        try:



            fields = message.embeds[

                0

            ].fields



            values = {

                field.name.strip().lower():

                    field.value.strip()

                for field in fields

            }



        except Exception as e:



            print(

                f"[VERIFY] Gagal membaca "

                f"field embed: {e}"

            )



            return False



        app_value = values.get("application id", "").strip()
        self.application_id = int(app_value) if app_value.isdigit() else self.application_id

        member_value = values.get(

            "member",

            ""

        )



        match = (

            re.search(

                r"`(\d+)`",

                member_value

            )

            or

            re.search(

                r"<@!?([0-9]+)>",

                member_value

            )

        )



        if not match:

            return False



        self.user_id = match.group(1)



        self.nama = values.get(

            "nama",

            ""

        )



        self.asal = values.get(

            "asal",

            ""

        )



        self.umur = values.get(

            "umur",

            ""

        )



        self.medsos = values.get(

            "medsos",

            ""

        )



        self.followers = values.get(

            "followers",

            ""

        )



        profile = values.get(

            "profile",

            ""

        )



        # Support markdown:

        # [Buka Profile]\(https://...)

        pm = re.search(

            r"\((https?://[^)]+)\)",

            profile

        )



        if pm:



            self.link = pm.group(1)



        else:



            if profile == "Tidak tersedia":



                self.link = ""



            else:



                self.link = profile



        gender_value = values.get(

            "gender",

            ""

        ).lower()



        if "siswi" in gender_value:



            self.gender = "P"



        elif "siswa" in gender_value:



            self.gender = "L"



        else:



            self.gender = values.get(

                "gender",

                ""

            )



        return True



    # =====================================================

    # APPROVE

    # =====================================================



    @discord.ui.button(

        label="Approve",

        style=discord.ButtonStyle.success,

        custom_id="verify_approve_button",

    )

    async def approve(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button,

    ):



        # =================================================

        # DEFER SEBELUM PROSES APA PUN

        # =================================================



        if not await safe_defer(

            interaction,

            ephemeral=True

        ):

            return



        # =================================================

        # VALIDASI GUILD

        # =================================================



        if interaction.guild is None:



            await safe_followup(

                interaction,

                (

                    "Verifikasi hanya dapat "

                    "diproses di dalam server."

                ),

                ephemeral=True,

            )

            return



        # =================================================

        # LOAD DATA

        # =================================================



        if not self._load_from_message(

            interaction.message

        ):



            await safe_followup(

                interaction,

                (

                    "Data verifikasi pada pesan "

                    "ini tidak dapat dibaca."

                ),

                ephemeral=True,

            )

            return



        # =================================================

        # CEK DATA USER ID

        # =================================================



        try:



            target_user_id = int(

                self.user_id

            )



        except (

            ValueError,

            TypeError

        ):



            await safe_followup(

                interaction,

                (

                    "ID member pada data "

                    "verifikasi tidak valid."

                ),

                ephemeral=True,

            )

            return



        # Validasi staff: role engagement atau izin moderasi/admin.
        staff_member = interaction.user
        staff_roles = getattr(staff_member, "roles", [])
        is_staff = (
            getattr(getattr(staff_member, "guild_permissions", None), "administrator", False)
            or getattr(getattr(staff_member, "guild_permissions", None), "manage_messages", False)
            or any(role.id == ENGAGEMENT_ROLE_ID for role in staff_roles)
        )
        if not is_staff:
            await safe_followup(interaction, "Kamu tidak memiliki izin untuk memproses verifikasi ini.", ephemeral=True)
            return

        try:
            app_row = await resolve_application(interaction, self.application_id, target_user_id)
        except Exception as exc:
            print(f"[VERIFY][user={target_user_id}][DB] Gagal memvalidasi aplikasi: {exc}")
            await safe_followup(interaction, "Database verifikasi gagal diakses. Keputusan belum diproses.", ephemeral=True)
            return
        if not app_row:
            await safe_followup(interaction, "Pengajuan ini tidak cocok dengan pengajuan aktif atau merupakan tombol lama. Tidak ada perubahan yang dilakukan.", ephemeral=True)
            return

        claimed, decision_token = await claim_decision(interaction, app_row, "APPROVING")
        if not claimed:
            await safe_followup(interaction, "Pengajuan ini sudah diproses staff lain atau statusnya sudah berubah.", ephemeral=True)
            return

        # =================================================

        # AMBIL MEMBER

        # =================================================



        member = (

            interaction.guild.get_member(

                target_user_id

            )

        )



        # Kalau tidak ada di cache, coba fetch

        if member is None:



            try:



                member = (

                    await interaction.guild.fetch_member(

                        target_user_id

                    )

                )



            except (

                discord.NotFound,

                discord.HTTPException

            ):



                member = None



        if member is None:
            await release_approval_for_retry(app_row['id'], interaction.guild.id, target_user_id, decision_token)
            await safe_followup(interaction, "Member tidak ditemukan di server. Status belum disetujui; coba periksa kembali.", ephemeral=True)
            return

        # =================================================

        # AMBIL ROLE

        # =================================================



        guild = interaction.guild



        member_role = guild.get_role(

            MEMBER_ROLE_ID

        )



        siswa_role = guild.get_role(

            SISWA_ROLE_ID

        )



        siswi_role = guild.get_role(

            SISWI_ROLE_ID

        )



        age_15_18_role = guild.get_role(

            AGE_15_18_ROLE_ID

        )



        age_19_22_role = guild.get_role(

            AGE_19_22_ROLE_ID

        )



        age_23_plus_role = guild.get_role(

            AGE_23_PLUS_ROLE_ID

        )



        nonverif_role = guild.get_role(

            NONVERIF_ROLE_ID

        )



        selected_age_role_check = {
            "15-18": age_15_18_role,
            "19-22": age_19_22_role,
            "23+": age_23_plus_role,
        }.get(self.umur)
        selected_gender_role_check = siswa_role if self.gender == "L" else siswi_role if self.gender == "P" else None
        if not member_role or not selected_age_role_check or not selected_gender_role_check:
            await release_approval_for_retry(app_row['id'], interaction.guild.id, target_user_id, decision_token)
            await safe_followup(interaction, "Role wajib untuk verifikasi tidak ditemukan. Periksa ID role di cogs/verifysystem.py; status belum disetujui.", ephemeral=True)
            return

        # =================================================

        # PROSES ROLE

        # =================================================



        if member:



            roles_to_add = []



            # -------------------------------------------------

            # MEMBER ROLE

            # -------------------------------------------------



            if (

                member_role

                and member_role not in member.roles

            ):



                roles_to_add.append(

                    member_role

                )



            # -------------------------------------------------

            # GENDER

            # -------------------------------------------------



            if self.gender == "L":



                if (

                    siswa_role

                    and siswa_role not in member.roles

                ):



                    roles_to_add.append(

                        siswa_role

                    )



                # Hapus Siswi jika ada

                if (

                    siswi_role

                    and siswi_role in member.roles

                ):



                    try:



                        await member.remove_roles(

                            siswi_role,

                            reason=(

                                "nanZ Verification "

                                "Gender Update"

                            ),

                        )



                    except discord.HTTPException as e:



                        print(

                            "[VERIFY] Gagal menghapus "

                            f"role Siswi: {e}"

                        )



            elif self.gender == "P":



                if (

                    siswi_role

                    and siswi_role not in member.roles

                ):



                    roles_to_add.append(

                        siswi_role

                    )



                # Hapus Siswa jika ada

                if (

                    siswa_role

                    and siswa_role in member.roles

                ):



                    try:



                        await member.remove_roles(

                            siswa_role,

                            reason=(

                                "nanZ Verification "

                                "Gender Update"

                            ),

                        )



                    except discord.HTTPException as e:



                        print(

                            "[VERIFY] Gagal menghapus "

                            f"role Siswa: {e}"

                        )



            # -------------------------------------------------

            # UMUR

            # -------------------------------------------------



            age_roles = {

                "15-18": age_15_18_role,

                "19-22": age_19_22_role,

                "23+": age_23_plus_role,

            }



            selected_age_role = age_roles.get(

                self.umur

            )



            if (

                selected_age_role

                and selected_age_role not in member.roles

            ):



                roles_to_add.append(

                    selected_age_role

                )



            # Hapus role umur lain

            roles_to_remove = []



            for role in [

                age_15_18_role,

                age_19_22_role,

                age_23_plus_role,

            ]:



                if (

                    role

                    and role != selected_age_role

                    and role in member.roles

                ):



                    roles_to_remove.append(

                        role

                    )



            if roles_to_remove:



                try:



                    await member.remove_roles(

                        *roles_to_remove,

                        reason=(

                            "nanZ Verification "

                            "Age Update"

                        ),

                    )



                except discord.HTTPException as e:



                    print(

                        "[VERIFY] Gagal menghapus "

                        f"role umur lama: {e}"

                    )



            # -------------------------------------------------

            # TAMBAHKAN ROLE

            # -------------------------------------------------



            if roles_to_add:



                try:



                    await member.add_roles(

                        *roles_to_add,

                        reason=(

                            "nanZ Verification Approved"

                        ),

                    )



                except discord.Forbidden:



                    print(

                        "[VERIFY] Bot tidak memiliki "

                        "izin untuk memberikan role."

                    )



                except discord.HTTPException as e:



                    print(

                        "[VERIFY] Gagal memberikan "

                        f"role: {e}"

                    )



            # -------------------------------------------------

            # HAPUS NON VERIF

            # -------------------------------------------------



            if (

                nonverif_role

                and nonverif_role in member.roles

            ):



                try:



                    await member.remove_roles(

                        nonverif_role,

                        reason=(

                            "nanZ Verification Approved"

                        ),

                    )



                except discord.HTTPException as e:



                    print(

                        "[VERIFY] Gagal menghapus "

                        f"Non Verif: {e}"

                    )



            # Pastikan role wajib benar-benar terpasang sebelum status dianggap selesai.
            try:
                fresh_member = await guild.fetch_member(target_user_id)
                fresh_role_ids = {role.id for role in fresh_member.roles}
                required_role_ids = {member_role.id, selected_age_role_check.id, selected_gender_role_check.id}
                if not required_role_ids.issubset(fresh_role_ids) or (nonverif_role and nonverif_role.id in fresh_role_ids):
                    await release_approval_for_retry(app_row['id'], interaction.guild.id, target_user_id, decision_token)
                    await safe_followup(interaction, "Pemberian/penghapusan role belum berhasil sepenuhnya. Pengajuan tetap menunggu staff; periksa izin dan posisi role bot.", ephemeral=True)
                    return
            except Exception as exc:
                await release_approval_for_retry(app_row['id'], interaction.guild.id, target_user_id, decision_token)
                print(f"[VERIFY][app={app_row['id']}][APPROVING] Gagal memverifikasi role akhir: {exc}")
                await safe_followup(interaction, "Tidak bisa memastikan role member. Status belum diselesaikan; coba lagi setelah memeriksa bot.", ephemeral=True)
                return

            try:
                await finalize_approval(app_row['id'], interaction.guild.id, target_user_id, decision_token)
            except Exception as exc:
                await release_approval_for_retry(app_row['id'], interaction.guild.id, target_user_id, decision_token)
                print(f"[VERIFY][app={app_row['id']}][APPROVING] Gagal menyimpan status final: {exc}")
                await safe_followup(interaction, "Role sudah diproses tetapi status database belum berhasil diselesaikan. Silakan coba Approve lagi; proses role aman diulang.", ephemeral=True)
                return

            # -------------------------------------------------

            # DM MEMBER

            # -------------------------------------------------



            try:



                await member.send(

                    "Verifikasi kamu disetujui."

                )



            except Exception:



                # DM tertutup bukan error sistem

                pass



        # =================================================

        # SIMPAN DATA MEMBER

        # =================================================



        data_channel = interaction.client.get_channel(DATA_MEMBER_CHANNEL_ID)
        if data_channel is None:
            try:
                data_channel = await interaction.client.fetch_channel(DATA_MEMBER_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                print(f"[VERIFY][app={app_row['id']}][DATA_MEMBER] Channel tidak dapat diakses: {exc}")
                data_channel = None



        if data_channel:



            data_embed = discord.Embed(

                title="Data Member Baru",

                color=0x57F287,

            )



            if member:



                user_display = (

                    f"{member} "

                    f"({self.user_id})"

                )



                username_display = member.name



            else:



                user_display = (

                    f"User tidak ditemukan "

                    f"({self.user_id})"

                )



                username_display = (

                    self.user_id

                )



            data_embed.add_field(

                name="User",

                value=user_display,

                inline=False,

            )



            data_embed.add_field(

                name="Nama",

                value=self.nama or "Tidak diisi",

                inline=True,

            )



            data_embed.add_field(

                name="Asal",

                value=self.asal or "Tidak diisi",

                inline=True,

            )



            data_embed.add_field(

                name="Umur",

                value=(

                    self.umur

                    or "Tidak diisi"

                ),

                inline=True,

            )



            data_embed.add_field(

                name="Gender",

                value=(

                    "Siswa"

                    if self.gender == "L"

                    else (

                        "Siswi"

                        if self.gender == "P"

                        else (

                            self.gender

                            or "Tidak diisi"

                        )

                    )

                ),

                inline=True,

            )



            data_embed.add_field(

                name="Medsos",

                value=(

                    self.medsos

                    or "Tidak diisi"

                ),

                inline=False,

            )



            data_embed.add_field(

                name="Followers",

                value=(

                    self.followers

                    or "Tidak dicek"

                ),

                inline=True,

            )



            data_embed.add_field(

                name="Profile",

                value=(

                    self.link

                    or "Tidak tersedia"

                ),

                inline=False,

            )



            data_embed.add_field(

                name="Approved By",

                value=interaction.user.mention,

                inline=False,

            )



            if member:



                data_embed.set_thumbnail(

                    url=member.display_avatar.url

                )



            try:



                await data_channel.send(

                    content=(

                        f"**Username:** "

                        f"{username_display}"

                    ),

                    embed=data_embed,

                )



            except discord.HTTPException as e:



                print(

                    "[VERIFY] Gagal menyimpan "

                    f"data member: {e}"

                )



        # =================================================

        else:
            print(f"[VERIFY][app={app_row['id']}][DATA_MEMBER] Channel {DATA_MEMBER_CHANNEL_ID} tidak tersedia.")
            await safe_followup(
                interaction,
                "Role sudah diberikan, tetapi data member belum terkirim karena channel data member tidak dapat diakses. Periksa ID channel dan izin bot.",
                ephemeral=True,
            )
            return

        # UPDATE PANEL

        # =================================================



        if interaction.message.embeds:



            try:



                embed = (

                    interaction.message.embeds[0]

                )



                embed.color = 0x57F287



                embed.add_field(

                    name="Status",

                    value=(

                        f"Approved by "

                        f"{interaction.user.mention}"

                    ),

                    inline=False,

                )



                await interaction.message.edit(

                    embed=embed,

                    view=None,

                )



            except discord.HTTPException as e:
                print(f"[VERIFY][app={app_row['id']}] Gagal mengupdate panel approve: {e}")
                await safe_followup(
                    interaction,
                    "Data sudah diproses, tetapi pesan tombol gagal diperbarui. Periksa izin bot di channel verifikasi.",
                    ephemeral=True,
                )
                return



        # =================================================

        # RESPONSE

        # =================================================



        await safe_followup(

            interaction,

            "Verifikasi berhasil diapprove.",

            ephemeral=True,

        )



    # =====================================================

    # DENY

    # =====================================================



    @discord.ui.button(

        label="Deny",

        style=discord.ButtonStyle.danger,

        custom_id="verify_deny_button",

    )

    async def deny(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button,

    ):



        # =================================================

        # DEFER SECEPAT MUNGKIN

        # =================================================



        if not await safe_defer(

            interaction,

            ephemeral=True

        ):

            return



        # =================================================

        # VALIDASI GUILD

        # =================================================



        if interaction.guild is None:



            await safe_followup(

                interaction,

                (

                    "Verifikasi hanya dapat "

                    "diproses di dalam server."

                ),

                ephemeral=True,

            )

            return



        # =================================================

        # LOAD DATA

        # =================================================



        if not self._load_from_message(

            interaction.message

        ):



            await safe_followup(

                interaction,

                (

                    "Data verifikasi pada pesan "

                    "ini tidak dapat dibaca."

                ),

                ephemeral=True,

            )

            return



        # =================================================

        # USER ID

        # =================================================



        try:



            target_user_id = int(

                self.user_id

            )



        except (

            ValueError,

            TypeError

        ):



            await safe_followup(

                interaction,

                (

                    "ID member pada data "

                    "verifikasi tidak valid."

                ),

                ephemeral=True,

            )

            return



        # =================================================

        # AMBIL MEMBER

        # =================================================



        member = (

            interaction.guild.get_member(

                target_user_id

            )

        )



        if member is None:



            try:



                member = (

                    await interaction.guild.fetch_member(

                        target_user_id

                    )

                )



            except (

                discord.NotFound,

                discord.HTTPException

            ):



                member = None



        staff_member = interaction.user
        staff_roles = getattr(staff_member, "roles", [])
        is_staff = (
            getattr(getattr(staff_member, "guild_permissions", None), "administrator", False)
            or getattr(getattr(staff_member, "guild_permissions", None), "manage_messages", False)
            or any(role.id == ENGAGEMENT_ROLE_ID for role in staff_roles)
        )
        if not is_staff:
            await safe_followup(interaction, "Kamu tidak memiliki izin untuk memproses verifikasi ini.", ephemeral=True)
            return
        try:
            app_row = await resolve_application(interaction, self.application_id, target_user_id)
        except Exception as exc:
            print(f"[VERIFY][user={target_user_id}][DB] Gagal memvalidasi aplikasi: {exc}")
            await safe_followup(interaction, "Database verifikasi gagal diakses. Keputusan belum diproses.", ephemeral=True)
            return
        if not app_row:
            await safe_followup(interaction, "Pengajuan ini tidak cocok dengan pengajuan aktif atau merupakan tombol lama. Tidak ada perubahan yang dilakukan.", ephemeral=True)
            return
        claimed, decision_token = await claim_decision(interaction, app_row, "DENYING")
        if not claimed:
            await safe_followup(interaction, "Pengajuan ini sudah diproses staff lain atau statusnya sudah berubah.", ephemeral=True)
            return
        try:
            await finalize_denial(app_row['id'], interaction.guild.id, target_user_id, decision_token)
        except Exception as exc:
            print(f"[VERIFY][app={app_row['id']}][DENYING] Gagal menyimpan keputusan: {exc}")
            await safe_followup(interaction, "Keputusan belum tersimpan di database. Coba lagi atau hubungi admin.", ephemeral=True)
            return

        # =================================================

        # DM MEMBER

        # =================================================



        if member:



            try:



                await member.send(

                    "Verifikasi kamu ditolak."

                )



            except Exception:



                pass



        # =================================================

        # UPDATE PANEL

        # =================================================



        if interaction.message.embeds:



            try:



                embed = (

                    interaction.message.embeds[0]

                )



                embed.color = 0xED4245



                embed.add_field(

                    name="Status",

                    value=(

                        f"Denied by "

                        f"{interaction.user.mention}"

                    ),

                    inline=False,

                )



                await interaction.message.edit(

                    embed=embed,

                    view=None,

                )



            except discord.HTTPException as e:



                print(

                    "[VERIFY] Gagal mengupdate "

                    f"panel deny: {e}"

                )



        # =================================================

        # RESPONSE

        # =================================================



        await safe_followup(

            interaction,

            "Verifikasi berhasil dideny.",

            ephemeral=True,

        )





# =========================================================

# MAIN COG

# =========================================================



class VerifySystem(

    commands.Cog

):



    def __init__(

        self,

        bot

    ):



        self.bot = bot



    async def cog_load(self):
        try:
            await setup_verification_database()
            print("[VERIFY][DB] Tabel verifikasi siap.")
        except Exception as exc:
            print(f"[VERIFY][DB] Gagal menyiapkan tabel verifikasi: {exc}")
            raise
        if not self.reminder_worker.is_running():
            self.reminder_worker.start()

    async def cog_unload(self):
        self.reminder_worker.cancel()

    @tasks.loop(minutes=5)
    async def reminder_worker(self):
        try:
            rows = await db.fetchall("""
                SELECT id,guild_id,user_id,status,reminder_count
                FROM nanz_verification_applications
                WHERE status IN ('MENUNGGU_VOICE','MENUNGGU_STAFF')
                  AND reminder_blocked=0 AND reminder_claim IS NULL
                  AND next_reminder_at IS NOT NULL AND next_reminder_at <= NOW()
                ORDER BY next_reminder_at ASC LIMIT 50
            """)
        except Exception as exc:
            print(f"[VERIFY][REMINDER][DB] Gagal mengambil antrean pengingat: {exc}")
            return
        for row in rows:
            app_id = int(row['id'])
            guild_id = int(row['guild_id'])
            user_id = int(row['user_id'])
            reminder_token = uuid.uuid4().hex
            try:
                await db.execute("""
                    UPDATE nanz_verification_applications SET reminder_claim=%s
                    WHERE id=%s AND reminder_claim IS NULL AND reminder_blocked=0
                      AND next_reminder_at <= NOW()
                      AND status IN ('MENUNGGU_VOICE','MENUNGGU_STAFF')
                """, reminder_token, app_id)
                claim_row = await db.fetchone(
                    "SELECT reminder_claim FROM nanz_verification_applications WHERE id=%s LIMIT 1", app_id
                )
                if not claim_row or claim_row.get('reminder_claim') != reminder_token:
                    continue
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    # Cache/connection may not be ready just after restart. Do not
                    # incorrectly mark a valid applicant as LEFT; release the claim
                    # so a later worker pass can retry.
                    await db.execute(
                        "UPDATE nanz_verification_applications "
                        "SET reminder_claim=NULL WHERE id=%s AND reminder_claim=%s",
                        app_id, reminder_token
                    )
                    continue

                member = guild.get_member(user_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(user_id)
                    except discord.NotFound:
                        member = None
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        # A temporary fetch failure is not proof that the member left.
                        await db.execute(
                            "UPDATE nanz_verification_applications "
                            "SET reminder_claim=NULL WHERE id=%s AND reminder_claim=%s",
                            app_id, reminder_token
                        )
                        print(
                            f"[VERIFY][app={app_id}][REMINDER] "
                            f"Gagal memastikan member masih di server; akan dicoba lagi: {exc}"
                        )
                        continue

                if member is None:
                    await db.execute(
                        "UPDATE nanz_verification_applications "
                        "SET status='LEFT',reminder_blocked=1,next_reminder_at=NULL,reminder_claim=NULL "
                        "WHERE id=%s AND reminder_claim=%s AND status IN ('MENUNGGU_VOICE','MENUNGGU_STAFF')",
                        app_id, reminder_token
                    )
                    await db.execute(
                        "UPDATE nanz_verification_active SET status='LEFT' "
                        "WHERE guild_id=%s AND user_id=%s AND current_app_id=%s",
                        guild_id, user_id, app_id
                    )
                    continue
                if row['status'] == 'MENUNGGU_VOICE':
                    message = "Pengingat verifikasi nanZ: data kamu sudah dikirim. Silakan masuk ke Voice Verif untuk konfirmasi bersama staff."
                else:
                    message = "Pengingat verifikasi nanZ: kamu masih menunggu konfirmasi staff. Silakan tetap berada di server; jika sudah menunggu lama, hubungi staff."
                try:
                    await member.send(message)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    await db.execute("UPDATE nanz_verification_applications SET reminder_blocked=1,next_reminder_at=NULL,reminder_claim=NULL WHERE id=%s AND reminder_claim=%s", app_id, reminder_token)
                    print(f"[VERIFY][app={app_id}][{row['status']}][REMINDER] DM gagal; pengingat dihentikan untuk follow-up staff: {exc}")
                    continue
                await db.execute("""
                    UPDATE nanz_verification_applications
                    SET last_reminder_at=NOW(),
                        next_reminder_at=DATE_ADD(NOW(), INTERVAL 8 HOUR),
                        reminder_blocked=0,
                        reminder_count=IF(reminder_count >= 2,0,reminder_count+1),
                        reminder_claim=NULL
                    WHERE id=%s AND reminder_claim=%s AND status IN ('MENUNGGU_VOICE','MENUNGGU_STAFF') AND reminder_blocked=0
                """, app_id, reminder_token)
            except Exception as exc:
                # Avoid a permanent reminder_claim lock after transient DB/API errors.
                try:
                    await db.execute(
                        "UPDATE nanz_verification_applications "
                        "SET reminder_claim=NULL WHERE id=%s AND reminder_claim=%s",
                        app_id, reminder_token
                    )
                except Exception as release_exc:
                    print(
                        f"[VERIFY][app={app_id}][REMINDER] "
                        f"Gagal melepas claim pengingat: {release_exc}"
                    )
                print(f"[VERIFY][app={app_id}][REMINDER] Error: {exc}")

    @reminder_worker.before_loop
    async def before_reminder_worker(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or after.channel is None:
            return
        if after.channel.id not in VOICE_VERIF_CHANNEL_IDS:
            return
        if before.channel and before.channel.id == after.channel.id:
            return
        try:
            await mark_voice_arrival(self.bot, member, after.channel)
        except Exception as exc:
            print(f"[VERIFY][user={member.id}][MENUNGGU_STAFF] Voice event gagal diproses: {exc}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            await db.execute("""
                UPDATE nanz_verification_applications
                SET status='LEFT',reminder_blocked=1,next_reminder_at=NULL
                WHERE guild_id=%s AND user_id=%s AND status IN ('MENGISI_DATA','MENUNGGU_VOICE','MENUNGGU_STAFF','APPROVING','DENYING')
            """, member.guild.id, member.id)
            await db.execute("""
                UPDATE nanz_verification_active SET status='LEFT',claim_token=NULL
                WHERE guild_id=%s AND user_id=%s AND status NOT IN ('DISETUJUI','DENIED')
            """, member.guild.id, member.id)
        except Exception as exc:
            print(f"[VERIFY][user={member.id}][LEFT] Gagal memperbarui status keluar server: {exc}")

    # =====================================================

    # SHOW VERIFICATION PANEL

    # =====================================================



    async def show_verification_panel(

        self,

        interaction: discord.Interaction,

    ):

        """

        Dipanggil dari tombol Data Verif

        di bawah GIF welcome.



        Panel dikirim ephemeral agar hanya

        member terkait yang melihatnya.

        """



        embed = discord.Embed(

            title="Verifikasi Member",

            description=(

                "**Verifikasi wajib untuk semua member baru nanZ.**\n\n"

                "**LANGKAH 1 — Pilih data awal**\n"

                "Pilih platform medsos yang kamu gunakan, rentang umur, dan gender melalui menu di bawah.\n\n"

                "**LANGKAH 2 — Isi formulir**\n"

                "Setelah ketiga pilihan lengkap, tekan **Lanjut Isi Data**. Isi nama, asal, dan username medsos "
                "(boleh dengan atau tanpa `@`), lalu submit formulir. Pastikan username benar agar staff bisa mengeceknya.\n\n"

                "**LANGKAH 3 — Konfirmasi lewat voice**\n"

                "Setelah submit berhasil, tekan **Join Voice Verif**. Masuk atau tunggu di voice yang diarahkan, "
                "lalu staff akan bergabung untuk mengonfirmasi data kamu.\n\n"

                "**LANGKAH 4 — Tunggu keputusan staff**\n"

                "Jangan mengirim formulir berulang kali. Jika staff belum datang atau belum memproses pengajuan, "
                "bot akan mengirim pengingat lewat DM setiap sekitar 8 jam (maksimal 3 kali sehari) selama pengajuan masih pending."

            ),

            color=0x5865F2,

        )



        embed.add_field(

            name="Data yang diperlukan",

            value=(

                "1. Platform medsos, rentang umur, dan gender\n"

                "2. Tekan **Lanjut Isi Data**\n"

                "3. Isi nama, asal, dan username medsos\n"

                "4. Submit formulir\n"

                "5. Join Voice Verif untuk konfirmasi bersama staff"

            ),

            inline=False,

        )



        embed.set_footer(

            text="nanZ Verification System"

        )



        await safe_response_send(

            interaction,

            embed=embed,

            view=VerifyButton(

                self.bot

            ),

            ephemeral=True,

        )



    # =====================================================

    # COMMAND DATAVERIF

    # =====================================================



    @commands.command(

        name="dataverif"

    )

    async def verifikasi(

        self,

        ctx

    ):



        if (

            ctx.channel.id

            != VERIF_CHANNEL_ID

        ):

            return



        embed = discord.Embed(

            title="Verifikasi Member",

            description=(

                f"{NANZ_ARROW_BLUE} "

                "Panel manual untuk staff.\n"

                "Gunakan panel ini jika diperlukan."

            ),

            color=0x5865F2,

        )



        embed.add_field(

            name="Informasi",

            value=(

                "Data hanya dapat dilihat staff.\n"

                "Umur dan gender dipilih melalui opsi.\n"

                "Role umur dan gender diberikan "

                "otomatis setelah approve."

            ),

            inline=False,

        )



        # Panel aktif selama 1 jam

        try:



            await ctx.send(

                embed=embed,

                view=VerifyButton(

                    self.bot

                ),

                delete_after=3600,

            )



        except discord.HTTPException as e:



            print(

                f"[VERIFY] Gagal mengirim "

                f"panel dataverif: {e}"

            )



            return



        # Hapus command

        try:



            await ctx.message.delete()



        except (

            discord.Forbidden,

            discord.NotFound,

            discord.HTTPException

        ):



            pass





# =========================================================

# SETUP

# =========================================================



async def setup(bot):



    # =====================================================

    # PERSISTENT APPROVE / DENY

    # =====================================================



    bot.add_view(

        VerifyView(bot)

    )



    # =====================================================

    # COG

    # =====================================================



    await bot.add_cog(

        VerifySystem(bot)

    )



    print(

        "[VERIFY] VerifySystem Cog loaded."

    )