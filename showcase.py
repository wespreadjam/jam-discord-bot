import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import discord
from aiohttp import web
from elasticsearch import Elasticsearch, NotFoundError


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"

SHOWCASE_TITLE = os.getenv("SHOWCASE_TITLE", "Jam Project Showcase").strip() or "Jam Project Showcase"
SHOWCASE_CHANNEL_NAMES = [
    part.strip().lower().lstrip("#")
    for part in os.getenv("SHOWCASE_CHANNEL_NAMES", "projects").split(",")
    if part.strip()
]
SHOWCASE_CHANNEL_SET = set(SHOWCASE_CHANNEL_NAMES or ["projects"])
SHOWCASE_ROUTE_PREFIX = os.getenv("SHOWCASE_ROUTE_PREFIX", "/showcase").strip() or "/showcase"
if not SHOWCASE_ROUTE_PREFIX.startswith("/"):
    SHOWCASE_ROUTE_PREFIX = f"/{SHOWCASE_ROUTE_PREFIX}"
SHOWCASE_ROUTE_PREFIX = SHOWCASE_ROUTE_PREFIX.rstrip("/") or "/showcase"
SHOWCASE_APP_URL = os.getenv("SHOWCASE_APP_URL", "").rstrip("/")
SHOWCASE_ACCESS_TOKEN = os.getenv("SHOWCASE_ACCESS_TOKEN", "")
SHOWCASE_SYNC_ON_START = os.getenv("SHOWCASE_SYNC_ON_START", "false").strip().lower() in {"1", "true", "yes", "on"}

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "").strip()
ELASTICSEARCH_API_KEY = os.getenv("ELASTICSEARCH_API_KEY", "").strip()
ELASTICSEARCH_USERNAME = os.getenv("ELASTICSEARCH_USERNAME", "").strip()
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD", "").strip()
ELASTICSEARCH_INDEX = os.getenv("ELASTICSEARCH_INDEX", "jam-project-showcase").strip() or "jam-project-showcase"

SHOWCASE_URL_RE = re.compile(r"https?://[^\s<>\"]+")
SHOWCASE_STOP_WORDS = {
    "about",
    "after",
    "also",
    "build",
    "building",
    "built",
    "check",
    "community",
    "demo",
    "discord",
    "from",
    "have",
    "here",
    "into",
    "just",
    "like",
    "project",
    "projects",
    "share",
    "showing",
    "some",
    "that",
    "this",
    "with",
    "work",
    "working",
}
SHOWCASE_SKIP_DOMAINS = {
    "discord.com",
    "discord.gg",
    "youtu.be",
    "youtube.com",
    "x.com",
    "twitter.com",
    "reddit.com",
    "instagram.com",
    "twitch.tv",
    "giphy.com",
    "tenor.com",
    "imgur.com",
    "gist.github.com",
}
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif")

_bot: discord.Client | None = None
_client: Elasticsearch | None = None


def configure_showcase(discord_bot: discord.Client):
    global _bot
    _bot = discord_bot


def showcase_enabled() -> bool:
    return bool(ELASTICSEARCH_URL)


def should_sync_on_start() -> bool:
    return showcase_enabled() and SHOWCASE_SYNC_ON_START


def get_showcase_route(guild_id: int | None = None) -> str:
    base = SHOWCASE_APP_URL or SHOWCASE_ROUTE_PREFIX
    if guild_id is None:
        return base
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}guild_id={guild_id}"


def _json_response(payload: dict[str, Any], *, status: int = 200) -> web.Response:
    return web.json_response(
        payload,
        status=status,
        headers={"Access-Control-Allow-Origin": "*"},
    )


def _normalize_channel_name(name: str | None) -> str:
    return (name or "").strip().lower().lstrip("#")


