"""Core data models for whoami."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScraperConfig(BaseModel, frozen=True):
    """Configuration passed to each scraper."""

    timeout: float = 30.0
    max_items: int = 50
    extra: dict[str, Any] = Field(default_factory=dict)


class ScrapedItem(BaseModel, frozen=True):
    """A single piece of scraped information."""

    category: str
    key: str
    value: Any
    url: str | None = None


class ScrapedData(BaseModel, frozen=True):
    """Aggregated result from a single scraper run."""

    platform: str
    username: str | None = None
    bio: str | None = None
    items: list[ScrapedItem] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    source_url: str = ""
