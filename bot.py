"""
Jam Bot - Discord Ranking System
Tracks messages (XP) and referrals via invite links to assign roles automatically.

Roles:
  - Strawberry Jam (Level 1): 100 XP or 1 referral
  - Blueberry Jam (Level 2): 500 XP or 5 referrals
  - Golden Jam (Level 3): 1500 XP or 15 referrals

XP Rules:
  - 1 XP per message (with 60s cooldown to prevent spam)
  - Bonus XP for longer messages (2 XP if 50+ chars)

Referrals:
  - /mylink generates a personal invite link for the user
  - when someone joins through that link, the inviter gets credit automatically
  - no limit on how many people you can refer
"""

import os
import time
import discord
from discord import app_commands
from discord.ext import commands
import psycopg2
from psycopg2 import sql

# ---------------------------------------------------------------------------
# Configuration - edit these to customize your bot
# ---------------------------------------------------------------------------

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# role names (must match exactly what you create in discord server settings)
ROLE_NAMES = {
    1: "strawberry jam",
    2: "blueberry jam",
    3: "golden jam",
}

# level thresholds: (xp_required, referrals_required)
# user needs to meet EITHER the xp OR the referral threshold to level up
# level thresholds (xp only, referrals grant 50 xp each)
LEVEL_THRESHOLDS = {
    1: {"xp": 100},
    2: {"xp": 500},
    3: {"xp": 1500},
}

XP_PER_MESSAGE = 1
XP_BONUS_LONG_MESSAGE = 2       # bonus xp for messages with 50+ characters
XP_PER_REFERRAL = 50            # xp earned when someone joins through your link
XP_COOLDOWN_SECONDS = 60        # prevents spamming for xp
IGNORED_PREFIXES = ("!", "/", "?", ".")  # ignore bot commands

# channel where the bot will post referral announcements (set to None to use system channel)
REFERRAL_CHANNEL_NAME = "general"

# ---------------------------------------------------------------------------
# Database setup (PostgreSQL)
# ---------------------------------------------------------------------------

# railway auto-sets DATABASE_URL when you add a postgres addon
DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
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
    conn.commit()
    conn.close()


def get_user(user_id: int) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, xp, level, referrals, total_messages FROM users WHERE user_id = %s", (user_id,))
    row = c.fetchone()
    if row is None:
        c.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
        conn.commit()
        conn.close()
        return {"user_id": user_id, "xp": 0, "level": 0, "referrals": 0, "total_messages": 0}
    conn.close()
    return {"user_id": row[0], "xp": row[1], "level": row[2], "referrals": row[3], "total_messages": row[4]}


def update_user(user_id: int, **kwargs):
    conn = get_conn()
    c = conn.cursor()
    sets = ", ".join(f"{k} = %s" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    c.execute(f"UPDATE users SET {sets} WHERE user_id = %s", vals)
    conn.commit()
    conn.close()


def add_referral(referrer_id: int, referred_id: int) -> bool:
    """returns True if referral was recorded, False if already exists."""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO referral_log (referrer_id, referred_id, timestamp) VALUES (%s, %s, %s)",
            (referrer_id, referred_id, time.time()),
        )
        conn.commit()
        conn.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        conn.close()
        return False


