"""YouTube Data API v3 adapter — top performers across many keyword variants."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..config import SETTINGS
from .types import ResearchItem

log = logging.getLogger(__name__)


def _expand_keywords(topic: str) -> list[str]:
    """15 keyword variations to widen the discovery net."""
    base = topic.strip()
    return [
        base,
        f"{base} tutorial",
        f"{base} explained",
        f"how to {base}",
        f"{base} for beginners",
        f"{base} mistakes",
        f"{base} tips",
        f"why {base}",
        f"{base} secret",
        f"{base} hack",
        f"best {base}",
        f"{base} review",
        f"{base} truth",
        f"{base} story",
        f"{base} 2026",
    ][:15]


def fetch_top_videos(topic: str, days_back: int = 30, per_keyword: int = 5) -> list[ResearchItem]:
    if not SETTINGS.youtube_api_key:
        log.warning("YOUTUBE_API_KEY not set — skipping YouTube research")
        return []

    try:
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.errors import HttpError  # type: ignore
    except ImportError:
        log.warning("google-api-python-client not installed — skipping YouTube")
        return []

    service = build("youtube", "v3", developerKey=SETTINGS.youtube_api_key, cache_discovery=False)
    published_after = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat().replace("+00:00", "Z")

    items: list[ResearchItem] = []
    seen_ids: set[str] = set()

    for query in _expand_keywords(topic):
        try:
            search_resp = service.search().list(
                q=query,
                part="snippet",
                type="video",
                order="viewCount",
                publishedAfter=published_after,
                maxResults=per_keyword,
                relevanceLanguage="en",
            ).execute()
        except HttpError as exc:
            log.warning("YouTube search failed for %r: %s", query, exc)
            continue

        video_ids = [r["id"]["videoId"] for r in search_resp.get("items", []) if r["id"].get("videoId")]
        new_ids = [vid for vid in video_ids if vid not in seen_ids]
        if not new_ids:
            continue

        try:
            stats_resp = service.videos().list(
                id=",".join(new_ids),
                part="statistics,snippet",
            ).execute()
        except HttpError as exc:
            log.warning("YouTube stats fetch failed: %s", exc)
            continue

        for v in stats_resp.get("items", []):
            seen_ids.add(v["id"])
            stats = v.get("statistics", {})
            snippet = v.get("snippet", {})
            items.append(
                ResearchItem(
                    source="youtube",
                    title=snippet.get("title", ""),
                    body=snippet.get("description", ""),
                    url=f"https://www.youtube.com/watch?v={v['id']}",
                    engagement=int(stats.get("viewCount", 0) or 0),
                    metadata={
                        "channel": snippet.get("channelTitle"),
                        "likes": int(stats.get("likeCount", 0) or 0),
                        "comments": int(stats.get("commentCount", 0) or 0),
                        "query": query,
                    },
                )
            )

    items.sort(key=lambda i: i.engagement, reverse=True)
    return items
