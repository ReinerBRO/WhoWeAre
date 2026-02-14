"""Medium scraper using RSS feed."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper
from whoami.utils.http import fetch_text


class MediumScraper(BaseScraper):
    """Scraper for Medium profiles via RSS feed."""

    url_patterns = ["medium.com/*", "*.medium.com*"]

    def get_platform_name(self) -> str:
        return "Medium"

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        username = self._extract_username(url)

        # Fetch RSS feed
        rss_url = f"https://medium.com/feed/@{username}"
        rss_text = await fetch_text(rss_url, timeout=config.timeout)

        # Parse RSS XML
        root = ET.fromstring(rss_text)
        channel = root.find("channel")

        if channel is None:
            raise ValueError("Invalid RSS feed: no channel element found")

        items = self._build_items(channel, config.max_items)
        author_name = self._extract_author_name(channel)

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=None,
            items=items,
            raw={"rss_url": rss_url, "author_name": author_name},
            scraped_at=datetime.utcnow(),
            source_url=url,
        )

    def _extract_username(self, url: str) -> str:
        """Extract username from Medium URL."""
        parsed = urlparse(url if "://" in url else f"https://{url}")
        path = parsed.path.strip("/")

        # Handle @username format
        if "@" in path:
            username_part = path.split("@")[1].split("/")[0]
            return username_part

        # Handle subdomain format (username.medium.com)
        if parsed.netloc.endswith(".medium.com"):
            return parsed.netloc.split(".")[0]

        return ""

    def _extract_author_name(self, channel: ET.Element) -> str | None:
        """Extract author name from RSS channel."""
        # Try dc:creator first
        creator = channel.find(".//{http://purl.org/dc/elements/1.1/}creator")
        if creator is not None and creator.text:
            return creator.text

        # Fallback to title
        title = channel.find("title")
        if title is not None and title.text:
            # Medium RSS titles are often "Stories by Author Name on Medium"
            text = title.text
            if " by " in text:
                return text.split(" by ")[1].split(" on ")[0]

        return None

    def _build_items(
        self, channel: ET.Element, max_items: int
    ) -> list[ScrapedItem]:
        """Build scraped items from RSS channel."""
        items = []

        # Extract author name as profile item
        author_name = self._extract_author_name(channel)
        if author_name:
            items.append(
                ScrapedItem(
                    category="profile",
                    key="name",
                    value=author_name,
                    url=None,
                )
            )

        # Extract articles
        article_items = channel.findall("item")
        for article in article_items[:max_items]:
            title_elem = article.find("title")
            link_elem = article.find("link")
            pub_date_elem = article.find("pubDate")

            # Extract categories/tags
            categories = [
                cat.text for cat in article.findall("category") if cat.text
            ]

            article_data = {
                "title": title_elem.text if title_elem is not None else None,
                "published_at": pub_date_elem.text if pub_date_elem is not None else None,
                "tags": categories,
            }

            items.append(
                ScrapedItem(
                    category="article",
                    key="title",
                    value=article_data,
                    url=link_elem.text if link_elem is not None else None,
                )
            )

        return items
