"""Build a niche-specific hook pattern database from real top-performing titles.

This replaces the hardcoded seed list in `proven_hooks.py` for any topic where
we can pull a meaningful research sample. Falls back to the seed list when the
research sweep is too sparse.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from ..research.reddit import fetch_pain_points
from ..research.twitter import fetch_engagement_posts
from ..research.youtube import fetch_top_videos
from .base import call_structured
from .proven_hooks import PROVEN_HOOKS

log = logging.getLogger(__name__)


SYSTEM = """You are a copywriting analyst. Given a list of titles from top-performing \
short-form videos, social posts, and viral threads in a specific niche, your job is to \
extract the underlying HOOK PATTERNS — the structural archetypes that make these titles \
work as scroll-stoppers.

Process:
1. Read every title.
2. Identify the structural patterns. A "pattern" is a TEMPLATE, not a topic. Examples: \
"Specific Number" ($47K in 11 days), "Contrarian Truth" (Everyone X. They're wrong.), \
"Imminent Threat" (If you're still doing X in 2026 you've lost.), "Hidden Mechanism" \
(There's a team running 20 agents to do Y.).
3. Cluster titles that share a pattern. Be ruthless about deduplication — "curiosity \
loop" and "open question" are the same pattern.
4. Return ONLY patterns that appear in at least {min_occurrences} of the input titles. \
One-off patterns are noise.
5. For each surviving pattern, give:
   - a 2-4 word pattern name (Title Case)
   - ONE clean paraphrased example — re-cast it generically, do not quote a real title
   - one sentence on why it works mechanically
   - the count of titles that fit
   - up to 3 source titles as evidence

