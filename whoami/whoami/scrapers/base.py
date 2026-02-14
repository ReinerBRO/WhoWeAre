"""Base scraper interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from whoami.models import ScrapedData, ScraperConfig


class BaseScraper(ABC):
    """All scrapers must implement this interface."""

    url_patterns: list[str] = []

    @abstractmethod
    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        """Scrape the given URL and return structured data."""
        ...

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return the human-readable platform name."""
        ...

    def can_handle(self, url: str) -> bool:
        """Check if this scraper can handle the given URL."""
        from fnmatch import fnmatch
        from urllib.parse import urlparse

        parsed = urlparse(url if "://" in url else f"https://{url}")
        host_path = f"{parsed.netloc}{parsed.path}"
        return any(fnmatch(host_path, p) for p in self.url_patterns)
