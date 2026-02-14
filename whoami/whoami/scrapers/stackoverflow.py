"""Stack Overflow profile scraper using Stack Exchange API v2.3."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_API_BASE = "https://api.stackexchange.com/2.3"


class StackOverflowScraper(BaseScraper):
    """Scrape public Stack Overflow profiles via the Stack Exchange API."""

    url_patterns: list[str] = ["stackoverflow.com/*"]

    def get_platform_name(self) -> str:
        return "Stack Overflow"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        user_id = self._extract_user_id(url)
        timeout = config.timeout

        # Fetch user info, top tags, and top answers concurrently
        user_data, tags_data, answers_data = await asyncio.gather(
            self._fetch_user(user_id, timeout),
            self._fetch_top_tags(user_id, timeout),
            self._fetch_top_answers(user_id, timeout, config.max_items),
        )

        items: list[ScrapedItem] = []

        # --- profile items ---
        username = None
        bio = None
        if user_data:
            username = user_data.get("display_name")
            bio = user_data.get("about_me")
            items.extend(self._build_profile_items(user_data))

        # --- tag items ---
        if tags_data:
            items.extend(self._build_tag_items(tags_data))

        # --- answer items ---
        if answers_data:
            items.extend(self._build_answer_items(answers_data))

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=bio,
            items=items,
            raw={"user": user_data or {}, "tags": tags_data or [], "answers": answers_data or []},
            source_url=url,
        )

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_user_id(url: str) -> str:
        """Extract user ID from Stack Overflow URL.

        Example: https://stackoverflow.com/users/22656/jon-skeet -> 22656
        """
        parsed = urlparse(url if "://" in url else f"https://{url}")
        parts = [p for p in parsed.path.strip("/").split("/") if p]

        # URL format: /users/{id}/{username}
        if len(parts) >= 2 and parts[0] == "users":
            user_id = parts[1]
            if user_id.isdigit():
                return user_id

        raise ValueError(f"Cannot extract Stack Overflow user ID from URL: {url}")

    # ------------------------------------------------------------------
    # API fetchers (each returns None on failure for graceful degradation)
    # ------------------------------------------------------------------

    async def _fetch_user(self, user_id: str, timeout: float) -> dict[str, Any] | None:
        """Fetch user profile information."""
        try:
            url = f"{_API_BASE}/users/{user_id}"
            params = {"site": "stackoverflow"}

            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                if data.get("items"):
                    return data["items"][0]
                return None
        except Exception:
            logger.warning("Failed to fetch user profile for %s", user_id, exc_info=True)
            return None

    async def _fetch_top_tags(self, user_id: str, timeout: float) -> list[dict[str, Any]] | None:
        """Fetch user's top tags."""
        try:
            url = f"{_API_BASE}/users/{user_id}/top-tags"
            params = {"site": "stackoverflow", "pagesize": 10}

            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                if data.get("items"):
                    return data["items"]
                return None
        except Exception:
            logger.warning("Failed to fetch top tags for %s", user_id, exc_info=True)
            return None

    async def _fetch_top_answers(
        self, user_id: str, timeout: float, max_items: int
    ) -> list[dict[str, Any]] | None:
        """Fetch user's top answers by votes."""
        try:
            url = f"{_API_BASE}/users/{user_id}/answers"
            pagesize = min(max_items, 10)
            params = {
                "site": "stackoverflow",
                "order": "desc",
                "sort": "votes",
                "pagesize": pagesize,
            }

            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                if data.get("items"):
                    return data["items"]
                return None
        except Exception:
            logger.warning("Failed to fetch top answers for %s", user_id, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Item builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_profile_items(user: dict[str, Any]) -> list[ScrapedItem]:
        """Build profile items from user data."""
        items: list[ScrapedItem] = []
        profile_url = user.get("link")

        # Basic profile info
        if reputation := user.get("reputation"):
            items.append(
                ScrapedItem(category="stats", key="reputation", value=reputation, url=profile_url)
            )

        # Badge counts
        if badge_counts := user.get("badge_counts"):
            for badge_type in ["gold", "silver", "bronze"]:
                if count := badge_counts.get(badge_type):
                    items.append(
                        ScrapedItem(
                            category="stats",
                            key=f"{badge_type}_badges",
                            value=count,
                            url=profile_url,
                        )
                    )

        # Location
        if location := user.get("location"):
            items.append(
                ScrapedItem(category="profile", key="location", value=location, url=profile_url)
            )

        # Website
        if website := user.get("website_url"):
            items.append(
                ScrapedItem(category="profile", key="website", value=website, url=profile_url)
            )

        return items

    @staticmethod
    def _build_tag_items(tags: list[dict[str, Any]]) -> list[ScrapedItem]:
        """Build tag items from top tags data."""
        items: list[ScrapedItem] = []

        for tag_data in tags:
            tag_name = tag_data.get("tag_name")
            tag_count = tag_data.get("answer_count", 0)

            if tag_name:
                items.append(
                    ScrapedItem(
                        category="tag",
                        key=tag_name,
                        value=tag_count,
                        url=f"https://stackoverflow.com/questions/tagged/{tag_name}",
                    )
                )

        return items

    @staticmethod
    def _build_answer_items(answers: list[dict[str, Any]]) -> list[ScrapedItem]:
        """Build answer items from top answers data."""
        items: list[ScrapedItem] = []

        for answer in answers:
            answer_id = answer.get("answer_id")
            question_id = answer.get("question_id")
            score = answer.get("score", 0)
            title = answer.get("title", "Untitled")

            # Clean HTML tags from title
            title = re.sub(r"<[^>]+>", "", title)

            if answer_id and question_id:
                items.append(
                    ScrapedItem(
                        category="answer",
                        key=title[:100],  # Truncate long titles
                        value={"score": score, "accepted": answer.get("is_accepted", False)},
                        url=f"https://stackoverflow.com/a/{answer_id}",
                    )
                )

        return items