Sort the output by occurrence count, descending."""


class ExtractedPattern(BaseModel):
    pattern_name: str = Field(..., description="2-4 word title-case label.")
    example: str = Field(..., description="Generic paraphrased example, not a real title.")
    why_it_works: str = Field(..., description="One sentence on the underlying mechanism.")
    occurrences: int = Field(ge=1)
    source_titles: list[str] = Field(default_factory=list, max_length=5)


class HookDatabaseOutput(BaseModel):
    patterns: list[ExtractedPattern]


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_dir() -> Path:
    base = Path(os.getenv("CONTENTFARM_CACHE_DIR", "/tmp/contentfarm_cache"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _cache_path(topic: str) -> Path:
    h = hashlib.sha256(topic.lower().strip().encode()).hexdigest()[:12]
    return _cache_dir() / f"hook_db_{h}.json"


def _read_cache(topic: str, ttl_hours: int) -> list[ExtractedPattern] | None:
    path = _cache_path(topic)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        built_at = datetime.fromisoformat(data["built_at"])
        age_hours = (datetime.now(timezone.utc) - built_at).total_seconds() / 3600
        if age_hours >= ttl_hours:
            log.info("Hook DB cache expired for %r (%.1fh > %dh)", topic, age_hours, ttl_hours)
            return None
        log.info("Hook DB cache hit for %r (age=%.1fh)", topic, age_hours)
        return [ExtractedPattern(**p) for p in data["patterns"]]
    except Exception as exc:
        log.warning("Hook DB cache read failed: %s", exc)
        return None


def _write_cache(topic: str, patterns: list[ExtractedPattern], title_count: int) -> None:
    path = _cache_path(topic)
    try:
        path.write_text(json.dumps(
            {
                "topic": topic,
                "built_at": datetime.now(timezone.utc).isoformat(),
                "title_count": title_count,
                "patterns": [p.model_dump() for p in patterns],
            },
            indent=2,
        ))
        log.info("Cached hook DB to %s", path)
    except Exception as exc:
        log.warning("Hook DB cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Title harvest
# ---------------------------------------------------------------------------


def harvest_titles(topic: str) -> list[tuple[str, str]]:
    """Pull a wide net of titles across all platforms. Returns (source, title) tuples."""
    titles: list[tuple[str, str]] = []

    # YouTube: 15 keywords × 25 results, look back 6 months for a deeper pool
    try:
        yt = fetch_top_videos(topic, days_back=180, per_keyword=25)
        titles.extend(("youtube", item.title) for item in yt if item.title)
    except Exception as exc:
        log.warning("YouTube title harvest failed: %s", exc)

    # Reddit: post titles only — comments aren't hooks
    try:
        rd = fetch_pain_points(topic, limit=100, comment_quotes_per_post=0)
        titles.extend(
            ("reddit", item.title)
            for item in rd
            if item.title and item.metadata.get("kind") == "submission"
        )
    except Exception as exc:
        log.warning("Reddit title harvest failed: %s", exc)

    # X: first line of each tweet acts as the hook
    try:
        xt = fetch_engagement_posts(topic, max_results=100)
        titles.extend(("x", item.title) for item in xt if item.title)
    except Exception as exc:
        log.warning("X title harvest failed: %s", exc)

    # Dedupe by lowercase text
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for src, title in titles:
        key = title.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((src, title))
    return deduped


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


MIN_TITLES_FOR_BUILD = 10
SEED_FALLBACK_THRESHOLD = 25  # below this, we still build but log a warning


def build_hook_database(
    topic: str,
    *,
    min_occurrences: int = 3,
    use_cache: bool = True,
    ttl_hours: int = 168,  # 1 week
    max_titles_to_analyze: int = 500,
) -> list[ExtractedPattern]:
    """Build a niche-specific hook pattern database for a topic.

    Steps:
      1. Try the per-topic cache (TTL 7 days by default).
      2. Harvest titles from YouTube + Reddit + X.
      3. If too few, fall back to the hardcoded seed patterns.
      4. Otherwise, ask Claude to extract recurring structural patterns.
      5. Persist to cache.
    """
    if use_cache:
        cached = _read_cache(topic, ttl_hours)
        if cached is not None:
            return cached

    titles = harvest_titles(topic)
    log.info("Harvested %d unique titles for hook DB build (%r)", len(titles), topic)

    if len(titles) < MIN_TITLES_FOR_BUILD:
        log.warning(
            "Too few titles (%d < %d) — falling back to seed patterns",
            len(titles),
            MIN_TITLES_FOR_BUILD,
        )
        return _seed_as_extracted()

    if len(titles) < SEED_FALLBACK_THRESHOLD:
        log.warning(
            "Sparse harvest (%d < %d) — niche-specific patterns may be weak",
            len(titles),
            SEED_FALLBACK_THRESHOLD,
        )

    sample = titles[:max_titles_to_analyze]
    titles_block = "\n".join(f"- [{src}] {title}" for src, title in sample)
    user = (
        f"# TOPIC\n{topic}\n\n"
        f"# TITLES ({len(sample)} total)\n{titles_block}\n\n"
        f"Extract structural hook patterns appearing in at least {min_occurrences} titles. "
        f"Sort by occurrence count, descending."
    )

    out = call_structured(
        system=SYSTEM.format(min_occurrences=min_occurrences),
        user=user,
        schema=HookDatabaseOutput,
        effort="high",
    )

    patterns = [p for p in out.patterns if p.occurrences >= min_occurrences]
    patterns.sort(key=lambda p: p.occurrences, reverse=True)
    log.info("Extracted %d niche-specific hook patterns for %r", len(patterns), topic)

    if not patterns:
        log.warning("No patterns survived min_occurrences filter — falling back to seed")
        return _seed_as_extracted()

    if use_cache:
        _write_cache(topic, patterns, len(titles))
    return patterns


def _seed_as_extracted() -> list[ExtractedPattern]:
    return [
        ExtractedPattern(
            pattern_name=h["pattern"],
            example=h["example"],
            why_it_works=h["why_it_works"],
            occurrences=1,
            source_titles=[],
        )
        for h in PROVEN_HOOKS
    ]


# ---------------------------------------------------------------------------
# Public formatting helper
# ---------------------------------------------------------------------------


def as_inspiration_block(topic: str) -> str:
    """Format the hook database as a prompt block for the Hook Writer agent."""
    patterns = build_hook_database(topic)
    if not patterns:
        from .proven_hooks import as_inspiration_block as seed_block
        return seed_block()

    lines = []
    for p in patterns:
        evidence = ""
        if p.source_titles:
            evidence = "\n  Evidence: " + "; ".join(t[:80] for t in p.source_titles[:3])
        lines.append(
            f"- {p.pattern_name} (seen in {p.occurrences} top titles)\n"
            f"  Example: {p.example}\n"
            f"  Why: {p.why_it_works}{evidence}"
        )
    return "\n".join(lines)
