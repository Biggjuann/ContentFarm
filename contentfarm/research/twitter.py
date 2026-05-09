"""X / Twitter API v2 adapter — high-engagement posts with active comment fights."""

from __future__ import annotations

import logging

from ..config import SETTINGS
from .types import ResearchItem

log = logging.getLogger(__name__)


def fetch_engagement_posts(topic: str, max_results: int = 50) -> list[ResearchItem]:
    if not SETTINGS.x_bearer_token:
        log.warning("X_BEARER_TOKEN not set — skipping X research")
        return []

    try:
        import tweepy  # type: ignore
    except ImportError:
        log.warning("tweepy not installed — skipping X")
        return []

    client = tweepy.Client(bearer_token=SETTINGS.x_bearer_token, wait_on_rate_limit=False)

    # API v2 recent search caps at 100; we ask for max_results within that
    capped = max(10, min(max_results, 100))
    query = f"{topic} -is:retweet lang:en"

    try:
        resp = client.search_recent_tweets(
            query=query,
            max_results=capped,
            tweet_fields=["public_metrics", "created_at", "author_id", "conversation_id"],
        )
    except Exception as exc:
        log.warning("X search failed: %s", exc)
        return []

    tweets = resp.data or []
    items: list[ResearchItem] = []
    for t in tweets:
        m = getattr(t, "public_metrics", {}) or {}
        replies = int(m.get("reply_count", 0) or 0)
        likes = int(m.get("like_count", 0) or 0)
        retweets = int(m.get("retweet_count", 0) or 0)
        # Engagement score weights replies more — that's the "people fighting in the comments" signal.
        engagement = likes + 2 * retweets + 4 * replies

        items.append(
            ResearchItem(
                source="x",
                title=(t.text or "").split("\n", 1)[0][:120],
                body=t.text or "",
                url=f"https://x.com/i/web/status/{t.id}",
                engagement=engagement,
                metadata={
                    "likes": likes,
                    "retweets": retweets,
                    "replies": replies,
                    "fight_factor": replies / max(likes, 1),
                },
            )
        )

    # Sort: items with the most argument-per-like first, then raw engagement
    items.sort(
        key=lambda i: (i.metadata.get("fight_factor", 0), i.engagement),
        reverse=True,
    )
    return items
