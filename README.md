<div align="center">

# jam bot

<img src="https://img.shields.io/badge/jam-discord%20bot-ff6b6b?style=for-the-badge&logo=discord&logoColor=white" alt="jam discord bot"/>

<br/>

[![discord](https://img.shields.io/discord/1234567890?label=join%20the%20jam&logo=discord&logoColor=white&color=5865F2&style=flat-square)](https://discord.gg/5sdGUP4pG5)
[![python](https://img.shields.io/badge/python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3.0+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![postgres](https://img.shields.io/badge/postgresql-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)

*a community engagement bot with referrals, levels, onboarding, github webhooks, and project submissions*

[join the discord](https://discord.gg/5sdGUP4pG5) · [report a bug](https://github.com/wespreadjam/jam-discord-bot/issues) · [request a feature](https://github.com/wespreadjam/jam-discord-bot/issues)

</div>

---

## what is jam bot?

jam bot is a discord bot that gamifies your community. it tracks messages, awards xp, manages referrals, and hands out jam-themed roles as members level up.

it also handles onboarding. new members have to introduce themselves and share a project before they get verified. no lurkers allowed.

this version also includes `/showcase-project`, a slash command that opens a modal and sends an encrypted project submission to a separate showcase backend that you host elsewhere.

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
| `/link-github` | link your github account to merged PR announcements |
| `/showcase-project` | submit a project to the external showcase API |

### admin commands

| command | what it does |
|---|---|
| `/setxp` | manually set a user's xp |
| `/setreferrals` | manually set a user's referral count |
| `/setup-welcome` | post the welcome embeds |
| `/test-welcome` | dm yourself the welcome message |

## features

- xp and leveling with cooldowns, bonuses, and role assignment
- referral tracking with personal invite links
- onboarding gate for `#intros` and `#projects`
- auto-archiving for selected thread channels
- welcome dm flow for new members
- server info and countdown commands
- github webhook announcements with discord account linking
- encrypted project submissions to a separate showcase backend

## showcase submission flow

`/showcase-project` opens a modal with:

- project name
- short description
- github url
- live/demo url
- tags

when the user submits, the bot:

1. builds a structured payload with guild, channel, member, and project metadata
2. encrypts that payload with a shared Fernet key
3. sends it to your separate showcase API
4. returns an ephemeral confirmation to the member

this keeps the showcase UI and storage in a separate repo while making it easy for community members to submit projects from discord.

## showcase api contract

the bot sends a `POST` request to `SHOWCASE_SUBMISSION_API_URL` with:

```json
{
  "version": 1,
  "source": "jam-discord-bot",
  "payload": "gAAAAAB..."
}
```

headers:

- `Content-Type: application/json`
- `Authorization: Bearer ...` when `SHOWCASE_SUBMISSION_BEARER_TOKEN` is set
- `X-Showcase-Key-Id: ...` when `SHOWCASE_KEY_ID` is set
- `X-Showcase-Request-Id: ...` for request tracing

the `payload` field is a Fernet-encrypted JSON document containing guild, channel, member, and project metadata. the separate showcase backend should decrypt it with the shared key and can optionally return JSON like:

```json
{
  "submission_id": "abc123",
  "project_url": "https://your-showcase.example.com/projects/abc123"
}
```

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

SHOWCASE_SUBMISSION_API_URL=https://your-showcase-api.example.com/api/submissions
SHOWCASE_SUBMISSION_FERNET_KEY=your_fernet_key_here
SHOWCASE_SUBMISSION_BEARER_TOKEN=optional_api_bearer_token
SHOWCASE_PUBLIC_URL=https://your-showcase.example.com
SHOWCASE_SOURCE=jam-discord-bot
SHOWCASE_KEY_ID=primary
SHOWCASE_REQUEST_TIMEOUT_SECONDS=10
```

generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

the same key must be configured in your separate showcase backend so it can decrypt incoming submissions.

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

## deploy

the bot runs a built-in web server for github webhooks, so it includes a `Procfile` for platforms like railway or heroku:

```text
web: python bot.py
```

## tech stack

| | |
|---|---|
| language | python |
| bot framework | discord.py |
| database | postgresql |
| encryption | Fernet via `cryptography` |
| outbound showcase integration | encrypted HTTP POST to your separate showcase API |

## credits

credits to **hassan2bit bread** on discord for naming infinity jam.

---

<div align="center">

**[join the jam discord](https://discord.gg/5sdGUP4pG5)**

-jia

</div>
