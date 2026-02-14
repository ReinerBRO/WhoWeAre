"""Auto-discover and register all scrapers."""

from __future__ import annotations

import importlib

from whoami.scrapers.base import BaseScraper

_SCRAPER_MODULES = [
    "whoami.scrapers.github",
    "whoami.scrapers.gitlab",
    "whoami.scrapers.bilibili",
    "whoami.scrapers.steam",
    "whoami.scrapers.stackoverflow",
    "whoami.scrapers.devto",
    "whoami.scrapers.medium",
    "whoami.scrapers.reddit",
    "whoami.scrapers.zhihu",
    "whoami.scrapers.douban",
    "whoami.scrapers.weibo",
    "whoami.scrapers.scholar",
    "whoami.scrapers.xiaohongshu",
    "whoami.scrapers.generic",  # catch-all, must be last
]


def get_all_scrapers() -> list[BaseScraper]:
    """Import and instantiate all available scrapers."""
    scrapers: list[BaseScraper] = []
    for mod_path in _SCRAPER_MODULES:
        try:
            mod = importlib.import_module(mod_path)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseScraper)
                    and attr is not BaseScraper
                ):
                    scrapers.append(attr())
        except ImportError:
            pass
    return scrapers
