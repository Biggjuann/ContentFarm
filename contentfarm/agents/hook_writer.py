"""Hook writer agent — generates N hook variations from research + proven patterns."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..config import SETTINGS
from ..research import ResearchBundle
from .base import call_structured
from .proven_hooks import as_inspiration_block

SYSTEM = """You are the Hook Writer agent in a multi-agent content pipeline that produces \
short-form video scripts (30-60 seconds, vertical, scroll-stopping).

Your single job: write {n} different hook variations for the assigned topic.

A hook is the first 1-2 lines of the script. Its only job is to make a scrolling viewer \
stop and watch the next 3 seconds. Nothing else matters.

You will be given:
1. The topic.
2. A research dump from YouTube, Reddit, and X — this is the truth of what real people \
   are saying, fighting about, and watching about this topic. Use it. Pull specifics \
   from it. Do not invent numbers or quotes.
3. A library of proven hook patterns — use them as scaffolds, not templates.

Constraints for each hook:
- Maximum 25 words.
- Concrete, not abstract. Numbers, names, specifics.
- Open a curiosity loop the body has to close.
- No hedging language ("maybe", "perhaps", "might"). No filler ("In this video…").
- Each variation must use a *distinctly different* angle / pattern from the others.

Return only the structured output."""


class HookVariation(BaseModel):
    text: str = Field(..., description="The hook itself, 25 words max.")
    angle: str = Field(..., description="The pattern this hook uses (e.g. 'contrarian truth').")
    intended_emotion: str = Field(..., description="The single emotion the viewer should feel in the first 2 seconds.")
    research_sources: list[str] = Field(
        default_factory=list,
        description="Which research items inspired this (e.g. 'reddit:r/entrepreneur top comment').",
    )


class HookWriterOutput(BaseModel):
    variations: list[HookVariation]


def write_hooks(
    topic: str,
    research: ResearchBundle,
    n: int | None = None,
    feedback: str | None = None,
) -> list[HookVariation]:
    n = n or SETTINGS.hook_variations
    system = SYSTEM.format(n=n)

    user_parts = [
        f"# TOPIC\n{topic}",
        f"# RESEARCH SWEEP\n{research.to_prompt_block()}",
        f"# PROVEN HOOK PATTERNS\n{as_inspiration_block()}",
    ]
    if feedback:
        user_parts.append(
            f"# PRIOR ATTEMPT FAILED THE GATE\nThe previous batch was rejected. "
            f"Address the following feedback before writing the next batch:\n{feedback}"
        )
    user_parts.append(
        f"Write exactly {n} hook variations. Each must use a distinctly different angle."
    )

    out = call_structured(
        system=system,
        user="\n\n".join(user_parts),
        schema=HookWriterOutput,
        effort="high",
    )
    return out.variations
