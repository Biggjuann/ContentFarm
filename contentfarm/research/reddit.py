"""Reddit adapter — viral threads + customer pain quotes."""

from __future__ import annotations

import logging

from ..config import SETTINGS
from .types import ResearchItem

log = logging.getLogger(__name__)


def fetch_pain_points(topic: str, limit: int = 25, comment_quotes_per_post: int = 3) -> list[ResearchItem]:
    if not (SETTINGS.reddit_client_id and SETTINGS.reddit_client_secret):
        log.warning("Reddit credentials missing — skipping Reddit research")
        return []

    try:
        import praw  # type: ignore
    except ImportError:
        log.warning("praw not installed — skipping Reddit")
        return []

    reddit = praw.Reddit(
        client_id=SETTINGS.reddit_client_id,
        client_secret=SETTINGS.reddit_client_secret,
        user_agent=SETTINGS.reddit_user_agent,
    )
    reddit.read_only = True

    items: list[ResearchItem] = []

    try:
        submissions = list(reddit.subreddit("all").search(
            query=topic,
            sort="top",
            time_filter="month",
            limit=limit,
        ))
    except Exception as exc:
        log.warning("Reddit search failed: %s", exc)
        return []

    for post in submissions:
        items.append(
            ResearchItem(
                source="reddit",
                title=post.title or "",
                body=post.selftext or "",
                url=f"https://reddit.com{post.permalink}",
                engagement=int(post.score or 0),
                metadata={
                    "subreddit": str(post.subreddit),
                    "num_comments": int(post.num_comments or 0),
                    "kind": "submission",
                },
            )
        )

        # Pull a few top comments — these are the "exact quotes from viral threads"
        try:
            post.comments.replace_more(limit=0)
            top_comments = sorted(
                (c for c in post.comments.list() if hasattr(c, "body")),
                key=lambda c: int(getattr(c, "score", 0) or 0),
                reverse=True,
            )[:comment_quotes_per_post]
        except Exception as exc:
            log.debug("Could not fetch comments for %s: %s", post.id, exc)
            top_comments = []

        for c in top_comments:
            items.append(
                ResearchItem(
                    source="reddit",
                    title=f"Top comment on: {post.title[:80]}",
                    body=getattr(c, "body", ""),
                    url=f"https://reddit.com{post.permalink}",
                    engagement=int(getattr(c, "score", 0) or 0),
                    metadata={
                        "subreddit": str(post.subreddit),
                        "kind": "comment",
                        "parent_post_id": post.id,
                    },
                )
            )

    items.sort(key=lambda i: i.engagement, reverse=True)
    return items
