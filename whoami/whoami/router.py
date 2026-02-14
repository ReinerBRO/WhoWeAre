"""Link Router — dispatch URLs to the appropriate scraper."""

from __future__ import annotations

from whoami.scrapers.base import BaseScraper


class LinkRouter:
    """Registry of scrapers; routes a URL to the matching scraper."""

    def __init__(self) -> None:
        self._scrapers: list[BaseScraper] = []

    def register(self, scraper: BaseScraper) -> None:
        self._scrapers.append(scraper)

    def resolve(self, url: str) -> BaseScraper | None:
        for scraper in self._scrapers:
            if scraper.can_handle(url):
                return scraper
        return None

    def resolve_all(self, urls: list[str]) -> list[tuple[str, BaseScraper | None]]:
        return [(url, self.resolve(url)) for url in urls]
