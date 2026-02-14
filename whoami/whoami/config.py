"""Configuration management for whoami."""

from __future__ import annotations

import os
from dataclasses import dataclass

from llmkit import LLMConfig


@dataclass(frozen=True)
class Config:
    """Global configuration."""

    llm: LLMConfig = LLMConfig()
    github_token: str | None = None
    youtube_api_key: str | None = None
    steam_api_key: str | None = None
    twitter_bearer_token: str | None = None
    http_timeout: float = 30.0
    max_items_per_platform: int = 50

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            llm=LLMConfig.from_env(),
            github_token=os.getenv("GITHUB_TOKEN"),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
            steam_api_key=os.getenv("STEAM_API_KEY"),
            twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            http_timeout=float(os.getenv("WHOAMI_TIMEOUT", "30")),
            max_items_per_platform=int(os.getenv("WHOAMI_MAX_ITEMS", "50")),
        )
