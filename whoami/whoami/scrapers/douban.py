"""Douban (豆瓣) profile scraper using HTML parsing."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper
from whoami.utils.http import fetch_text

logger = logging.getLogger(__name__)


class DoubanScraper(BaseScraper):
    """Scrape public Douban profiles via HTML parsing."""

    url_patterns: list[str] = ["*douban.com/people/*"]

    def get_platform_name(self) -> str:
        return "Douban"

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        user_id = self._extract_user_id(url)
        profile_url = f"https://www.douban.com/people/{user_id}/"

        try:
            html = await self._fetch_profile(profile_url, config.timeout)
            items = self._parse_profile(html, profile_url)
            username = self._extract_username(html)
            bio = self._extract_bio(html)

            return ScrapedData(
                platform=self.get_platform_name(),
                username=username,
                bio=bio,
                items=items,
                raw={"html_length": len(html)},
                source_url=profile_url,
            )
        except Exception as e:
            logger.warning("Failed to scrape Douban profile %s: %s", user_id, e)
            return ScrapedData(
                platform=self.get_platform_name(),
                username=user_id,
                bio=None,
                items=[],
                raw={"error": str(e)},
                source_url=profile_url,
            )

    @staticmethod
    def _extract_user_id(url: str) -> str:
        """Extract user ID from Douban URL."""
        parsed = urlparse(url if "://" in url else f"https://{url}")
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2 and parts[0] == "people":
            return parts[1]
        raise ValueError(f"Cannot extract Douban user ID from URL: {url}")

    async def _fetch_profile(self, url: str, timeout: float) -> str:
        """Fetch profile HTML with anti-scraping headers."""
        headers = {
            "Referer": "https://www.douban.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        return await fetch_text(url, headers=headers, timeout=timeout)

    @staticmethod
    def _extract_username(html: str) -> str | None:
        """Extract username from HTML."""
        title_match = re.search(r"<title>\s*([^<\n]+)\s*</title>", html, re.DOTALL)
        if title_match:
            username = title_match.group(1).strip()
            if username and username != "豆瓣":
                return username

        name_match = re.search(r'<div class="name"[^>]*>([^<]+)</div>', html)
        if name_match:
            return name_match.group(1).strip()

        return None

    @staticmethod
    def _extract_bio(html: str) -> str | None:
        """Extract bio/intro from HTML."""
        bio_match = re.search(r'<div class="intro"[^>]*>([^<]+)</div>', html)
        if bio_match:
            return bio_match.group(1).strip()

        return None

    def _parse_profile(self, html: str, profile_url: str) -> list[ScrapedItem]:
        """Parse profile HTML and extract items."""
        items: list[ScrapedItem] = []

        items.extend(self._extract_profile_info(html, profile_url))
        items.extend(self._extract_stats(html, profile_url))

        return items

    @staticmethod
    def _extract_profile_info(html: str, profile_url: str) -> list[ScrapedItem]:
        """Extract profile information."""
        items: list[ScrapedItem] = []

        location_match = re.search(r'常居:&nbsp;<a[^>]*>([^<]+)</a>', html)
        if location_match:
            items.append(
                ScrapedItem(
                    category="profile",
                    key="location",
                    value=location_match.group(1).strip(),
                    url=profile_url,
                )
            )

        join_match = re.search(r'(\d{4}-\d{2}-\d{2})\s*加入', html)
        if join_match:
            items.append(
                ScrapedItem(
                    category="profile",
                    key="join_date",
                    value=join_match.group(1),
                    url=profile_url,
                )
            )

        return items

    @staticmethod
    def _extract_stats(html: str, profile_url: str) -> list[ScrapedItem]:
        """Extract statistics from sidebar."""
        items: list[ScrapedItem] = []

        movie_match = re.search(r'(\d+)部看过', html)
        if movie_match:
            items.append(
                ScrapedItem(
                    category="stats",
                    key="movies_watched",
                    value=int(movie_match.group(1)),
                    url=profile_url,
                )
            )

        book_match = re.search(r'(\d+)本读过', html)
        if book_match:
            items.append(
                ScrapedItem(
                    category="stats",
                    key="books_read",
                    value=int(book_match.group(1)),
                    url=profile_url,
                )
            )

        music_match = re.search(r'(\d+)张听过', html)
        if music_match:
            items.append(
                ScrapedItem(
                    category="stats",
                    key="music_listened",
                    value=int(music_match.group(1)),
                    url=profile_url,
                )
            )

        return items
