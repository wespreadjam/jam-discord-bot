<div align="center">

# jam bot

<img src="https://img.shields.io/badge/jam-discord%20bot-ff6b6b?style=for-the-badge&logo=discord&logoColor=white" alt="jam discord bot"/>

<br/>

[![discord](https://img.shields.io/discord/1234567890?label=join%20the%20jam&logo=discord&logoColor=white&color=5865F2&style=flat-square)](https://discord.gg/5sdGUP4pG5)
[![python](https://img.shields.io/badge/python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3.0+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![postgres](https://img.shields.io/badge/postgresql-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![license](https://img.shields.io/github/license/wespreadjam/jam-discord-bot?style=flat-square&color=ff6b6b)](LICENSE)

[![github stars](https://img.shields.io/github/stars/wespreadjam/jam-discord-bot?style=flat-square&logo=github&color=ffdd57)](https://github.com/wespreadjam/jam-discord-bot)
[![last commit](https://img.shields.io/github/last-commit/wespreadjam/jam-discord-bot?style=flat-square&color=a8e6cf)](https://github.com/wespreadjam/jam-discord-bot)
[![repo size](https://img.shields.io/github/repo-size/wespreadjam/jam-discord-bot?style=flat-square&color=dcd0ff)](https://github.com/wespreadjam/jam-discord-bot)
[![code lines](https://img.shields.io/badge/lines%20of%20code-1017-f9a8d4?style=flat-square)](https://github.com/wespreadjam/jam-discord-bot)

<br/>

*a community engagement bot with referrals, levels, and more fun easter eggs*

[join the discord](https://discord.gg/5sdGUP4pG5) · [report a bug](https://github.com/wespreadjam/jam-discord-bot/issues) · [request a feature](https://github.com/wespreadjam/jam-discord-bot/issues)

</div>

---

## what is jam bot?

jam bot is a discord bot that gamifies your community. it tracks messages, awards xp, manages referrals, and hands out jam-themed roles as members level up. 

it also handles onboarding. new members have to introduce themselves and share a project before they get verified. no lurkers allowed (well, fewer lurkers).

## how it works

```
message sent → xp awarded → level up → jam role assigned → announced to the server
```

every message earns **10 xp** (with a 60-second cooldown so you can't spam your way to the top). longer messages (50+ chars) earn a **5 xp bonus**. refer a friend and get **50 xp** on top of that.

## the jam tier system

| level | role | xp needed |
|:---:|---|---:|
| 1 | strawberry jam | 100 |
| 2 | blueberry jam | 500 |
| 3 | golden jam | 1,500 |
| 4 | diamond jam | 8,000 |
| 5 | platinum jam | 15,000 |
| 6 | infinity jam | 25,000 |

## commands

| command | what it does |
|---|---|
| `/rank` | check your xp, level, referrals, and message count |
| `/mylink` | get your personal referral invite link |
| `/myreferrals` | see everyone you've referred |
| `/leaderboard` | top 10 members by xp |
| `/ref-leaderboard` | top 10 members by referrals |
| `/joined` | check when a member joined the server |
| `/serverinfo` | display server stats (members, channels, boosts, and more) |
| `/countdown` | start a countdown embed to an upcoming event |
| `/bread` | receive a random bread blessing |
| `/am-i-jam` | deep philosophical question |
| `/link-github` | link your github account to be tagged in PR merges |

### admin commands

| command | what it does |
|---|---|
| `/setxp` | manually set a user's xp |
| `/setreferrals` | manually set a user's referral count |
| `/setup-welcome` | post welcome embeds to a channel |
| `/test-welcome` | dm yourself the welcome message |

## referral tracking

jam bot gives every member a personal invite link they can share. when someone joins through that link, the referrer gets credit and **50 xp**.

### how it works

```
member runs /mylink → gets personal invite link → shares it → new member joins
→ bot detects which invite was used → credits the referrer → awards 50 xp
→ announces it to the server
```

1. **invite creation** — when a member runs `/mylink`, the bot creates a permanent discord invite tied to their account and stores the link in the database. if they already have one, it reuses it.
2. **join detection** — the bot caches all invite use counts. when a new member joins, it compares the cached counts to the current counts to figure out which invite was used.
3. **referrer lookup** — the bot checks the `invite_owners` table to find who owns the invite. if the invite wasn't created through `/mylink`, it falls back to discord's built-in invite creator field.
4. **reward & announce** — the referrer's referral count goes up by 1, they get 50 xp, and the bot posts a message in the configured channel (defaults to #commands). if the xp pushes them to a new level, that gets announced too.
5. **duplicate prevention** — each referred member can only count once. if someone leaves and rejoins through the same link, it won't double-count.

### referral commands

| command | what it does |
|---|---|
| `/mylink` | get your personal referral invite link + see your referral stats |
| `/myreferrals` | see the list of people you've referred (up to 20 most recent) |
| `/ref-leaderboard` | top 10 members ranked by referral count |
| `/setreferrals` | (admin) manually set a user's referral count |

### database

referrals are tracked across three postgres tables:

- **`users`** — stores each member's total referral count alongside their xp and level
- **`referral_log`** — records every referral (who referred whom and when), with a unique constraint on the referred member to prevent duplicates
- **`invite_owners`** — maps invite codes to the members who created them

## fun / useless commands

not everything has to be productive. these do nothing useful and that's the point.

### `/bread`

receive a random bread blessing. there are 15 possible outcomes, including:

- *a warm loaf of sourdough is given to you*
- *a tiny baguette rolls across the floor and stops at your feet*
- *a mysterious bread fairy delivers a pretzel to you*
- *the universe grants you a single, perfect slice of milk bread*

### `/am-i-jam`

ask the bot a deep philosophical question about whether you are jam. it will respond with one of two possible answers. neither of them actually answers the question.

### `/8ball`

a magic 8-ball with 20 possible responses — some positive, some uncertain, some negative. a few are on-brand: "bread says yes", "jam is confused, ask later", "bread says no". takes a question as input and returns its wisdom in a purple embed.

## features

- **xp & leveling** — message-based xp with cooldowns, bonus xp for longer messages, automatic role assignment
- **referral tracking** — personal invite links, referral credit with xp rewards, persistent tracking via database
- **onboarding gate** — new members must post in #intros and #projects to get verified
- **thread management** — auto-archives threads in specified channels to keep things tidy
- **welcome system** — dms new members with onboarding info and their personal referral link
- **server info** — rich embed showing member counts, channel breakdown, boost level, roles, and creation date
- **event countdowns** — post a live countdown embed for any upcoming event using discord's dynamic timestamps
- **github webhooks** — automatically announce merged PRs to a channel and ping the author

## setup

### prerequisites

- python 3.11+
- a postgresql database
- a discord bot token from the [developer portal](https://discord.com/developers/applications)

### install

```bash
git clone https://github.com/wespreadjam/jam-discord-bot.git
cd jam-discord-bot
pip install -r requirements.txt
```

### environment variables

```env
DISCORD_BOT_TOKEN=your_bot_token_here
DATABASE_URL=your_postgres_connection_string
GITHUB_WEBHOOK_SECRET=your_secure_random_string
PR_ANNOUNCEMENT_CHANNEL_NAME=testing-announcements
```

### server setup

create these roles in your discord server:
> strawberry jam · blueberry jam · golden jam · diamond jam · platinum jam · infinity jam · verified

create these channels:
> #intros · #projects · #commands

### run

```bash
python bot.py
```

then run `/setup-welcome` in any channel to post the welcome embeds.

### deploy

the bot runs a built-in web server to listen for GitHub webhooks, so it includes a `Procfile` for easy deployment to railway or heroku. Note that it runs as a `web` process to expose the port correctly:

```
web: python bot.py
```

on railway, the `DATABASE_URL` is set automatically when you add the postgres plugin.

## tech stack

| | |
|---|---|
| language | python |
| framework | discord.py |
| database | postgresql |
| hosting | railway / heroku |

## credits

credits to **hassan2bit bread** on discord for naming infinity jam

---

<div align="center">

**[join the jam discord](https://discord.gg/5sdGUP4pG5)**

-jia 

</div>
