"""
Jam Bot - Discord Ranking System
Tracks messages (XP) and referrals via invite links to assign roles automatically.

Roles:
  - Strawberry Jam (Level 1): 100 XP or 1 referral
  - Blueberry Jam (Level 2): 500 XP or 5 referrals
  - Golden Jam (Level 3): 1500 XP or 15 referrals

XP Rules:
  - 10 XP per message (with 60s cooldown to prevent spam)
  - Bonus XP for longer messages (5 XP if 50+ chars)

Referrals:
  - /mylink generates a personal invite link for the user
  - when someone joins through that link, the inviter gets credit automatically
  - no limit on how many people you can refer
"""

import asyncio
import os
import time
import random
import discord
from discord import app_commands
from discord.ext import commands
import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2 import sql
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Configuration - edit these to customize your bot
# ---------------------------------------------------------------------------

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# role names (must match exactly what you create in discord server settings)
ROLE_NAMES = {
    1: "strawberry jam",
    2: "blueberry jam",
    3: "golden jam",
    4: "diamond jam",
    5: "platinum jam",
    6: "infinity jam",
}

# level thresholds: (xp_required, referrals_required)
# user needs to meet EITHER the xp OR the referral threshold to level up
# level thresholds (xp only, referrals grant 50 xp each)
LEVEL_THRESHOLDS = {
    1: {"xp": 100},
    2: {"xp": 500},
    3: {"xp": 1500},
    4: {"xp": 8000},
    5: {"xp": 15000},
    6: {"xp": 25000},
}

XP_PER_MESSAGE = 10
XP_BONUS_LONG_MESSAGE = 5       # bonus xp for messages with 50+ characters
XP_PER_REFERRAL = 50            # xp earned when someone joins through your link
XP_COOLDOWN_SECONDS = 60        # prevents spamming for xp
IGNORED_PREFIXES = ("!", "/", "?", ".")  # ignore bot commands

# channels where threads should be auto-archived (keeps sidebar clean)
AUTO_ARCHIVE_CHANNELS = ["intros"]

# onboarding gate: new members must post in both channels to get verified
# create a role called "verified" and restrict other channels to verified-only
VERIFIED_ROLE_NAME = "verified"
REQUIRED_CHANNELS = ["intros", "projects"]  # must post in both to get verified

# channel where the bot will post level-up announcements
ANNOUNCEMENT_CHANNEL_NAME = "commands"

# channel where the bot will post referral announcements (set to None to use system channel)
REFERRAL_CHANNEL_NAME = "commands"

# ---------------------------------------------------------------------------
# Database setup (PostgreSQL)
# ---------------------------------------------------------------------------

# railway auto-sets DATABASE_URL when you add a postgres addon
DATABASE_URL = os.getenv("DATABASE_URL")


db_pool: pg_pool.SimpleConnectionPool | None = None


def init_pool():
    global db_pool
    if db_pool is None:
        db_pool = pg_pool.SimpleConnectionPool(1, 10, DATABASE_URL)


