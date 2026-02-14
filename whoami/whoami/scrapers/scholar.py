"""Google Scholar profile scraper using the scholarly library."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any
from urllib.parse import parse_qs, urlparse

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class GoogleScholarScraper(BaseScraper):
    """Scrape Google Scholar author profiles via scholarly."""

    url_patterns: list[str] = [
        "scholar.google.com/citations*",
        "scholar.google.com.*/citations*",
    ]

    def get_platform_name(self) -> str:
        return "Google Scholar"

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        author_id = self._extract_author_id(url)
        loop = asyncio.get_running_loop()
        try:
            filled = await loop.run_in_executor(
                None, partial(self._fetch_author, author_id)
            )
        except Exception:
            logger.warning("Failed to fetch scholar %s", author_id, exc_info=True)
            return ScrapedData(platform=self.get_platform_name(), source_url=url)

        items = self._build_items(filled, url, config.max_items)
        bio = filled.get("affiliation")

        return ScrapedData(
            platform=self.get_platform_name(),
            username=filled.get("name"),
            bio=bio,
            items=items,
            raw=self._safe_raw(filled),
            source_url=url,
        )

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_author_id(url: str) -> str:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        qs = parse_qs(parsed.query)
        ids = qs.get("user", [])
        if not ids:
            raise ValueError(f"Cannot extract author ID from URL: {url}")
        return ids[0]

    # ------------------------------------------------------------------
    # Data fetching (synchronous — run via executor)
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_author(author_id: str) -> dict[str, Any]:
        from scholarly import scholarly

        author = scholarly.search_author_id(author_id)
        return scholarly.fill(
            author, sections=["basics", "indices", "counts", "publications"]
        )

    # ------------------------------------------------------------------
    # Item builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_items(
        data: dict[str, Any], url: str, max_pubs: int
    ) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        # Profile fields
        field_map = {
            "name": "name",
            "affiliation": "affiliation",
            "email_domain": "email_domain",
            "citedby": "citations",
            "hindex": "h_index",
            "i10index": "i10_index",
        }
        for src_key, item_key in field_map.items():
            val = data.get(src_key)
            if val is not None and val != "":
                items.append(
                    ScrapedItem(category="profile", key=item_key, value=val, url=url)
                )

        # Research interests
        interests = data.get("interests", [])
        if interests:
            items.append(
                ScrapedItem(
                    category="profile", key="interests", value=interests, url=url
                )
            )

        # Publications
        for pub in data.get("publications", [])[:max_pubs]:
            bib = pub.get("bib", {})
            title = bib.get("title", "untitled")
            items.append(
                ScrapedItem(
                    category="publication",
                    key=title,
                    value={
                        "year": bib.get("pub_year"),
                        "venue": bib.get("citation", ""),
                        "citations": pub.get("num_citations", 0),
                    },
                    url=url,
                )
            )

        return items

    @staticmethod
    def _safe_raw(data: dict[str, Any]) -> dict[str, Any]:
        """Extract JSON-serializable fields for raw storage."""
        safe: dict[str, Any] = {}
        for key in ("name", "affiliation", "interests", "email_domain",
                     "citedby", "hindex", "i10index", "scholar_id"):
            if key in data:
                safe[key] = data[key]
        pubs = []
        for pub in data.get("publications", []):
            bib = pub.get("bib", {})
            pubs.append({
                "title": bib.get("title"),
                "year": bib.get("pub_year"),
                "venue": bib.get("citation", ""),
                "citations": pub.get("num_citations", 0),
            })
        safe["publications"] = pubs
        return safe
