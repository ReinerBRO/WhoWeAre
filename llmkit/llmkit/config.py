"""Shared LLM configuration used by whoami and whoareu."""

from __future__ import annotations

import os
from dataclasses import dataclass

from llmkit.providers import ProviderInfo, get_provider


@dataclass(frozen=True)
class LLMConfig:
    """LLM connection settings."""

    model: str = "openai/gpt-4o-mini"
    api_base: str | None = None
    api_key: str | None = None
    provider: str | None = None

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Build config from WWA_* environment variables."""
        provider_name = os.getenv("WWA_PROVIDER")
        provider = get_provider(provider_name) if provider_name else None

        model = os.getenv("WWA_MODEL")
        api_base = os.getenv("WWA_API_BASE")
        api_key = os.getenv("WWA_API_KEY")

        if provider and not model:
            model = provider.default_model
        if provider and not api_base:
            api_base = provider.api_base
        if provider and not api_key:
            api_key = os.getenv(provider.env_key)

        return cls(
            model=model or "openai/gpt-4o-mini",
            api_base=api_base,
            api_key=api_key,
            provider=provider_name,
        )

    def to_litellm_kwargs(self) -> dict[str, str]:
        """Return kwargs suitable for litellm.acompletion()."""
        kwargs: dict[str, str] = {"model": self.model}
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return kwargs
