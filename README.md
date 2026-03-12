<div align="center">

# jam bot

<img src="https://img.shields.io/badge/jam-discord%20bot-ff6b6b?style=for-the-badge&logo=discord&logoColor=white" alt="jam discord bot"/>

<br/>

[![discord](https://img.shields.io/discord/1234567890?label=join%20the%20jam&logo=discord&logoColor=white&color=5865F2&style=flat-square)](https://discord.gg/5sdGUP4pG5)
[![python](https://img.shields.io/badge/python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3.0+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![postgres](https://img.shields.io/badge/postgresql-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)

*a community engagement bot with referrals, levels, onboarding, github webhooks, and a searchable project showcase*

[join the discord](https://discord.gg/5sdGUP4pG5) · [report a bug](https://github.com/wespreadjam/jam-discord-bot/issues) · [request a feature](https://github.com/wespreadjam/jam-discord-bot/issues)

</div>

---

## what is jam bot?

jam bot is a discord bot that gamifies your community. it tracks messages, awards xp, manages referrals, and hands out jam-themed roles as members level up.

it also handles onboarding. new members have to introduce themselves and share a project before they get verified. no lurkers allowed.

it now also indexes your showcase channels into elasticsearch and powers a searchable project dashboard.

## how it works

```text
message sent -> xp awarded -> level up -> jam role assigned -> announced to the server
```

every message earns **10 xp** with a 60-second cooldown to prevent spam. messages with 50+ characters earn a **5 xp bonus**. referrals add **50 xp**.

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
| `/serverinfo` | display server stats |
| `/countdown` | post a countdown embed for an upcoming event |
| `/bread` | receive a random bread blessing |
| `/am-i-jam` | ask the bot a deeply important question |
| `/link-github` | link your github account to be tagged in merged PR announcements |
| `/showcase-link` | get the project showcase dashboard URL |

### admin commands

| command | what it does |
|---|---|
| `/setxp` | manually set a user's xp |
| `/setreferrals` | manually set a user's referral count |
| `/setup-welcome` | post the welcome embeds |
| `/test-welcome` | dm yourself the welcome message |
| `/sync-showcase` | backfill tracked showcase channels into elasticsearch |

## features

- xp and leveling with cooldowns, bonuses, and role assignment
- referral tracking with personal invite links
- onboarding gate for `#intros` and `#projects`
- auto-archiving for selected thread channels
- welcome dm flow for new members
- server info and countdown commands
- github webhook announcements with discord account linking
- elasticsearch-backed project showcase search

## project showcase search

the bot can scrape project posts from one or more configured channels, index them into elasticsearch, and expose:

- `GET /api/showcase/search` - elastic-backed search API
- `GET /api/showcase/health` - quick health and document count check
- `GET /showcase` - the built frontend dashboard when `frontend/dist` exists

### how it works

1. set `SHOWCASE_CHANNEL_NAMES` to the channels you want indexed.
2. configure your elasticsearch credentials.
3. run `/sync-showcase` once to backfill history.
4. keep the bot online so new project posts, edits, and deletes stay in sync.
5. build the frontend and visit `/showcase`, or deploy `frontend/` separately.

### what gets indexed

- project name inferred from the post or github repo
- summary text from the discord message
- github link
- live demo link
- source discord post url
- attachments and preview image
- builder name, username, and avatar
- guild and channel metadata

## setup

### prerequisites

- python 3.11+
- a postgresql database
- a discord bot token from the [developer portal](https://discord.com/developers/applications)
- an elasticsearch cluster if you want showcase search enabled

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

ELASTICSEARCH_URL=https://your-elastic-cluster.example.com
ELASTICSEARCH_API_KEY=your_api_key_here
# or:
# ELASTICSEARCH_USERNAME=elastic
# ELASTICSEARCH_PASSWORD=your_password_here
ELASTICSEARCH_INDEX=jam-project-showcase

SHOWCASE_CHANNEL_NAMES=projects
SHOWCASE_APP_URL=https://your-app.example.com/showcase
SHOWCASE_ROUTE_PREFIX=/showcase
SHOWCASE_ACCESS_TOKEN=optional_shared_secret
SHOWCASE_SYNC_ON_START=false
```

### server setup

create these roles in your discord server:

`strawberry jam`, `blueberry jam`, `golden jam`, `diamond jam`, `platinum jam`, `infinity jam`, `verified`

create these channels:

`#intros`, `#projects`, `#commands`

make sure the bot can:

- view channels
- read message history
- read message content
- send messages
- manage roles
- create invites

### run the bot

```bash
python bot.py
```

then run `/setup-welcome` in any channel to post the welcome embeds.

### frontend dashboard

```bash
cd frontend
npm install
npm run dev
```

set `VITE_SHOWCASE_API_BASE_URL` if you host the frontend separately from the bot API.

to let the bot serve the dashboard itself, build the frontend first:

```bash
npm --prefix frontend run build
```

that creates `frontend/dist`, which the bot serves at `/showcase`.

## deploy

the bot already runs a built-in web server for github webhooks and the showcase API. it includes a `Procfile` for platforms like railway or heroku:

```text
web: python bot.py
```

for same-origin showcase hosting, build the frontend during your deploy so `frontend/dist` exists at runtime.

## tech stack

| | |
|---|---|
| language | python |
| bot framework | discord.py |
| primary database | postgresql |
| search index | elasticsearch |
| frontend | react + typescript + vite + shadcn/ui |
| hosting | railway / heroku / separate static frontend |

## credits

credits to **hassan2bit bread** on discord for naming infinity jam.

---

<div align="center">

**[join the jam discord](https://discord.gg/5sdGUP4pG5)**

-jia

</div>
