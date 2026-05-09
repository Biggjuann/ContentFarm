"""Line-by-line critic + rewriter — the 2D 10/10 gate that runs against every line."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from ..config import SETTINGS
from .base import call_structured

log = logging.getLogger(__name__)


CRITIC_SYSTEM = """You are the Line Critic agent. Every single line of a finished script \
must clear your bar before it ships.

You score each line independently on TWO dimensions, 1-10:

1. invention_novelty — Does this line make the content itself feel like a breakthrough? \
   10 = the audience has genuinely never heard a sentence quite like this. \
   1 = generic, recycled, the kind of sentence that exists in 10,000 other videos.

2. copy_intensity — Is the line sharp enough that the viewer FEELS an emotion through it, \
   not just understands the information? \
   10 = the words punch — visceral, vivid, image-forming, charged. \
   1 = flat, informational, neutral.

Both dimensions must hit 10/10 for the line to pass. A 9 on either one is a fail.

For any line that fails, produce ONE concrete rewrite suggestion: tell the rewriter \
specifically what to change (replace this word with this kind of word, sharpen the verb, \
swap the abstraction for a concrete image, etc.).

Be honest. Most lines are not 10/10. The point of this gate is to catch the lines that \
are merely "good" and force them to be remarkable."""


REWRITER_SYSTEM = """You are the Line Rewriter agent. You receive a single weak line plus \
specific feedback from the Line Critic, and you return a single replacement line.

Constraints:
- Preserve the line's role in the script (don't change what point it's making, only how).
- Do not lengthen the line meaningfully — short is good, sharp is better.
- Apply the critic's note directly. If the critic says "swap abstraction for concrete \
  image", do that — don't paraphrase.
- Respond with the rewritten line and nothing else."""


class LineScore(BaseModel):
    line: str
    invention_novelty: int = Field(ge=1, le=10)
    copy_intensity: int = Field(ge=1, le=10)
    rewrite_suggestion: str = Field(default="", description="Concrete change for the rewriter; empty if the line passes.")

    @property
    def passes(self) -> bool:
        return self.invention_novelty == 10 and self.copy_intensity == 10


class LineScoreBatch(BaseModel):
    scores: list[LineScore]


class RewrittenLine(BaseModel):
    new_line: str
    change_summary: str = Field(..., description="One-sentence summary of what was changed and why.")


def score_lines(lines: list[str]) -> list[LineScore]:
    user = "Score each line independently. Return one entry per line in the same order.\n\n" + "\n".join(
        f"{i+1}. {line}" for i, line in enumerate(lines)
    )
    out = call_structured(
        system=CRITIC_SYSTEM,
        user=user,
        schema=LineScoreBatch,
        effort="high",
    )
    return out.scores


def rewrite_line(line: str, feedback: str, context_before: str, context_after: str) -> RewrittenLine:
    user = (
        f"# CONTEXT BEFORE\n{context_before or '(start of script)'}\n\n"
        f"# WEAK LINE TO REWRITE\n{line}\n\n"
        f"# CRITIC FEEDBACK\n{feedback}\n\n"
        f"# CONTEXT AFTER\n{context_after or '(end of script)'}\n\n"
        "Return the rewritten line."
    )
    return call_structured(
        system=REWRITER_SYSTEM,
        user=user,
        schema=RewrittenLine,
        effort="medium",
    )


def gate_lines(lines: list[str]) -> tuple[list[str], list[dict]]:
    """Run the per-line gate. Each line is rewritten until it passes or attempts run out.

    Returns (final_lines, audit_trail) where audit_trail records every attempt per line.
    """
    audit: list[dict] = []
    final = list(lines)

    # Score the whole script in one call to start, then iterate per-line.
    scores = score_lines(final)

    for idx, score in enumerate(scores):
        line_audit = {
            "index": idx,
            "original": score.line,
            "attempts": [
                {
                    "version": score.line,
                    "invention_novelty": score.invention_novelty,
                    "copy_intensity": score.copy_intensity,
                    "feedback": score.rewrite_suggestion,
                    "passed": score.passes,
                }
            ],
        }

        attempt = 0
        current = score
        while not current.passes and attempt < SETTINGS.line_gate_max_attempts:
            attempt += 1
            ctx_before = "\n".join(final[max(0, idx - 2): idx])
            ctx_after = "\n".join(final[idx + 1: idx + 3])
            try:
                rewritten = rewrite_line(
                    line=current.line,
                    feedback=current.rewrite_suggestion or "Sharpen the line — more concrete imagery, sharper verb, less abstraction.",
                    context_before=ctx_before,
                    context_after=ctx_after,
                )
            except Exception as exc:
                log.warning("Rewriter failed on line %d: %s", idx, exc)
                break

            new_text = rewritten.new_line.strip()
            final[idx] = new_text

            try:
                rescore = score_lines([new_text])[0]
            except Exception as exc:
                log.warning("Re-scoring failed on line %d: %s", idx, exc)
                break

            line_audit["attempts"].append({
                "version": new_text,
                "invention_novelty": rescore.invention_novelty,
                "copy_intensity": rescore.copy_intensity,
                "feedback": rescore.rewrite_suggestion,
                "change_summary": rewritten.change_summary,
                "passed": rescore.passes,
            })
            current = rescore

        line_audit["final_text"] = final[idx]
        line_audit["final_passed"] = current.passes
        audit.append(line_audit)

    return final, audit
