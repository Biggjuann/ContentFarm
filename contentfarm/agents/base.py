"""Shared Anthropic client + structured-output helpers for every agent."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from ..config import SETTINGS

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    if not SETTINGS.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to the environment "
            "(or .env locally / Railway variables in production)."
        )
    return anthropic.Anthropic(api_key=SETTINGS.anthropic_api_key)


def call_structured(
    *,
    system: str,
    user: str,
    schema: type[T],
    effort: str = "high",
    max_tokens: int = 16_000,
    cache_system: bool = True,
) -> T:
    """Call Claude and parse a typed Pydantic response.

    Uses adaptive thinking + ephemeral cache on the system prompt so repeated
    calls (which is most of what the line-by-line critic does) stay cheap.
    """
    client = get_client()

    if cache_system:
        system_blocks = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system_blocks = system  # type: ignore[assignment]

    response = client.messages.parse(
        model=SETTINGS.model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        system=system_blocks,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )

    if response.parsed_output is None:
        raise RuntimeError(
            f"Claude returned no parseable output. stop_reason={response.stop_reason}"
        )
    return response.parsed_output