def save_invite_owner(invite_code: str, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO invite_owners (invite_code, user_id) VALUES (%s, %s)
           ON CONFLICT (invite_code) DO UPDATE SET user_id = EXCLUDED.user_id""",
        (invite_code, user_id),
    )
    conn.commit()
    conn.close()


def get_invite_owner(invite_code: str) -> int | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM invite_owners WHERE invite_code = %s", (invite_code,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_leaderboard(limit: int = 10) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, xp, level, referrals, total_messages FROM users ORDER BY xp DESC LIMIT %s", (limit,))
    rows = c.fetchall()
    conn.close()
    return [
        {"user_id": r[0], "xp": r[1], "level": r[2], "referrals": r[3], "total_messages": r[4]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Level calculation
# ---------------------------------------------------------------------------

def calculate_level(xp: int, referrals: int = 0) -> int:
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


async def sync_roles(member: discord.Member, new_level: int):
    """add the correct role and remove outdated jam roles."""
    guild = member.guild
    for lvl, role_name in ROLE_NAMES.items():
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            continue
        if lvl <= new_level:
            if role not in member.roles:
                await member.add_roles(role)
        else:
            if role in member.roles:
                await member.remove_roles(role)


def level_emoji(level: int) -> str:
    return {1: "🍓", 2: "🫐", 3: "✨"}.get(level, "")


async def cache_invites(guild: discord.Guild):
    """snapshot all current invite use counts for a guild."""
    try:
        invites = await guild.invites()
        invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
    except discord.Forbidden:
        print(f"missing 'manage server' permission in {guild.name}, invite tracking won't work")


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
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT invite_code FROM invite_owners WHERE user_id = %s", (member.id,))
    row = c.fetchone()
    conn.close()

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
    except discord.Forbidden:
        return None

    save_invite_owner(invite.code, member.id)
    await cache_invites(guild)
    return invite.url


async def dm_invite_link(member: discord.Member, invite_url: str):
    """send the member their personal invite link via dm."""
    try:
        embed = discord.Embed(
            title="🔗 your personal invite link",
            description=(
                f"**{invite_url}**\n\n"
                f"share this with friends! anyone who joins through your link "
                f"earns you referral credit toward leveling up."
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text="you can also use /mylink anytime to see this again")
        await member.send(embed=embed)
    except discord.Forbidden:
        # user has dms disabled, that's fine, they can use /mylink
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
    # generate invite links in the background so commands work immediately
    for guild in bot.guilds:
        bot.loop.create_task(generate_links_for_guild(guild))


async def generate_links_for_guild(guild: discord.Guild):
    """generate invite links for existing members in the background."""
    import asyncio
    count = 0
    for member in guild.members:
        if not member.bot:
            await ensure_invite_link(member)
            count += 1
            # small delay to avoid rate limits
            if count % 5 == 0:
                await asyncio.sleep(2)
    print(f"done generating invite links for {count} members in {guild.name}")


@bot.event
async def on_invite_create(invite: discord.Invite):
    """keep cache updated when new invites are created."""
    if invite.guild:
        await cache_invites(invite.guild)


@bot.event
async def on_invite_delete(invite: discord.Invite):
    """keep cache updated when invites are deleted."""
    if invite.guild:
        await cache_invites(invite.guild)


@bot.event
async def on_member_join(member: discord.Member):
    """detect which invite was used by comparing before/after use counts."""
    guild = member.guild
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

    # update the cache
    invite_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}

    if used_invite is None:
        return

    # check if this invite is owned by someone (from /mylink)
    referrer_id = get_invite_owner(used_invite.code)

    # fallback: if the invite wasn't created by /mylink, credit the invite creator
    if referrer_id is None and used_invite.inviter and not used_invite.inviter.bot:
        referrer_id = used_invite.inviter.id

    if referrer_id is None or referrer_id == member.id:
        # still generate an invite link for the new member even if no referrer found
        invite_url = await ensure_invite_link(member)
        if invite_url:
            await dm_invite_link(member, invite_url)
        return

    # record the referral
    success = add_referral(referrer_id, member.id)

    # generate an invite link for the new member and dm it
    invite_url = await ensure_invite_link(member)
    if invite_url:
        await dm_invite_link(member, invite_url)

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
            f"🎉 **{member.display_name}** joined via **{referrer_name}**'s invite! "
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
async def on_message(message: discord.Message):
    # ignore bots and dms
    if message.author.bot or message.guild is None:
        return

    # ignore command-like messages
    if message.content.startswith(IGNORED_PREFIXES):
        await bot.process_commands(message)
        return

    user_id = message.author.id
    now = time.time()

    # cooldown check
    last_xp_time = xp_cooldowns.get(user_id, 0)
    if now - last_xp_time < XP_COOLDOWN_SECONDS:
        await bot.process_commands(message)
        return

    xp_cooldowns[user_id] = now

    # make sure this user has an invite link (fallback if they missed the dm)
    invite_url = await ensure_invite_link(message.author)

    # calculate xp earned
    xp_earned = XP_PER_MESSAGE
    if len(message.content) >= 50:
        xp_earned += XP_BONUS_LONG_MESSAGE

    # update database
    user = get_user(user_id)
    new_xp = user["xp"] + xp_earned
    new_messages = user["total_messages"] + 1
    new_level = calculate_level(new_xp, user["referrals"])

    update_user(user_id, xp=new_xp, total_messages=new_messages, level=new_level)

    # check for level up
    if new_level > user["level"]:
        role_name = ROLE_NAMES.get(new_level, f"level {new_level}")
        emoji = level_emoji(new_level)
        await message.channel.send(
            f"{emoji} **{message.author.display_name}** just reached **{role_name}**! (level {new_level}) {emoji}"
        )
        await sync_roles(message.author, new_level)

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
        else:
            xp_progress = f"{user['xp']} xp (max level!)"

        embed = discord.Embed(
            title=f"{emoji} {target.display_name}'s rank",
            color=discord.Color.from_str({1: "#ff6b6b", 2: "#748ffc", 3: "#ffd43b"}.get(current_level, "#868e96")),
        )
        embed.add_field(name="level", value=f"{current_level} ({role_name})", inline=True)
        embed.add_field(name="xp", value=xp_progress, inline=True)
        embed.add_field(name="referrals", value=str(user["referrals"]), inline=True)
        embed.add_field(name="total messages", value=str(user["total_messages"]), inline=True)
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
            title="🔗 your personal invite link",
            description=f"**{invite_url}**\n\nshare this link! anyone who joins through it will count as your referral.",
            color=discord.Color.green(),
        )
        embed.add_field(name="current referrals", value=str(user["referrals"]), inline=True)

        next_level = user["level"] + 1
        if next_level in LEVEL_THRESHOLDS:
            refs_needed = LEVEL_THRESHOLDS[next_level]["referrals"]
            embed.add_field(
                name=f"referrals to {ROLE_NAMES.get(next_level, f'level {next_level}')}",
                value=f"{user['referrals']}/{refs_needed}",
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
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT referred_id, timestamp FROM referral_log WHERE referrer_id = %s ORDER BY timestamp DESC LIMIT 20",
            (user_id,),
        )
        rows = c.fetchall()
        conn.close()

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
            title=f"🎉 your referrals ({user['referrals']} total)",
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
        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        for i, u in enumerate(top):
            member = interaction.guild.get_member(u["user_id"])
            name = member.display_name if member else f"user {u['user_id']}"
            medal = medals.get(i, f"**{i+1}.**")
            role_name = ROLE_NAMES.get(u["level"], "unranked")
            lines.append(f"{medal} **{name}** | {u['xp']} xp | {u['referrals']} refs | {role_name}")

        embed = discord.Embed(
            title="🏆 leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"error in /leaderboard: {e}")
        await interaction.followup.send("something went wrong, check the logs!")


@bot.tree.command(name="setxp", description="(admin) set a user's xp manually")
@app_commands.describe(member="target user", xp="new xp value")
@app_commands.checks.has_permissions(administrator=True)
async def setxp(interaction: discord.Interaction, member: discord.Member, xp: int):
    await interaction.response.defer(ephemeral=True)
    try:
        user = get_user(member.id)
        new_level = calculate_level(xp, user["referrals"])
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
        new_level = calculate_level(user["xp"], referrals)
        update_user(member.id, referrals=referrals, level=new_level)
        await sync_roles(member, new_level)
        await interaction.followup.send(
            f"set **{member.display_name}**'s referrals to {referrals} (level {new_level})"
        )
    except Exception as e:
        print(f"error in /setreferrals: {e}")
        await interaction.followup.send(f"error: {e}")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(TOKEN)