@contextmanager
def get_conn():
    init_pool()
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS referral_log (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT NOT NULL UNIQUE,
                timestamp DOUBLE PRECISION NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS invite_owners (
                invite_code TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS onboarding_progress (
                user_id BIGINT NOT NULL,
                channel_name TEXT NOT NULL,
                completed_at DOUBLE PRECISION NOT NULL,
                PRIMARY KEY (user_id, channel_name)
            )
        """)
        conn.commit()


def get_user(user_id: int) -> dict:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, xp, level, referrals, total_messages FROM users WHERE user_id = %s", (user_id,))
        row = c.fetchone()
        if row is None:
            c.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
            conn.commit()
            return {"user_id": user_id, "xp": 0, "level": 0, "referrals": 0, "total_messages": 0}
        return {"user_id": row[0], "xp": row[1], "level": row[2], "referrals": row[3], "total_messages": row[4]}


def update_user(user_id: int, **kwargs):
    with get_conn() as conn:
        c = conn.cursor()
        sets = ", ".join(f"{k} = %s" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        c.execute(f"UPDATE users SET {sets} WHERE user_id = %s", vals)
        conn.commit()


def add_referral(referrer_id: int, referred_id: int) -> bool:
    """returns True if referral was recorded, False if already exists."""
    with get_conn() as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO referral_log (referrer_id, referred_id, timestamp) VALUES (%s, %s, %s)",
                (referrer_id, referred_id, time.time()),
            )
            conn.commit()
            return True
        except psycopg2.IntegrityError:
            conn.rollback()
            return False


def save_invite_owner(invite_code: str, user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO invite_owners (invite_code, user_id) VALUES (%s, %s)
               ON CONFLICT (invite_code) DO UPDATE SET user_id = EXCLUDED.user_id""",
            (invite_code, user_id),
        )
        conn.commit()


def get_invite_owner(invite_code: str) -> int | None:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM invite_owners WHERE invite_code = %s", (invite_code,))
        row = c.fetchone()
        return row[0] if row else None


def get_leaderboard(limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, xp, level, referrals, total_messages FROM users ORDER BY xp DESC LIMIT %s", (limit,))
        rows = c.fetchall()
        return [
            {"user_id": r[0], "xp": r[1], "level": r[2], "referrals": r[3], "total_messages": r[4]}
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Onboarding gate
# ---------------------------------------------------------------------------

def mark_channel_done(user_id: int, channel_name: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO onboarding_progress (user_id, channel_name, completed_at)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, channel_name) DO NOTHING""",
            (user_id, channel_name, time.time()),
        )
        conn.commit()


def get_completed_channels(user_id: int) -> set:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT channel_name FROM onboarding_progress WHERE user_id = %s", (user_id,))
        rows = c.fetchall()
        return {r[0] for r in rows}


def is_onboarding_complete(user_id: int) -> bool:
    completed = get_completed_channels(user_id)
    return all(ch in completed for ch in REQUIRED_CHANNELS)


# ---------------------------------------------------------------------------
# Level calculation
# ---------------------------------------------------------------------------

def calculate_level(xp: int) -> int:
    """determine the highest level a user qualifies for based on xp."""
    level = 0
    for lvl in sorted(LEVEL_THRESHOLDS.keys()):
        req = LEVEL_THRESHOLDS[lvl]
        if xp >= req["xp"]:
            level = lvl
        else:
            break
    return level


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.invites = True  # needed to track invite usage

bot = commands.Bot(command_prefix="!", intents=intents)

# cooldown tracker: {user_id: last_xp_timestamp}
xp_cooldowns: dict[int, float] = {}

# cached invite uses per guild: {guild_id: {invite_code: uses}}
invite_cache: dict[int, dict[str, int]] = {}
invite_lock = asyncio.Lock()


async def sync_roles(member: discord.Member, new_level: int):
    """assign only the current level role, remove all lower jam roles."""
    guild = member.guild
    for lvl, role_name in ROLE_NAMES.items():
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            continue
        if lvl == new_level:
            if role not in member.roles:
                await member.add_roles(role)
        else:
            if role in member.roles:
                await member.remove_roles(role)


def level_emoji(level: int) -> str:
    return {1: "🍓", 2: "🫐", 3: "🍯", 4: "💎", 5: "✨", 6: "♾️"}.get(level, "")


async def cache_invites(guild: discord.Guild):
    """snapshot all current invite use counts for a guild."""
    try:
        invites = await guild.invites()
        invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"could not cache invites for {guild.name}: {e}")


async def get_referral_channel(guild: discord.Guild) -> discord.TextChannel | None:
    if REFERRAL_CHANNEL_NAME:
        ch = discord.utils.get(guild.text_channels, name=REFERRAL_CHANNEL_NAME)
        if ch:
            return ch
    return guild.system_channel


async def ensure_invite_link(member: discord.Member) -> str | None:
    """make sure a member has a personal invite link. creates one if they don't.
    returns the invite url or None if it couldn't be created."""
    if member.bot:
        return None

    # check if they already have one in the db
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT invite_code FROM invite_owners WHERE user_id = %s", (member.id,))
        row = c.fetchone()

    if row:
        # verify the invite still exists on discord (it may have been deleted)
        try:
            invites = await member.guild.invites()
            for inv in invites:
                if inv.code == row[0]:
                    return inv.url
        except discord.Forbidden:
            return None
        # invite was deleted, fall through to create a new one

    # create a new invite
    guild = member.guild
    channel = guild.system_channel or guild.text_channels[0]

    try:
        invite = await channel.create_invite(
            max_age=0,
            max_uses=0,
            unique=True,
            reason=f"auto-generated referral link for {member.display_name}",
        )
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"could not create invite for {member.display_name}: {e}")
        return None

    save_invite_owner(invite.code, member.id)
    await cache_invites(guild)
    return invite.url


async def dm_welcome(member: discord.Member, invite_url: str = None):
    """send the new member a welcome DM with onboarding info."""
    try:
        embed = discord.Embed(
            title=f"welcome to {member.guild.name}!",
            description=(
                f"hey **{member.display_name}**, we're glad you're here! "
                f"here's everything you need to get started."
            ),
            color=discord.Color.from_str("#ff6b6b"),
        )

        embed.add_field(
            name="introduce yourself",
            value="head over to **#intros** and tell us a bit about yourself! who you are, what you're working on, what brings you here.",
            inline=False,
        )

        embed.add_field(
            name="share your projects",
            value="got something you're building? drop it in **#projects**! we love seeing what people are working on.",
            inline=False,
        )

        embed.add_field(
            name="ranking system",
            value=(
                "you earn **xp** by chatting and referring friends:\n"
                f"- **{XP_PER_MESSAGE} xp** per message ({XP_PER_MESSAGE + XP_BONUS_LONG_MESSAGE} xp for longer messages)\n"
                f"- **{XP_PER_REFERRAL} xp** per friend you invite\n\n"
                f"🍓 **strawberry jam** — {LEVEL_THRESHOLDS[1]['xp']} xp\n"
                f"🫐 **blueberry jam** — {LEVEL_THRESHOLDS[2]['xp']} xp\n"
                f"🍯 **golden jam** — {LEVEL_THRESHOLDS[3]['xp']} xp\n"
                f"💎 **diamond jam** — {LEVEL_THRESHOLDS[4]['xp']} xp\n"
                f"✨ **platinum jam** — {LEVEL_THRESHOLDS[5]['xp']} xp\n"
                f"♾️ **infinity jam** — {LEVEL_THRESHOLDS[6]['xp']} xp"
            ),
            inline=False,
        )

        if invite_url:
            embed.add_field(
                name="your referral link",
                value=f"**{invite_url}**\nshare this with friends to earn xp! use `/mylink` anytime to see it again.",
                inline=False,
            )
        else:
            embed.add_field(
                name="invite your friends",
                value="use `/mylink` in the server to get your personal referral link. share it with friends to earn 50 xp per invite!",
                inline=False,
            )

        embed.add_field(
            name="useful commands",
            value=(
                "`/rank` — check your xp and level\n"
                "`/leaderboard` — see the top members\n"
                "`/mylink` — get your referral link\n"
                "`/myreferrals` — see who you've referred"
                "`/am i jam?` — checks whether you're jam or bread\n"
            ),
            inline=False,
        )

        embed.set_footer(text="have fun and don't be a stranger!")
        await member.send(embed=embed)
    except discord.Forbidden:
        # user has dms disabled
        pass


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    init_db()
    # cache invites for all guilds
    for guild in bot.guilds:
        await cache_invites(guild)
    try:
        synced = await bot.tree.sync()
        print(f"synced {len(synced)} slash commands")
    except Exception as e:
        print(f"failed to sync commands: {e}")
    print(f"jam bot is online as {bot.user}")


# background invite generation disabled - invites are created on demand via /mylink
# or when a new member joins. run cleanup_invites.py first if you hit the invite limit.


@bot.event
async def on_invite_create(invite: discord.Invite):
    """just update cache locally without fetching all invites."""
    if invite.guild:
        invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses


@bot.event
async def on_invite_delete(invite: discord.Invite):
    """just remove from cache locally without fetching all invites."""
    if invite.guild and invite.guild.id in invite_cache:
        invite_cache[invite.guild.id].pop(invite.code, None)


@bot.event
async def on_member_join(member: discord.Member):
    """detect which invite was used by comparing before/after use counts."""
    guild = member.guild

    async with invite_lock:
        old_cache = invite_cache.get(guild.id, {})

        try:
            new_invites = await guild.invites()
        except discord.Forbidden:
            return

        used_invite = None
        for inv in new_invites:
            old_uses = old_cache.get(inv.code, 0)
            if inv.uses > old_uses:
                used_invite = inv
                break

        invite_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}

    if used_invite is None:
        return

    # check if this invite is owned by someone (from /mylink)
    referrer_id = get_invite_owner(used_invite.code)

    # fallback: if the invite wasn't created by /mylink, credit the invite creator
    if referrer_id is None and used_invite.inviter and not used_invite.inviter.bot:
        referrer_id = used_invite.inviter.id

    if referrer_id is None or referrer_id == member.id:
        await dm_welcome(member)
        return

    # record the referral
    success = add_referral(referrer_id, member.id)

    # welcome the new member (no auto invite, they use /mylink)
    await dm_welcome(member)

    if not success:
        return

    # update referrer stats (grant xp + referral count)
    ref_user = get_user(referrer_id)
    new_referrals = ref_user["referrals"] + 1
    new_xp = ref_user["xp"] + XP_PER_REFERRAL
    new_level = calculate_level(new_xp)
    update_user(referrer_id, referrals=new_referrals, xp=new_xp, level=new_level)

    # announce
    channel = await get_referral_channel(guild)
    referrer_member = guild.get_member(referrer_id)
    referrer_name = referrer_member.display_name if referrer_member else f"user {referrer_id}"

    if channel:
        await channel.send(
            f"**{member.display_name}** joined via **{referrer_name}**'s invite! "
            f"{referrer_name} earned {XP_PER_REFERRAL} xp and now has {new_referrals} referral(s)."
        )

    # check for level up
    if new_level > ref_user["level"] and channel:
        role_name = ROLE_NAMES.get(new_level, f"level {new_level}")
        emoji = level_emoji(new_level)
        await channel.send(
            f"{emoji} **{referrer_name}** just reached **{role_name}**! (level {new_level}) {emoji}"
        )
        if referrer_member:
            await sync_roles(referrer_member, new_level)


@bot.event
async def on_thread_create(thread: discord.Thread):
    """auto-archive threads in specified channels to keep the sidebar clean."""
    parent = thread.parent
    if parent and parent.name in AUTO_ARCHIVE_CHANNELS:
        # wait a bit so the thread creator can see their post
        await asyncio.sleep(5)
        try:
            await thread.edit(archived=True)
        except discord.Forbidden:
            pass


@bot.event
async def on_message(message: discord.Message):
    # ignore bots
    if message.author.bot:
        return

    # get guild from thread parent if needed
    guild = message.guild
    if guild is None and isinstance(message.channel, discord.Thread):
        guild = message.channel.guild
    if guild is None:
        return

    # ignore command-like messages
    content = message.content or ""
    if content.startswith(IGNORED_PREFIXES):
        await bot.process_commands(message)
        return

    user_id = message.author.id
    member = guild.get_member(user_id)

    # --- onboarding gate ---
    # check if message is in a required onboarding channel
    channel_name = message.channel.name if hasattr(message.channel, "name") else ""
    # also check parent channel for threads (e.g. forum posts in #intros)
    if isinstance(message.channel, discord.Thread) and message.channel.parent:
        channel_name = message.channel.parent.name

    if channel_name in REQUIRED_CHANNELS and member:
        mark_channel_done(user_id, channel_name)
        # check if they just completed all requirements
        if is_onboarding_complete(user_id):
            verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
            if verified_role and verified_role not in member.roles:
                await member.add_roles(verified_role)
                announce_ch = discord.utils.get(guild.text_channels, name=ANNOUNCEMENT_CHANNEL_NAME)
                if announce_ch:
                    await announce_ch.send(
                        f"<@{user_id}> completed onboarding and is now verified!"
                    )
        else:
            # tell them what's left
            completed = get_completed_channels(user_id)
            remaining = [ch for ch in REQUIRED_CHANNELS if ch not in completed]
            verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
            if verified_role and verified_role not in member.roles:
                try:
                    await message.author.send(
                        f"nice! now post in **#{'**, **#'.join(remaining)}** to unlock the full server."
                    )
                except discord.Forbidden:
                    pass

    now = time.time()

    # cooldown check
    last_xp_time = xp_cooldowns.get(user_id, 0)
    if now - last_xp_time < XP_COOLDOWN_SECONDS:
        await bot.process_commands(message)
        return

    xp_cooldowns[user_id] = now

    # calculate xp earned
    xp_earned = XP_PER_MESSAGE
    if len(content) >= 50:
        xp_earned += XP_BONUS_LONG_MESSAGE

    # update database
    user = get_user(user_id)
    new_xp = user["xp"] + xp_earned
    new_messages = user["total_messages"] + 1
    new_level = calculate_level(new_xp)

    update_user(user_id, xp=new_xp, total_messages=new_messages, level=new_level)

    # check for level up
    if new_level > user["level"]:
        role_name = ROLE_NAMES.get(new_level, f"level {new_level}")
        emoji = level_emoji(new_level)
        # post in commands channel instead of current channel
        announce_ch = discord.utils.get(guild.text_channels, name=ANNOUNCEMENT_CHANNEL_NAME)
        if announce_ch:
            await announce_ch.send(
                f"{emoji} <@{message.author.id}> just reached **{role_name}**! (level {new_level}) {emoji}"
            )
        if member:
            await sync_roles(member, new_level)

    await bot.process_commands(message)


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

@bot.tree.command(name="rank", description="check your current rank and xp")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    try:
        target = member or interaction.user
        user = get_user(target.id)

        current_level = user["level"]
        next_level = current_level + 1
        role_name = ROLE_NAMES.get(current_level, "unranked")
        emoji = level_emoji(current_level)

        # progress to next level
        if next_level in LEVEL_THRESHOLDS:
            next_req = LEVEL_THRESHOLDS[next_level]
            xp_progress = f"{user['xp']}/{next_req['xp']} xp"
            # calculate progress bar
            prev_xp = LEVEL_THRESHOLDS[current_level]["xp"] if current_level in LEVEL_THRESHOLDS else 0
            xp_in_level = user["xp"] - prev_xp
            xp_needed = next_req["xp"] - prev_xp
            progress = max(0.0, min(1.0, xp_in_level / xp_needed)) if xp_needed > 0 else 1.0
            bar_length = 10
            filled = round(progress * bar_length)
            bar = "\u2588" * filled + "\u2500" * (bar_length - filled)
            next_role = ROLE_NAMES.get(next_level, f"level {next_level}")
            next_emoji = level_emoji(next_level)
            progress_text = f"`{bar}` {int(progress * 100)}%\n{next_emoji} **{next_role}**"
        else:
            xp_progress = f"{user['xp']} xp (max level!)"
            bar = "\u2588" * 10
            progress_text = f"`{bar}` 100%\n♾️ **max level reached!**"

        embed = discord.Embed(
            title=f"{emoji} {target.display_name}'s rank",
            color=discord.Color.from_str({1: "#ff6b6b", 2: "#748ffc", 3: "#ffd43b"}.get(current_level, "#868e96")),
        )
        embed.add_field(name="level", value=f"{current_level} ({role_name})", inline=True)
        embed.add_field(name="xp", value=xp_progress, inline=True)
        embed.add_field(name="referrals", value=str(user["referrals"]), inline=True)
        embed.add_field(name="total messages", value=str(user["total_messages"]), inline=True)
        embed.add_field(name="progress", value=progress_text, inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)

        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"error in /rank: {e}")
        await interaction.followup.send("something went wrong, check the logs!", ephemeral=True)


