"""Run all platform research adapters in parallel and bundle results."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from .reddit import fetch_pain_points
from .twitter import fetch_engagement_posts
from .types import ResearchBundle
from .youtube import fetch_top_videos

log = logging.getLogger(__name__)


def sweep(topic: str) -> ResearchBundle:
    """Run a full research sweep across YouTube, Reddit, and X concurrently."""
    bundle = ResearchBundle(topic=topic)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            "youtube": pool.submit(fetch_top_videos, topic),
            "reddit": pool.submit(fetch_pain_points, topic),
            "x": pool.submit(fetch_engagement_posts, topic),
        }
        for name, fut in futures.items():
            try:
                items = fut.result(timeout=120)
            except Exception as exc:
                log.warning("Research adapter %s failed: %s", name, exc)
                bundle.notes.append(f"{name} adapter failed: {exc}")
                items = []
            setattr(bundle, name, items)

    counts = {k: len(getattr(bundle, k)) for k in ("youtube", "reddit", "x")}
    log.info("Research sweep complete for %r: %s", topic, counts)
    return bundle
