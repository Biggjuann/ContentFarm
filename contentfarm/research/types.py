"""Shared research data shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Source = Literal["youtube", "reddit", "x"]


@dataclass
class ResearchItem:
    source: Source
    title: str
    body: str
    url: str
    engagement: int = 0
    metadata: dict = field(default_factory=dict)

    def as_brief(self, limit: int = 280) -> str:
        body = self.body.replace("\n", " ").strip()
        if len(body) > limit:
            body = body[:limit].rstrip() + "…"
        return f"[{self.source} • {self.engagement:>6}] {self.title} — {body}"


@dataclass
class ResearchBundle:
    topic: str
    youtube: list[ResearchItem] = field(default_factory=list)
    reddit: list[ResearchItem] = field(default_factory=list)
    x: list[ResearchItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def all_items(self) -> list[ResearchItem]:
        return [*self.youtube, *self.reddit, *self.x]

    def to_prompt_block(self, per_source: int = 8) -> str:
        sections = []
        for label, items in (
            ("YOUTUBE — top performing videos", self.youtube[:per_source]),
            ("REDDIT — pain points & viral threads", self.reddit[:per_source]),
            ("X / TWITTER — high-engagement posts", self.x[:per_source]),
        ):
            if not items:
                sections.append(f"## {label}\n(no results available)\n")
                continue
            lines = "\n".join(f"- {item.as_brief()}" for item in items)
            sections.append(f"## {label}\n{lines}\n")
        if self.notes:
            sections.append("## NOTES\n" + "\n".join(f"- {n}" for n in self.notes))
        return "\n".join(sections)
