"""GitLab profile scraper using REST API v4."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper
from whoami.utils.http import fetch_json

logger = logging.getLogger(__name__)

_API_BASE = "https://gitlab.com/api/v4"


class GitLabScraper(BaseScraper):
    """
    Scrape public GitLab profiles via the REST API v4.

    Note: GitLab's public API has restrictions on user search endpoints.
    This scraper works by:
    1. Attempting to find one of the user's projects using common naming patterns
    2. Searching for projects with the username in the name
    3. Searching through top-starred projects

    This means the scraper works best for users with:
    - Projects with common names (username, dotfiles, config, etc.)
    - Projects that appear in search results
    - Popular projects with many stars

    Users with only private projects or projects that don't match these patterns
    may not be found.
    """

    url_patterns: list[str] = ["gitlab.com/*"]

    def get_platform_name(self) -> str:
        return "GitLab"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        username = self._extract_username(url)
        timeout = config.timeout

        # GitLab's user search API is restricted, so we get a project first
        # to extract the user ID from the namespace
        user_id, user_data = await self._fetch_user_id_and_data(username, timeout)

        if not user_id or not user_data:
            return ScrapedData(
                platform=self.get_platform_name(),
                username=username,
                source_url=url,
            )

        # Fetch projects using the user ID
        projects_data = await self._fetch_projects(user_id, timeout, config.max_items)

        items: list[ScrapedItem] = []

        # --- profile items ---
        items.extend(self._build_profile_items(user_data))

        # --- project items ---
        if projects_data:
            items.extend(self._build_project_items(projects_data))

        return ScrapedData(
            platform=self.get_platform_name(),
            username=user_data.get("path") or username,
            bio=user_data.get("bio"),
            items=items,
            raw={"user": user_data, "projects": projects_data or []},
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
            raise ValueError(f"Cannot extract GitLab username from URL: {url}")
        return parts[0]

    # ------------------------------------------------------------------
    # API fetchers (each returns None on failure for graceful degradation)
    # ------------------------------------------------------------------

    async def _fetch_user_id_and_data(
        self, username: str, timeout: float
    ) -> tuple[int | None, dict[str, Any] | None]:
        """
        Fetch user ID and data by getting one of their projects.
        GitLab's user search API is restricted, so we use the projects endpoint.
        """
        try:
            # Strategy 1: Try common project name patterns
            common_names = [username, username.lower(), username.upper(), "dotfiles", "config"]
            for name in common_names:
                try:
                    project = await fetch_json(
                        f"{_API_BASE}/projects/{username}%2F{name}",
                        timeout=timeout,
                    )
                    namespace = project.get("namespace", {})
                    if namespace.get("kind") == "user" and namespace.get("path") == username:
                        return self._extract_user_id_from_namespace(namespace), namespace
                except Exception:
                    continue

            # Strategy 2: Search for projects with username in the name
            try:
                projects = await fetch_json(
                    f"{_API_BASE}/projects",
                    params={"search": username, "per_page": 50},
                    timeout=timeout,
                )

                for project in projects:
                    namespace = project.get("namespace", {})
                    if namespace.get("path") == username and namespace.get("kind") == "user":
                        return self._extract_user_id_from_namespace(namespace), namespace
            except Exception:
                pass

            # Strategy 3: Search through top starred projects
            projects = await fetch_json(
                f"{_API_BASE}/projects",
                params={"per_page": 100, "order_by": "star_count", "sort": "desc"},
                timeout=timeout,
            )

            for project in projects:
                namespace = project.get("namespace", {})
                if namespace.get("path") == username and namespace.get("kind") == "user":
                    return self._extract_user_id_from_namespace(namespace), namespace

        except Exception:
            logger.warning("Failed to fetch user data for %s", username, exc_info=True)

        return None, None

    @staticmethod
    def _extract_user_id_from_namespace(namespace: dict[str, Any]) -> int | None:
        """Extract user ID from namespace avatar URL."""
        avatar_url = namespace.get("avatar_url", "")
        match = re.search(r"/user/avatar/(\d+)/", avatar_url)
        return int(match.group(1)) if match else None

    async def _fetch_projects(
        self,
        user_id: int,
        timeout: float,
        max_items: int,
    ) -> list[dict[str, Any]] | None:
        try:
            per_page = min(max_items, 100)
            data = await fetch_json(
                f"{_API_BASE}/users/{user_id}/projects",
                params={
                    "order_by": "star_count",
                    "sort": "desc",
                    "per_page": per_page,
                },
                timeout=timeout,
            )
            if isinstance(data, list):
                return data
            return None
        except Exception:
            logger.warning("Failed to fetch projects for user_id %s", user_id, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Item builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_profile_items(user: dict[str, Any]) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        profile_url = user.get("web_url")

        field_map: dict[str, str] = {
            "name": "name",
            "path": "username",
        }
        for api_key, item_key in field_map.items():
            val = user.get(api_key)
            if val is not None and val != "":
                items.append(
                    ScrapedItem(category="profile", key=item_key, value=val, url=profile_url)
                )
        return items

    @staticmethod
    def _build_project_items(projects: list[dict[str, Any]]) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        for project in projects:
            items.append(
                ScrapedItem(
                    category="project",
                    key=project.get("name", "unknown"),
                    value={
                        "description": project.get("description"),
                        "language": project.get("language"),
                        "stars": project.get("star_count", 0),
                        "forks": project.get("forks_count", 0),
                    },
                    url=project.get("web_url"),
                )
            )
        return items