@bot.tree.command(name="mylink", description="see your personal invite link")
async def mylink(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("this only works in a server!")
            return

        invite_url = await ensure_invite_link(interaction.user)
        if not invite_url:
            await interaction.followup.send(
                "couldn't create an invite link. make sure i have the 'create invite' permission!"
            )
            return

        user = get_user(interaction.user.id)

        embed = discord.Embed(
            title="your personal invite link",
            description=f"**{invite_url}**\n\nshare this link! anyone who joins through it will count as your referral.",
            color=discord.Color.green(),
        )
        embed.add_field(name="current referrals", value=str(user["referrals"]), inline=True)

        next_level = user["level"] + 1
        if next_level in LEVEL_THRESHOLDS:
            xp_needed = LEVEL_THRESHOLDS[next_level]["xp"]
            embed.add_field(
                name=f"xp to {ROLE_NAMES.get(next_level, f'level {next_level}')}",
                value=f"{user['xp']}/{xp_needed} ({user['referrals']} referrals = {user['referrals'] * XP_PER_REFERRAL} xp)",
                inline=True,
            )

        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"error in /mylink: {e}")
        await interaction.followup.send("something went wrong, check the logs!")


@bot.tree.command(name="myreferrals", description="see who you've referred")
async def myreferrals(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        user_id = interaction.user.id
        with get_conn() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT referred_id, timestamp FROM referral_log WHERE referrer_id = %s ORDER BY timestamp DESC LIMIT 20",
                (user_id,),
            )
            rows = c.fetchall()

        if not rows:
            await interaction.followup.send("you haven't referred anyone yet! use `/mylink` to get your invite link.")
            return

        lines = []
        for referred_id, ts in rows:
            member = interaction.guild.get_member(referred_id)
            name = member.display_name if member else f"user {referred_id}"
            date = time.strftime("%b %d, %Y", time.localtime(ts))
            lines.append(f"- **{name}** (joined {date})")

        user = get_user(user_id)
        embed = discord.Embed(
            title=f"your referrals ({user['referrals']} total)",
            description="\n".join(lines),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"error in /myreferrals: {e}")
        await interaction.followup.send("something went wrong, check the logs!")


