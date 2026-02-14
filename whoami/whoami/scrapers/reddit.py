"""Reddit profile scraper using public JSON API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper
from whoami.utils.http import fetch_json

logger = logging.getLogger(__name__)

_API_BASE = "https://www.reddit.com"


class RedditScraper(BaseScraper):
    """Scrape public Reddit profiles via the JSON API."""

    url_patterns: list[str] = ["*reddit.com/*"]

    def get_platform_name(self) -> str:
        return "Reddit"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        username = self._extract_username(url)
        headers = {"User-Agent": "whoami-scraper/0.1"}
        timeout = config.timeout

        # Fetch user about, posts, and comments concurrently.
        about_data, posts_data, comments_data = await asyncio.gather(
            self._fetch_about(username, headers, timeout),
            self._fetch_posts(username, headers, timeout),
            self._fetch_comments(username, headers, timeout),
        )

        items: list[ScrapedItem] = []

        # --- profile items ---
        if about_data:
            items.extend(self._build_profile_items(about_data))

        # --- post items ---
        if posts_data:
            items.extend(self._build_post_items(posts_data))

        # --- comment activity items ---
        if comments_data:
            items.extend(self._build_comment_items(comments_data))

        bio = None
        if about_data:
            user_data = about_data.get("data", {})
            subreddit = user_data.get("subreddit", {})
            bio = subreddit.get("public_description") if isinstance(subreddit, dict) else None

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=bio,
            items=items,
            raw={"about": about_data or {}, "posts": posts_data or {}, "comments": comments_data or {}},
            source_url=url,
        )

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_username(url: str) -> str:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2 or parts[0] not in ("user", "u"):
            raise ValueError(f"Cannot extract Reddit username from URL: {url}")
        return parts[1]

    # ------------------------------------------------------------------
    # API fetchers (each returns None on failure for graceful degradation)
    # ------------------------------------------------------------------

    async def _fetch_about(
        self, username: str, headers: dict[str, str], timeout: float
    ) -> dict[str, Any] | None:
        try:
            return await fetch_json(
                f"{_API_BASE}/user/{username}/about.json", headers=headers, timeout=timeout
            )
        except Exception:
            logger.warning("Failed to fetch about for %s", username, exc_info=True)
            return None

    async def _fetch_posts(
        self, username: str, headers: dict[str, str], timeout: float
    ) -> dict[str, Any] | None:
        try:
            return await fetch_json(
                f"{_API_BASE}/user/{username}/submitted.json",
                headers=headers,
                params={"limit": 20, "sort": "top", "t": "all"},
                timeout=timeout,
            )
        except Exception:
            logger.warning("Failed to fetch posts for %s", username, exc_info=True)
            return None

    async def _fetch_comments(
        self, username: str, headers: dict[str, str], timeout: float
    ) -> dict[str, Any] | None:
        try:
            return await fetch_json(
                f"{_API_BASE}/user/{username}/comments.json",
                headers=headers,
                params={"limit": 10, "sort": "top", "t": "all"},
                timeout=timeout,
            )
        except Exception:
            logger.warning("Failed to fetch comments for %s", username, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Item builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_profile_items(about: dict[str, Any]) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        user_data = about.get("data", {})
        profile_url = f"https://www.reddit.com/user/{user_data.get('name', '')}"

        field_map: dict[str, str] = {
            "name": "username",
            "link_karma": "link_karma",
            "comment_karma": "comment_karma",
            "total_karma": "total_karma",
            "created_utc": "account_created",
        }
        for api_key, item_key in field_map.items():
            val = user_data.get(api_key)
            if val is not None and val != "":
                items.append(
                    ScrapedItem(category="profile", key=item_key, value=val, url=profile_url)
                )
        return items

    @staticmethod
    def _build_post_items(posts: dict[str, Any]) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        children = posts.get("data", {}).get("children", [])
        for child in children:
            post_data = child.get("data", {})
            title = post_data.get("title", "")
            if title:
                items.append(
                    ScrapedItem(
                        category="post",
                        key=title[:100],
                        value={
                            "subreddit": post_data.get("subreddit"),
                            "score": post_data.get("score", 0),
                            "num_comments": post_data.get("num_comments", 0),
                        },
                        url=f"https://www.reddit.com{post_data.get('permalink', '')}",
                    )
                )
        return items

    @staticmethod
    def _build_comment_items(comments: dict[str, Any]) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        children = comments.get("data", {}).get("children", [])
        subreddit_counts: dict[str, int] = {}

        for child in children:
            comment_data = child.get("data", {})
            subreddit = comment_data.get("subreddit")
            if subreddit:
                subreddit_counts[subreddit] = subreddit_counts.get(subreddit, 0) + 1

        for subreddit, count in sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True):
            items.append(
                ScrapedItem(
                    category="activity",
                    key=f"comments_in_{subreddit}",
                    value=count,
                    url=f"https://www.reddit.com/r/{subreddit}",
                )
            )
        return items
