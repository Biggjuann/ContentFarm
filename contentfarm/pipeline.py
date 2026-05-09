"""End-to-end orchestrator: research → hook generation/gate → script → per-line gate."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from .agents.hook_manager import (
    HookScore,
    aggregate_feedback,
    score_hooks,
    select_winner,
)
from .agents.hook_writer import HookVariation, write_hooks
from .agents.line_critic import gate_lines
from .agents.script_writer import write_script
from .config import SETTINGS
from .research import ResearchBundle, sweep

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    topic: str
    research: ResearchBundle
    hook_attempts: list[list[HookScore]] = field(default_factory=list)
    final_hook: HookScore | None = None
    final_hook_variation: HookVariation | None = None
    raw_script_lines: list[str] = field(default_factory=list)
    final_script_lines: list[str] = field(default_factory=list)
    line_audit: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "research_summary": {
                "youtube_count": len(self.research.youtube),
                "reddit_count": len(self.research.reddit),
                "x_count": len(self.research.x),
                "notes": self.research.notes,
            },
            "hook_attempts": [
                [score.model_dump() for score in attempt]
                for attempt in self.hook_attempts
            ],
            "final_hook": self.final_hook.model_dump() if self.final_hook else None,
            "final_hook_variation": (
                self.final_hook_variation.model_dump() if self.final_hook_variation else None
            ),
            "raw_script_lines": self.raw_script_lines,
            "final_script_lines": self.final_script_lines,
            "line_audit": self.line_audit,
            "final_script_text": "\n".join(self.final_script_lines),
        }


def run_pipeline(topic: str) -> PipelineResult:
    log.info("Starting pipeline for topic: %r", topic)
    research = sweep(topic)
    result = PipelineResult(topic=topic, research=research)

    feedback: str | None = None
    winner_score: HookScore | None = None
    winner_variation: HookVariation | None = None

    for attempt in range(1, SETTINGS.hook_gate_max_attempts + 1):
        log.info("Hook gate attempt %d/%d", attempt, SETTINGS.hook_gate_max_attempts)
        variations = write_hooks(topic, research, feedback=feedback)
        scores = score_hooks(variations)
        result.hook_attempts.append(scores)

        winner_score = select_winner(scores)
        if winner_score is not None:
            winner_variation = next(
                (v for v in variations if v.text.strip() == winner_score.hook_text.strip()),
                variations[0],
            )
            log.info("Hook gate cleared on attempt %d", attempt)
            break

        feedback = aggregate_feedback(scores)

    if winner_score is None:
        log.warning("Hook gate never reached 10/10 — falling back to highest-scoring hook")
        flat = [s for batch in result.hook_attempts for s in batch]
        winner_score = max(
            flat,
            key=lambda s: (s.min_score, s.scroll_stop + s.curiosity_gap + s.specificity + s.stakes + s.compression),
        )
        # Find matching variation from last attempt
        winner_variation = next(
            (v for v in variations if v.text.strip() == winner_score.hook_text.strip()),
            variations[0] if variations else None,
        )

    result.final_hook = winner_score
    result.final_hook_variation = winner_variation

    raw_lines = write_script(
        hook=winner_score.hook_text,
        topic=topic,
        research=research,
    )
    result.raw_script_lines = raw_lines
    log.info("Script drafted with %d lines; running line gate", len(raw_lines))

    final_lines, audit = gate_lines(raw_lines)
    result.final_script_lines = final_lines
    result.line_audit = audit

    log.info("Pipeline complete: %d lines, %d total rewrite attempts",
             len(final_lines),
             sum(len(a["attempts"]) - 1 for a in audit))
    return result