def _collapse_whitespace(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _clean_url(value: str) -> str:
    return value.rstrip(".,);]>")


def _extract_urls_from_text(value: str | None) -> list[str]:
    return [_clean_url(match) for match in SHOWCASE_URL_RE.findall(value or "")]


def _extract_urls_from_message(message: discord.Message) -> list[str]:
    urls = _extract_urls_from_text(message.content)
    for embed in message.embeds:
        for value in (embed.url, embed.title, embed.description):
            if isinstance(value, str):
                urls.extend(_extract_urls_from_text(value))
        for field in embed.fields:
            urls.extend(_extract_urls_from_text(f"{field.name} {field.value}"))
    return _dedupe_preserve_order(urls)


def _normalized_domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _normalize_github_repo_url(url: str) -> str | None:
    if _normalized_domain(url) != "github.com":
        return None
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) < 2:
        return None
    return f"https://github.com/{parts[0]}/{parts[1]}"


def _is_skipped_demo_url(url: str) -> bool:
    domain = _normalized_domain(url)
    return domain in SHOWCASE_SKIP_DOMAINS or domain.endswith(".discord.com")


def _project_channel_name(message: discord.Message) -> str:
    channel = message.channel
    if isinstance(channel, discord.Thread) and channel.parent:
        return _normalize_channel_name(channel.parent.name)
    return _normalize_channel_name(getattr(channel, "name", ""))


def _derive_summary(message: discord.Message) -> str:
    raw_parts = [message.content or ""]
    for embed in message.embeds:
        if embed.description:
            raw_parts.append(embed.description)
    combined = " ".join(part for part in raw_parts if part)
    combined = SHOWCASE_URL_RE.sub("", combined)
    summary = _collapse_whitespace(combined)
    if len(summary) > 320:
        return f"{summary[:317].rstrip()}..."
    return summary


def _prettify_repo_name(url: str) -> str:
    repo_name = url.rstrip("/").split("/")[-1]
    return repo_name.replace("-", " ").replace("_", " ").title()


def _derive_project_name(
    message: discord.Message,
    summary: str,
    github_url: str | None,
) -> str:
    for embed in message.embeds:
        title = _collapse_whitespace(embed.title)
        if len(title) >= 4:
            return title[:80]

    if github_url:
        return _prettify_repo_name(github_url)[:80]

    for line in (message.content or "").splitlines():
        cleaned_line = SHOWCASE_URL_RE.sub("", line)
        cleaned_line = re.sub(r"[`*_>#-]+", " ", cleaned_line)
        cleaned_line = _collapse_whitespace(cleaned_line)
        if len(cleaned_line) >= 4:
            return cleaned_line[:80]

    if summary:
        return summary[:80]

    author_name = getattr(message.author, "display_name", None) or getattr(message.author, "name", "Unknown")
    return f"Project from {author_name}"[:80]


def _derive_keywords(project_name: str, summary: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9\-\+]{2,}", f"{project_name} {summary}".lower())
    keywords: list[str] = []
    for word in words:
        if word in SHOWCASE_STOP_WORDS:
            continue
        if word not in keywords:
            keywords.append(word)
        if len(keywords) >= 8:
            break
    return keywords


def _derive_project_key(author_id: int, project_name: str, github_url: str | None, demo_url: str | None) -> str:
    if github_url:
        return f"github:{github_url.lower()}"
    if demo_url:
        return f"demo:{demo_url.lower()}"
    slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-") or "untitled"
    return f"author:{author_id}:{slug}"


def _is_image_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(IMAGE_EXTENSIONS)


def _preview_image_url(attachment_urls: list[str]) -> str | None:
    for url in attachment_urls:
        if _is_image_url(url):
            return url
    return None


