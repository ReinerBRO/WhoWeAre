"""Generic web scraper -- fallback for any URL not matched by platform-specific scrapers."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import trafilatura

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper
from whoami.utils.http import fetch_text

_TABLE_NOISE_RE = re.compile(r"^[\s|_\-+=]+$")

logger = logging.getLogger(__name__)


class GenericScraper(BaseScraper):
    """Extract main content from any web page using trafilatura."""

    url_patterns: list[str] = ["*"]

    def get_platform_name(self) -> str:
        return "generic"

    def can_handle(self, url: str) -> bool:
        return True

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        domain = self._extract_domain(url)

        try:
            html = await fetch_text(url, timeout=config.timeout)
        except Exception:
            logger.warning("Failed to fetch %s", url, exc_info=True)
            return ScrapedData(platform=domain, source_url=url)

        extracted = self._extract(html, url)
        if extracted is None:
            return ScrapedData(platform=domain, source_url=url)

        # Fallback: pull <title> from HTML when trafilatura finds none.
        if not extracted.get("title"):
            extracted["title"] = self._extract_html_title(html)

        items = self._build_items(extracted, url)
        bio = extracted.get("description") or self._first_paragraph(extracted.get("text"))
        raw = {k: v for k, v in extracted.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}

        return ScrapedData(
            platform=domain,
            bio=bio,
            items=items,
            raw=raw,
            source_url=url,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_domain(url: str) -> str:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.netloc or parsed.path.split("/")[0]
        return host.removeprefix("www.")

    @staticmethod
    def _extract(html: str, url: str) -> dict[str, Any] | None:
        try:
            result = trafilatura.bare_extraction(
                html,
                url=url,
                include_formatting=True,
                include_links=True,
                as_dict=True,
            )
            return result if isinstance(result, dict) else None
        except Exception:
            logger.warning("trafilatura extraction failed for %s", url, exc_info=True)
            return None

    @staticmethod
    def _build_items(data: dict[str, Any], url: str) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        field_map: dict[str, str] = {
            "title": "title",
            "author": "author",
            "text": "text",
        }
        for src_key, item_key in field_map.items():
            value = data.get(src_key)
            if value:
                items.append(
                    ScrapedItem(category="content", key=item_key, value=value, url=url)
                )
        return items

    @staticmethod
    def _first_paragraph(text: str | None) -> str | None:
        if not text:
            return None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not _TABLE_NOISE_RE.match(stripped) and len(stripped) > 10:
                return stripped
        return None

    @staticmethod
    def _extract_html_title(html: str) -> str | None:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            return title if title else None
        return None
