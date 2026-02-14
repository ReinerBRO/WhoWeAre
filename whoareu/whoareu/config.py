"""Configuration for whoareu."""

from __future__ import annotations

import os
from dataclasses import dataclass

from llmkit import LLMConfig


@dataclass(frozen=True)
class Config:
    """Runtime configuration, populated from environment variables."""

    llm: LLMConfig = LLMConfig()
    language: str = "zh"
    output_dir: str = "."
    install_path: str | None = None

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            llm=LLMConfig.from_env(),
            language=os.environ.get("WHOAREU_LANGUAGE", cls.language),
            install_path=os.environ.get("WHOAREU_INSTALL_PATH"),
        )