def _build_document(message: discord.Message) -> dict[str, Any] | None:
    channel_name = _project_channel_name(message)
    if channel_name not in SHOWCASE_CHANNEL_SET:
        return None

    urls = _extract_urls_from_message(message)
    github_url = next((candidate for candidate in (_normalize_github_repo_url(url) for url in urls) if candidate), None)
    demo_url = next(
        (url for url in urls if url != github_url and not _is_skipped_demo_url(url) and _normalize_github_repo_url(url) is None),
        None,
    )
    attachment_urls = _dedupe_preserve_order(
        [attachment.url for attachment in message.attachments if getattr(attachment, "url", None)]
    )
    summary = _derive_summary(message)
    if not github_url and not demo_url and not attachment_urls and len(summary) < 24:
        return None

    author_name = getattr(message.author, "display_name", None) or getattr(message.author, "global_name", None) or message.author.name
    author_avatar = None
    if getattr(message.author, "display_avatar", None):
        author_avatar = str(message.author.display_avatar.url)

    project_name = _derive_project_name(message, summary, github_url)
    keywords = _derive_keywords(project_name, summary)
    created_at = message.created_at.timestamp()
    project_key = _derive_project_key(message.author.id, project_name, github_url, demo_url)

    return {
        "message_id": str(message.id),
        "project_key": project_key,
        "guild_id": str(message.guild.id if message.guild else 0),
        "guild_name": message.guild.name if message.guild else "Unknown Guild",
        "channel_id": str(getattr(message.channel, "id", 0)),
        "channel_name": channel_name,
        "author_id": str(message.author.id),
        "author_name": author_name,
        "author_username": message.author.name,
        "author_avatar_url": author_avatar,
        "project_name": project_name,
        "summary": summary,
        "message_content": _collapse_whitespace(message.content),
        "github_url": github_url,
        "demo_url": demo_url,
        "source_url": message.jump_url,
        "attachment_urls": attachment_urls,
        "preview_image_url": _preview_image_url(attachment_urls),
        "extra_urls": [url for url in urls if url not in {github_url, demo_url}],
        "keywords": keywords,
        "created_at": created_at,
    }


def _get_client() -> Elasticsearch | None:
    global _client
    if not showcase_enabled():
        return None
    if _client is not None:
        return _client

    kwargs: dict[str, Any] = {}
    if ELASTICSEARCH_API_KEY:
        kwargs["api_key"] = ELASTICSEARCH_API_KEY
    elif ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
        kwargs["basic_auth"] = (ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD)

    _client = Elasticsearch(ELASTICSEARCH_URL, **kwargs)
    return _client


def init_showcase_index():
    client = _get_client()
    if client is None:
        return
    if client.indices.exists(index=ELASTICSEARCH_INDEX):
        return

    client.indices.create(
        index=ELASTICSEARCH_INDEX,
        mappings={
            "properties": {
                "message_id": {"type": "keyword"},
                "project_key": {"type": "keyword"},
                "guild_id": {"type": "keyword"},
                "guild_name": {"type": "keyword"},
                "channel_id": {"type": "keyword"},
                "channel_name": {"type": "keyword"},
                "author_id": {"type": "keyword"},
                "author_name": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                "author_username": {"type": "keyword"},
                "author_avatar_url": {"type": "keyword", "ignore_above": 2048},
                "project_name": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                "summary": {"type": "text"},
                "message_content": {"type": "text"},
                "github_url": {"type": "keyword", "ignore_above": 2048},
                "demo_url": {"type": "keyword", "ignore_above": 2048},
                "source_url": {"type": "keyword", "ignore_above": 2048},
                "attachment_urls": {"type": "keyword", "ignore_above": 2048},
                "preview_image_url": {"type": "keyword", "ignore_above": 2048},
                "extra_urls": {"type": "keyword", "ignore_above": 2048},
                "keywords": {"type": "keyword"},
                "created_at": {"type": "date", "format": "epoch_second"},
            }
        },
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
    )


def index_showcase_document(message: discord.Message) -> bool:
    client = _get_client()
    if client is None:
        return False

    document = _build_document(message)
    if document is None:
        return False

    client.index(index=ELASTICSEARCH_INDEX, id=str(message.id), document=document, refresh=False)
    return True


def delete_showcase_document(message_id: int):
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(index=ELASTICSEARCH_INDEX, id=str(message_id), refresh=False)
    except NotFoundError:
        return


