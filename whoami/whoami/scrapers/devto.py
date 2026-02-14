"""Dev.to (Forem) scraper."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper
from whoami.utils.http import fetch_json


class DevtoScraper(BaseScraper):
    """Scraper for Dev.to profiles and articles."""

    url_patterns = ["dev.to/*"]

    def get_platform_name(self) -> str:
        return "Dev.to"

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        username = self._extract_username(url)

        # Dev.to API is sensitive to headers, use minimal headers
        headers = {"User-Agent": "whoami-scraper", "Accept": "application/json"}

        # Fetch articles (includes user info in each article)
        articles_data = await fetch_json(
            "https://dev.to/api/articles",
            params={"username": username, "per_page": min(config.max_items, 20)},
            headers=headers,
            timeout=config.timeout,
        )

        # Extract user data from first article
        user_data = articles_data[0]["user"] if articles_data else {}

        items = self._build_items(user_data, articles_data)

        return ScrapedData(
            platform=self.get_platform_name(),
            username=user_data.get("username"),
            bio=user_data.get("summary"),
            items=items,
            raw={"user": user_data, "articles": articles_data},
            scraped_at=datetime.utcnow(),
            source_url=url,
        )

    def _extract_username(self, url: str) -> str:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        path = parsed.path.strip("/")
        return path.split("/")[0] if path else ""

    def _build_items(
        self, user_data: dict, articles_data: list[dict]
    ) -> list[ScrapedItem]:
        items = []

        # Profile items
        if name := user_data.get("name"):
            items.append(
                ScrapedItem(category="profile", key="name", value=name, url=None)
            )

        if website_url := user_data.get("website_url"):
            items.append(
                ScrapedItem(
                    category="profile", key="website", value=website_url, url=None
                )
            )

        if github_username := user_data.get("github_username"):
            items.append(
                ScrapedItem(
                    category="profile",
                    key="github",
                    value=github_username,
                    url=f"https://github.com/{github_username}",
                )
            )

        if twitter_username := user_data.get("twitter_username"):
            items.append(
                ScrapedItem(
                    category="profile",
                    key="twitter",
                    value=twitter_username,
                    url=f"https://twitter.com/{twitter_username}",
                )
            )

        # Article items
        for article in articles_data:
            items.append(
                ScrapedItem(
                    category="article",
                    key="title",
                    value={
                        "title": article.get("title"),
                        "tags": article.get("tag_list", []),
                        "reactions": article.get("public_reactions_count", 0),
                        "comments": article.get("comments_count", 0),
                    },
                    url=article.get("url"),
                )
            )

        return items