@bot.tree.command(name="leaderboard", description="see the top members by xp")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        top = get_leaderboard(10)
        if not top:
            await interaction.followup.send("no one has earned xp yet!")
            return

        lines = []
        medals = {0: "**1.**", 1: "**2.**", 2: "**3.**"}
        for i, u in enumerate(top):
            member = interaction.guild.get_member(u["user_id"])
            name = member.display_name if member else f"user {u['user_id']}"
            medal = medals.get(i, f"**{i+1}.**")
            role_name = ROLE_NAMES.get(u["level"], "unranked")
            lines.append(f"{medal} **{name}** | {u['xp']} xp | {u['referrals']} refs | {role_name}")

        embed = discord.Embed(
            title="leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"error in /leaderboard: {e}")
        await interaction.followup.send("something went wrong, check the logs!")


@bot.tree.command(name="ref-leaderboard", description="see the top members by referrals")
async def ref_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, referrals, xp, level FROM users WHERE referrals > 0 ORDER BY referrals DESC LIMIT 10")
            rows = c.fetchall()

        if not rows:
            await interaction.followup.send("no one has referred anyone yet!")
            return

        lines = []
        medals = {0: "**1.**", 1: "**2.**", 2: "**3.**"}
        for i, (user_id, referrals, xp, level) in enumerate(rows):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"user {user_id}"
            medal = medals.get(i, f"**{i+1}.**")
            role_name = ROLE_NAMES.get(level, "unranked")
            lines.append(f"{medal} **{name}** | {referrals} referrals | {xp} xp | {role_name}")

        embed = discord.Embed(
            title="referral leaderboard",
            description="\n".join(lines),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"error in /ref-leaderboard: {e}")
        await interaction.followup.send("something went wrong, check the logs!")


@bot.tree.command(name="bread", description="receive a blessed piece of bread")
async def bread(interaction: discord.Interaction):
    import random
    breads = [
        f"a warm loaf of sourdough is given to **{interaction.user.display_name}**.",
        f"**{interaction.user.display_name}** receives a freshly baked baguette.",
        f"a golden croissant appears before **{interaction.user.display_name}**.",
        f"**{interaction.user.display_name}** is handed a perfect slice of focaccia.",
        f"a mysterious bread fairy delivers a pretzel to **{interaction.user.display_name}**.",
        f"**{interaction.user.display_name}** opens their hands and finds a warm brioche.",
        f"a piping hot piece of naan is bestowed upon **{interaction.user.display_name}**.",
        f"**{interaction.user.display_name}** is blessed with a fluffy milk bread roll.",
        f"a perfectly toasted slice of ciabatta lands in **{interaction.user.display_name}**'s lap.",
        f"the bread gods smile upon **{interaction.user.display_name}** and grant them a pumpernickel loaf.",
        f"**{interaction.user.display_name}** catches a flying pita bread out of thin air.",
        f"a steaming hot cornbread muffin materializes for **{interaction.user.display_name}**.",
        f"**{interaction.user.display_name}** is chosen to receive the sacred challah.",
        f"a tiny baguette rolls across the floor and stops at **{interaction.user.display_name}**'s feet.",
        f"**{interaction.user.display_name}** receives an everything bagel, still warm from the oven.",
    ]
    await interaction.response.send_message(f"*{random.choice(breads)}*")


@bot.tree.command(name="joined", description="Check when a member joined the server")
@app_commands.describe(member="The member to check (leave blank for yourself)")
async def joined(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    try:
        target = member or interaction.user
        
        if target.joined_at:
            # Unix timestamp for Discord dynamic formatting
            timestamp = int(target.joined_at.timestamp())
            
            embed = discord.Embed(
                title=f"Member Join Date",
                description=f"Information for {target.mention}",
                color=discord.Color.from_str("#748ffc")
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            
            # Use Discord's timestamp formats: 
            # F = Long Date/Time, R = Relative time (e.g., "5 months ago")
            embed.add_field(name="Joined On", value=f"<t:{timestamp}:F>", inline=False)
            embed.add_field(name="Duration", value=f"<t:{timestamp}:R>", inline=False)
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Could not retrieve join date for this member.")
            
    except Exception as e:
        print(f"error in /joined: {e}")
        await interaction.followup.send("An error occurred while fetching membership data.", ephemeral=True)


@bot.tree.command(name="setxp", description="(admin) set a user's xp manually")
@app_commands.describe(member="target user", xp="new xp value")
@app_commands.checks.has_permissions(administrator=True)
async def setxp(interaction: discord.Interaction, member: discord.Member, xp: int):
    await interaction.response.defer(ephemeral=True)
    try:
        user = get_user(member.id)
        new_level = calculate_level(xp)
        update_user(member.id, xp=xp, level=new_level)
        await sync_roles(member, new_level)
        await interaction.followup.send(
            f"set **{member.display_name}**'s xp to {xp} (level {new_level})"
        )
    except Exception as e:
        print(f"error in /setxp: {e}")
        await interaction.followup.send(f"error: {e}")


@bot.tree.command(name="setreferrals", description="(admin) set a user's referral count")
@app_commands.describe(member="target user", referrals="new referral count")
@app_commands.checks.has_permissions(administrator=True)
async def setreferrals(interaction: discord.Interaction, member: discord.Member, referrals: int):
    await interaction.response.defer(ephemeral=True)
    try:
        user = get_user(member.id)
        new_level = calculate_level(user["xp"])
        update_user(member.id, referrals=referrals, level=new_level)
        await sync_roles(member, new_level)
        await interaction.followup.send(
            f"set **{member.display_name}**'s referrals to {referrals} (level {new_level})"
        )
    except Exception as e:
        print(f"error in /setreferrals: {e}")
        await interaction.followup.send(f"error: {e}")


@bot.tree.command(name="setup-welcome", description="(admin) post the welcome/onboarding embed in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def setup_welcome(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        guild = interaction.guild

        # main welcome embed
        welcome = discord.Embed(
            title="welcome to jam!",
            description=(
                "we're a community of builders, creators, and curious minds. "
                "here's how to get started and make the most of your time here."
            ),
            color=discord.Color.from_str("#ff6b6b"),
        )

        welcome.add_field(
            name="1. introduce yourself",
            value="head to **#intros** and tell us who you are, what you're working on, and what brought you here!",
            inline=False,
        )

        welcome.add_field(
            name="2. share your projects",
            value="building something cool? show it off in **#projects**! we love seeing what people are creating.",
            inline=False,
        )

        welcome.add_field(
            name="3. start chatting",
            value="jump into any channel and say hi. every message earns you xp toward leveling up!",
            inline=False,
        )

        # ranking embed
        ranking = discord.Embed(
            title="ranking system",
            description="earn xp by chatting and inviting friends. level up to unlock roles!",
            color=discord.Color.from_str("#748ffc"),
        )

        ranking.add_field(
            name="how to earn xp",
            value=(
                f"**{XP_PER_MESSAGE} xp** per message ({XP_PER_MESSAGE + XP_BONUS_LONG_MESSAGE} xp for longer messages)\n"
                f"**{XP_PER_REFERRAL} xp** per friend you invite\n"
                f"{XP_COOLDOWN_SECONDS}s cooldown between messages"
            ),
            inline=False,
        )

        ranking.add_field(
            name="levels",
            value=(
                f"🍓 **strawberry jam** — {LEVEL_THRESHOLDS[1]['xp']} xp\n"
                f"🫐 **blueberry jam** — {LEVEL_THRESHOLDS[2]['xp']} xp\n"
                f"🍯 **golden jam** — {LEVEL_THRESHOLDS[3]['xp']} xp\n"
                f"💎 **diamond jam** — {LEVEL_THRESHOLDS[4]['xp']} xp\n"
                f"✨ **platinum jam** — {LEVEL_THRESHOLDS[5]['xp']} xp\n"
                f"♾️ **infinity jam** — {LEVEL_THRESHOLDS[6]['xp']} xp"
            ),
            inline=False,
        )

        ranking.add_field(
            name="commands",
            value=(
                "`/rank` — check your xp and level\n"
                "`/leaderboard` — see the top members\n"
                "`/mylink` — get your personal referral link\n"
                "`/myreferrals` — see who you've referred"
            ),
            inline=False,
        )

        ranking.set_footer(text="have fun and don't be a stranger!")

        await interaction.channel.send(embeds=[welcome, ranking])
        await interaction.followup.send("welcome embeds posted!")
    except Exception as e:
        print(f"error in /setup-welcome: {e}")
        await interaction.followup.send(f"error: {e}")


@bot.tree.command(name="test-welcome", description="(admin) send yourself the welcome DM to preview it")
@app_commands.checks.has_permissions(administrator=True)
async def test_welcome(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        await dm_welcome(interaction.user, "https://discord.gg/example-link")
        await interaction.followup.send("sent! check your DMs.")
    except Exception as e:
        print(f"error in /test-welcome: {e}")
        await interaction.followup.send(f"error: {e}")


@bot.tree.command(name="am-i-jam", description="am i jam?")
async def am_i_jam(interaction: discord.Interaction):
    result = random.choice(["You're the bread to my jam", "everyone is jam in their own way, but you, you'll always remain my bread"])
    await interaction.response.send_message(result)


@bot.tree.command(name="8ball", description="ask the magic 8-ball a question")
@app_commands.describe(question="your question for the 8-ball")
async def eight_ball(interaction: discord.Interaction, question: str):
    responses = [
        "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.",
        "You may rely on it.", "As I see it, yes.", "Most likely.", "Bread says yes.",
        "Yes.", "Signs point to yes.",
        "Hmmmm, Jam is confused, ask later.", "Ask again later.", "Better not tell you now.",
        "Cannot predict now.", "Jam doesn't like it. Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.",
        "Bread says no.", "Very doubtful.",
    ]
    answer = random.choice(responses)
    embed = discord.Embed(
        title="\U0001f3b1 magic 8-ball",
        color=discord.Color.dark_purple(),
    )
    embed.add_field(name="question", value=question, inline=False)
    embed.add_field(name="answer", value=f"*{answer}*", inline=False)
    embed.set_footer(text=f"asked by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(TOKEN)