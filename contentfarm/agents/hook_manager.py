"""Hook manager — scores each hook on 5 dimensions and gates at 10/10 each."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .base import call_structured
from .hook_writer import HookVariation

DIMENSIONS = [
    ("scroll_stop", "Will a viewer mid-scroll physically stop in the first ~0.5s?"),
    ("curiosity_gap", "Does it open a loop that demands the next sentence?"),
    ("specificity", "Are claims concrete (numbers, names, mechanisms) vs. vague?"),
    ("stakes", "Is what the viewer gains/loses by watching crystal clear?"),
    ("compression", "Maximum meaning per word; zero filler; nothing removable?"),
]

SYSTEM = f"""You are the Hook Manager agent — the gatekeeper between hook generation and \
the rest of the script pipeline.

Your single job: score each candidate hook on 5 independent dimensions, on a 1-10 scale, \
where 10 means a top-1% performer at that dimension and 1 means it actively hurts.

The 5 dimensions:
{chr(10).join(f"{i+1}. {name} — {desc}" for i, (name, desc) in enumerate(DIMENSIONS))}

Be brutal. A hook only passes the gate if it scores 10/10 on EVERY dimension. \
A 9 on any one dimension is a fail. The bar is "would I bet money this stops a \
scroll right now" — not "is this competent writing".

For each hook, also produce one specific, actionable rewrite suggestion for whichever \
dimension scored lowest. The Hook Writer will use it on the next attempt."""


class HookScore(BaseModel):
    hook_text: str
    scroll_stop: int = Field(ge=1, le=10)
    curiosity_gap: int = Field(ge=1, le=10)
    specificity: int = Field(ge=1, le=10)
    stakes: int = Field(ge=1, le=10)
    compression: int = Field(ge=1, le=10)
    rewrite_suggestion: str = Field(..., description="One concrete change to fix the weakest dimension.")
    notes: str = Field(default="", description="Optional brief reasoning.")

    @field_validator("rewrite_suggestion")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def passes_gate(self) -> bool:
        return all(
            getattr(self, dim) == 10
            for dim, _ in DIMENSIONS
        )

    @property
    def min_score(self) -> int:
        return min(getattr(self, dim) for dim, _ in DIMENSIONS)


class HookManagerOutput(BaseModel):
    scores: list[HookScore]


def score_hooks(hooks: list[HookVariation]) -> list[HookScore]:
    user = "Score each of the following hook candidates.\n\n" + "\n\n".join(
        f"### Candidate {i+1}\n"
        f"Hook: {h.text}\n"
        f"Stated angle: {h.angle}\n"
        f"Intended emotion: {h.intended_emotion}"
        for i, h in enumerate(hooks)
    )
    out = call_structured(
        system=SYSTEM,
        user=user,
        schema=HookManagerOutput,
        effort="high",
    )
    return out.scores


def select_winner(scores: list[HookScore]) -> HookScore | None:
    """Return the first hook that passes the gate, else None."""
    for s in scores:
        if s.passes_gate:
            return s
    return None


def aggregate_feedback(scores: list[HookScore]) -> str:
    """Roll up all rewrite suggestions for the next Hook Writer attempt."""
    lines = []
    for i, s in enumerate(scores):
        weakest = min(DIMENSIONS, key=lambda d: getattr(s, d[0]))
        lines.append(
            f"- Hook {i+1} (min={s.min_score}, weakest={weakest[0]}): {s.rewrite_suggestion}"
        )
    return "\n".join(lines)
