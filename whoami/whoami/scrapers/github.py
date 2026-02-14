"""GitHub profile scraper using REST API v3."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper
from whoami.utils.http import fetch_json

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"


class GitHubScraper(BaseScraper):
    """Scrape public GitHub profiles via the REST API."""

    url_patterns: list[str] = ["github.com/*"]

    def get_platform_name(self) -> str:
        return "GitHub"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        username = self._extract_username(url)
        token: str | None = config.extra.get("github_token")
        headers = self._build_headers(token)
        timeout = config.timeout

        # Fetch user profile, repos, and orgs concurrently.
        user_data, repos_data, orgs_data = await asyncio.gather(
            self._fetch_user(username, headers, timeout),
            self._fetch_repos(username, headers, timeout, config.max_items),
            self._fetch_orgs(username, headers, timeout),
        )

        items: list[ScrapedItem] = []

        # --- profile items ---
        if user_data:
            items.extend(self._build_profile_items(user_data))

        # --- repo items ---
        if repos_data:
            items.extend(self._build_repo_items(repos_data))

        # --- org items ---
        if orgs_data:
            items.extend(self._build_org_items(orgs_data))

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=user_data.get("bio") if user_data else None,
            items=items,
            raw={"user": user_data or {}, "repos": repos_data or [], "orgs": orgs_data or []},
            source_url=url,
        )

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_username(url: str) -> str:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if not parts:
            raise ValueError(f"Cannot extract GitHub username from URL: {url}")
        return parts[0]

    @staticmethod
    def _build_headers(token: str | None) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    # ------------------------------------------------------------------
    # API fetchers (each returns None on failure for graceful degradation)
    # ------------------------------------------------------------------

    async def _fetch_user(
        self, username: str, headers: dict[str, str], timeout: float
    ) -> dict[str, Any] | None:
        try:
            return await fetch_json(
                f"{_API_BASE}/users/{username}", headers=headers, timeout=timeout
            )
        except Exception:
            logger.warning("Failed to fetch user profile for %s", username, exc_info=True)
            return None

    async def _fetch_repos(
        self,
        username: str,
        headers: dict[str, str],
        timeout: float,
        max_items: int,
    ) -> list[dict[str, Any]] | None:
        try:
            per_page = min(max_items, 100)
            data = await fetch_json(
                f"{_API_BASE}/users/{username}/repos",
                headers=headers,
                params={"sort": "stargazers_count", "direction": "desc", "per_page": per_page},
                timeout=timeout,
            )
            if isinstance(data, list):
                return sorted(data, key=lambda r: r.get("stargazers_count", 0), reverse=True)
            return None
        except Exception:
            logger.warning("Failed to fetch repos for %s", username, exc_info=True)
            return None

    async def _fetch_orgs(
        self, username: str, headers: dict[str, str], timeout: float
    ) -> list[dict[str, Any]] | None:
        try:
            data = await fetch_json(
                f"{_API_BASE}/users/{username}/orgs", headers=headers, timeout=timeout
            )
            return data if isinstance(data, list) else None
        except Exception:
            logger.warning("Failed to fetch orgs for %s", username, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Item builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_profile_items(user: dict[str, Any]) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        profile_url = user.get("html_url")

        field_map: dict[str, str] = {
            "name": "name",
            "location": "location",
            "company": "company",
            "blog": "blog",
            "twitter_username": "twitter",
            "public_repos": "public_repos",
            "followers": "followers",
            "following": "following",
        }
        for api_key, item_key in field_map.items():
            val = user.get(api_key)
            if val is not None and val != "":
                items.append(
                    ScrapedItem(category="profile", key=item_key, value=val, url=profile_url)
                )
        return items

    @staticmethod
    def _build_repo_items(repos: list[dict[str, Any]]) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        for repo in repos:
            items.append(
                ScrapedItem(
                    category="repo",
                    key=repo.get("name", "unknown"),
                    value={
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                    },
                    url=repo.get("html_url"),
                )
            )
        return items

    @staticmethod
    def _build_org_items(orgs: list[dict[str, Any]]) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        for org in orgs:
            login = org.get("login", "unknown")
            items.append(
                ScrapedItem(
                    category="organization",
                    key=login,
                    value=org.get("description") or login,
                    url=f"https://github.com/{login}",
                )
            )
        return items
