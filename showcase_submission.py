import json
import os
import secrets
import time
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientSession, ClientTimeout
from cryptography.fernet import Fernet


SHOWCASE_SUBMISSION_API_URL = os.getenv("SHOWCASE_SUBMISSION_API_URL", "").strip()
SHOWCASE_SUBMISSION_FERNET_KEY = os.getenv("SHOWCASE_SUBMISSION_FERNET_KEY", "").strip()
SHOWCASE_SUBMISSION_BEARER_TOKEN = os.getenv("SHOWCASE_SUBMISSION_BEARER_TOKEN", "").strip()
SHOWCASE_PUBLIC_URL = os.getenv("SHOWCASE_PUBLIC_URL", "").strip()
SHOWCASE_SOURCE = os.getenv("SHOWCASE_SOURCE", "jam-discord-bot").strip() or "jam-discord-bot"
SHOWCASE_KEY_ID = os.getenv("SHOWCASE_KEY_ID", "").strip()

try:
    SHOWCASE_REQUEST_TIMEOUT_SECONDS = float(
        os.getenv("SHOWCASE_REQUEST_TIMEOUT_SECONDS", "10").strip() or "10"
    )
except ValueError:
    SHOWCASE_REQUEST_TIMEOUT_SECONDS = 10.0


def showcase_submission_enabled() -> bool:
    return bool(SHOWCASE_SUBMISSION_API_URL and SHOWCASE_SUBMISSION_FERNET_KEY)


def get_showcase_public_url() -> str:
    return SHOWCASE_PUBLIC_URL


def parse_showcase_tags(raw_value: str) -> list[str]:
    tags: list[str] = []
    for piece in raw_value.replace("\n", ",").split(","):
        cleaned = piece.strip().lower()
        if cleaned and cleaned not in tags:
            tags.append(cleaned)
    return tags[:10]


def is_valid_showcase_url(raw_value: str) -> bool:
    parsed = urlparse(raw_value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _fernet_client() -> Fernet:
    if not SHOWCASE_SUBMISSION_FERNET_KEY:
        raise ValueError("SHOWCASE_SUBMISSION_FERNET_KEY is not configured")
    return Fernet(SHOWCASE_SUBMISSION_FERNET_KEY.encode("utf-8"))


def build_showcase_payload(
    *,
    guild_id: int,
    guild_name: str,
    channel_id: int,
    channel_name: str,
    user_id: int,
    username: str,
    display_name: str,
    avatar_url: str | None,
    project_name: str,
    description: str,
    github_url: str | None,
    live_url: str | None,
    tags: list[str],
) -> dict[str, Any]:
    return {
        "version": 1,
        "request_id": secrets.token_hex(16),
        "submitted_at": int(time.time()),
        "source": SHOWCASE_SOURCE,
        "guild": {
            "id": str(guild_id),
            "name": guild_name,
        },
        "channel": {
            "id": str(channel_id),
            "name": channel_name,
        },
        "member": {
            "id": str(user_id),
            "username": username,
            "display_name": display_name,
            "avatar_url": avatar_url,
        },
        "project": {
            "name": project_name,
            "description": description,
            "github_url": github_url,
            "live_url": live_url,
            "tags": tags,
        },
    }


def encrypt_showcase_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return _fernet_client().encrypt(serialized).decode("utf-8")


async def submit_showcase_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not SHOWCASE_SUBMISSION_API_URL:
        raise ValueError("SHOWCASE_SUBMISSION_API_URL is not configured")

    encrypted_payload = encrypt_showcase_payload(payload)
    body = {
        "version": 1,
        "source": SHOWCASE_SOURCE,
        "payload": encrypted_payload,
    }

    headers = {
        "Content-Type": "application/json",
    }
    request_id = payload.get("request_id")
    if request_id:
        headers["X-Showcase-Request-Id"] = str(request_id)
    if SHOWCASE_SUBMISSION_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {SHOWCASE_SUBMISSION_BEARER_TOKEN}"
    if SHOWCASE_KEY_ID:
        headers["X-Showcase-Key-Id"] = SHOWCASE_KEY_ID

    timeout = ClientTimeout(total=max(SHOWCASE_REQUEST_TIMEOUT_SECONDS, 1.0))
    async with ClientSession(timeout=timeout) as session:
        async with session.post(SHOWCASE_SUBMISSION_API_URL, json=body, headers=headers) as response:
            response_text = await response.text()
            if response.status >= 400:
                raise RuntimeError(
                    f"showcase api returned {response.status}: {response_text[:300]}"
                )

            if not response_text.strip():
                return {}

            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError:
                return {"raw_response": response_text}

            if isinstance(parsed, dict):
                return parsed

            return {"data": parsed}