async def upsert_showcase_message(message: discord.Message) -> bool:
    return index_showcase_document(message)


async def sync_showcase_for_guild(guild: discord.Guild, limit: int | None = None) -> dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"enabled": False, "scanned": 0, "indexed": 0, "channels": 0, "missing": list(SHOWCASE_CHANNEL_SET)}

    init_showcase_index()

    scanned = 0
    indexed = 0
    matched_channels = [channel for channel in guild.text_channels if _normalize_channel_name(channel.name) in SHOWCASE_CHANNEL_SET]
    missing = sorted(name for name in SHOWCASE_CHANNEL_SET if name not in {_normalize_channel_name(channel.name) for channel in matched_channels})

    for channel in matched_channels:
        try:
            async for message in channel.history(limit=limit, oldest_first=False):
                scanned += 1
                if index_showcase_document(message):
                    indexed += 1
        except discord.Forbidden:
            missing.append(channel.name)

    return {
        "enabled": True,
        "scanned": scanned,
        "indexed": indexed,
        "channels": len(matched_channels),
        "missing": sorted(set(missing)),
    }


def _build_search_query(request: web.Request) -> tuple[dict[str, Any], int]:
    q = request.query.get("q", "").strip()
    guild_id = request.query.get("guild_id", "").strip()
    channel = _normalize_channel_name(request.query.get("channel"))
    author = request.query.get("author", "").strip()
    try:
        size = min(max(int(request.query.get("size", "48")), 1), 96)
    except ValueError:
        size = 48
    has_github = request.query.get("has_github", "").lower() in {"1", "true", "yes"}
    has_demo = request.query.get("has_demo", "").lower() in {"1", "true", "yes"}

    filters: list[dict[str, Any]] = []
    if guild_id:
        filters.append({"term": {"guild_id": guild_id}})
    if channel:
        filters.append({"term": {"channel_name": channel}})
    if author:
        filters.append({"term": {"author_name.keyword": author}})
    if has_github:
        filters.append({"exists": {"field": "github_url"}})
    if has_demo:
        filters.append({"exists": {"field": "demo_url"}})

    if q:
        query: dict[str, Any] = {
            "bool": {
                "filter": filters,
                "must": [
                    {
                        "bool": {
                            "should": [
                                {
                                    "multi_match": {
                                        "query": q,
                                        "fields": ["project_name^4", "summary^2", "message_content", "author_name^2", "keywords^3"],
                                        "type": "best_fields",
                                    }
                                },
                                {
                                    "multi_match": {
                                        "query": q,
                                        "fields": ["project_name^5", "author_name^3"],
                                        "type": "phrase_prefix",
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                ],
            }
        }
        sort = [{"_score": {"order": "desc"}}, {"created_at": {"order": "desc"}}]
    else:
        query = {"bool": {"filter": filters}}
        sort = [{"created_at": {"order": "desc"}}]

    body = {
        "size": size,
        "query": query,
        "sort": sort,
        "collapse": {"field": "project_key"},
        "aggs": {
            "unique_projects": {"cardinality": {"field": "project_key"}},
            "builders": {"cardinality": {"field": "author_id"}},
            "channels": {"terms": {"field": "channel_name", "size": 25}},
            "authors": {"terms": {"field": "author_name.keyword", "size": 100}},
            "guilds": {"terms": {"field": "guild_name", "size": 10}},
            "with_github": {"filter": {"exists": {"field": "github_url"}}},
            "with_demo": {"filter": {"exists": {"field": "demo_url"}}},
        },
    }
    return body, size


def _authorized(request: web.Request) -> bool:
    if not SHOWCASE_ACCESS_TOKEN:
        return True
    provided = request.query.get("token", "")
    return bool(provided) and provided == SHOWCASE_ACCESS_TOKEN


async def showcase_search_handler(request: web.Request) -> web.Response:
    if not _authorized(request):
        return _json_response({"error": "Unauthorized"}, status=401)

    client = _get_client()
    if client is None:
        return _json_response(
            {"error": "Showcase search is disabled. Set ELASTICSEARCH_URL to enable it."},
            status=503,
        )

    init_showcase_index()
    body, size = _build_search_query(request)
    response = client.search(index=ELASTICSEARCH_INDEX, body=body)

    hits = response["hits"]["hits"]
    projects = []
    for hit in hits:
        source = hit["_source"]
        projects.append(
            {
                "id": source["message_id"],
                "projectKey": source["project_key"],
                "projectName": source["project_name"],
                "summary": source.get("summary", ""),
                "authorName": source["author_name"],
                "authorUsername": source.get("author_username", ""),
                "authorAvatarUrl": source.get("author_avatar_url"),
                "channelName": source["channel_name"],
                "guildId": source["guild_id"],
                "guildName": source["guild_name"],
                "githubUrl": source.get("github_url"),
                "demoUrl": source.get("demo_url"),
                "sourceUrl": source["source_url"],
                "attachmentUrls": source.get("attachment_urls", []),
                "previewImageUrl": source.get("preview_image_url"),
                "keywords": source.get("keywords", []),
                "createdAt": source["created_at"],
                "score": hit.get("_score"),
            }
        )

    aggs = response.get("aggregations", {})
    return _json_response(
        {
            "title": SHOWCASE_TITLE,
            "results": projects,
            "meta": {
                "size": size,
                "stats": {
                    "projects": int(aggs.get("unique_projects", {}).get("value", len(projects))),
                    "builders": int(aggs.get("builders", {}).get("value", 0)),
                    "githubProjects": int(aggs.get("with_github", {}).get("doc_count", 0)),
                    "demoProjects": int(aggs.get("with_demo", {}).get("doc_count", 0)),
                },
                "filters": {
                    "channels": [bucket["key"] for bucket in aggs.get("channels", {}).get("buckets", [])],
                    "authors": [bucket["key"] for bucket in aggs.get("authors", {}).get("buckets", [])],
                    "guilds": [bucket["key"] for bucket in aggs.get("guilds", {}).get("buckets", [])],
                },
            },
        }
    )


async def showcase_health_handler(request: web.Request) -> web.Response:
    if not _authorized(request):
        return _json_response({"error": "Unauthorized"}, status=401)

    client = _get_client()
    if client is None:
        return _json_response({"enabled": False, "reason": "ELASTICSEARCH_URL is not configured"})

    init_showcase_index()
    count_response = client.count(index=ELASTICSEARCH_INDEX)
    return _json_response(
        {
            "enabled": True,
            "index": ELASTICSEARCH_INDEX,
            "documents": count_response.get("count", 0),
            "channels": sorted(SHOWCASE_CHANNEL_SET),
            "route": SHOWCASE_ROUTE_PREFIX,
        }
    )


async def showcase_index_handler(request: web.Request) -> web.Response:
    if not _authorized(request):
        return web.Response(text="Unauthorized", status=401)
    if not FRONTEND_DIST_DIR.exists():
        return web.Response(
            text="Frontend build not found. Run `npm --prefix frontend run build` to generate frontend/dist.",
            status=503,
        )
    return web.FileResponse(FRONTEND_DIST_DIR / "index.html")


def register_showcase_routes(app: web.Application):
    app.router.add_get("/api/showcase/search", showcase_search_handler)
    app.router.add_get("/api/showcase/health", showcase_health_handler)
    if FRONTEND_DIST_DIR.exists():
        assets_dir = FRONTEND_DIST_DIR / "assets"
        if assets_dir.exists():
            app.router.add_static("/assets", str(assets_dir))
        app.router.add_get(SHOWCASE_ROUTE_PREFIX, showcase_index_handler)
        app.router.add_get(f"{SHOWCASE_ROUTE_PREFIX}/{{tail:.*}}", showcase_index_handler)
