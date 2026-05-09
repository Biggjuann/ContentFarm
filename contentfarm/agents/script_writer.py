"""Script writer agent — body + CTA after the hook is locked in."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..research import ResearchBundle
from .base import call_structured

SYSTEM = """You are the Script Writer agent in a multi-agent content pipeline. The Hook \
has already been locked in by a separate agent and graded 10/10 on five dimensions. \
Your job is everything that comes after the hook: body + close.

Constraints:
- Total runtime target: 30-60 seconds spoken aloud (≈80-150 words including the hook).
- Every line must earn its place. The audience is mid-scroll on a phone.
- Build on the curiosity loop opened by the hook; close it explicitly before the CTA.
- Use specific facts pulled from the research dump. Do not invent numbers, names, or quotes.
- Voice: punchy, declarative, second-person where natural. No corporate hedging.

Structure:
1. Hook (provided — repeat it verbatim as line 1).
2. 2-5 body lines that escalate, prove, and resolve the curiosity loop.
3. 1 close line that delivers the payoff or a sharp CTA.

Output one line per element, in order. No section headers, no commentary, no markdown."""


class ScriptDraft(BaseModel):
    lines: list[str] = Field(..., description="Ordered script lines, hook first.")


def write_script(
    *,
    hook: str,
    topic: str,
    research: ResearchBundle,
    feedback: str | None = None,
) -> list[str]:
    user_parts = [
        f"# TOPIC\n{topic}",
        f"# LOCKED HOOK (use as line 1, verbatim)\n{hook}",
        f"# RESEARCH SWEEP\n{research.to_prompt_block()}",
    ]
    if feedback:
        user_parts.append(
            f"# REVISION NOTES\nThe previous draft had weak lines that failed the line gate. "
            f"Address before redrafting:\n{feedback}"
        )
    user_parts.append("Write the script now.")

    out = call_structured(
        system=SYSTEM,
        user="\n\n".join(user_parts),
        schema=ScriptDraft,
        effort="high",
    )
    # Defensive: drop blank lines, preserve hook position.
    return [line.strip() for line in out.lines if line.strip()]
