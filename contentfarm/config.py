"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    youtube_api_key: str | None
    reddit_client_id: str | None
    reddit_client_secret: str | None
    reddit_user_agent: str
    x_bearer_token: str | None

    model: str
    hook_variations: int
    hook_gate_max_attempts: int
    line_gate_max_attempts: int


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        reddit_user_agent=os.getenv(
            "REDDIT_USER_AGENT", "contentfarm/0.1 by anonymous"
        ),
        x_bearer_token=os.getenv("X_BEARER_TOKEN"),
        model=os.getenv("CONTENTFARM_MODEL", "claude-opus-4-7"),
        hook_variations=_int_env("CONTENTFARM_HOOK_VARIATIONS", 4),
        hook_gate_max_attempts=_int_env("CONTENTFARM_HOOK_GATE_MAX_ATTEMPTS", 3),
        line_gate_max_attempts=_int_env("CONTENTFARM_LINE_GATE_MAX_ATTEMPTS", 3),
    )


SETTINGS = load_settings()
