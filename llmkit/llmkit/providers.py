"""Provider registry — base URLs and default models for each LLM provider."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    """Metadata for an LLM provider."""

    name: str
    api_base: str | None  # None = use litellm default
    env_key: str  # environment variable for the API key
    default_model: str
    is_relay: bool = False


# --- Direct providers ---

_OPENAI = ProviderInfo(
    name="openai",
    api_base=None,
    env_key="OPENAI_API_KEY",
    default_model="openai/gpt-4o-mini",
)

_GOOGLE = ProviderInfo(
    name="google",
    api_base=None,
    env_key="GEMINI_API_KEY",
    default_model="gemini/gemini-2.0-flash",
)

_ANTHROPIC = ProviderInfo(
    name="anthropic",
    api_base=None,
    env_key="ANTHROPIC_API_KEY",
    default_model="anthropic/claude-sonnet-4-5-20250929",
)

_GLM = ProviderInfo(
    name="glm",
    api_base="https://open.bigmodel.cn/api/paas/v4",
    env_key="GLM_API_KEY",
    default_model="openai/glm-4-flash",
)

_MINIMAX = ProviderInfo(
    name="minimax",
    api_base="https://api.minimax.chat/v1",
    env_key="MINIMAX_API_KEY",
    default_model="openai/MiniMax-Text-01",
)

_DOUBAO = ProviderInfo(
    name="doubao",
    api_base="https://ark.cn-beijing.volces.com/api/v3",
    env_key="DOUBAO_API_KEY",
    default_model="openai/doubao-1.5-pro-32k",
)

_DEEPSEEK = ProviderInfo(
    name="deepseek",
    api_base="https://api.deepseek.com/v1",
    env_key="DEEPSEEK_API_KEY",
    default_model="openai/deepseek-chat",
)

# --- Relay / proxy providers ---

_PACKYCODE = ProviderInfo(
    name="packycode",
    api_base="https://api.packycode.com/v1",
    env_key="PACKYCODE_API_KEY",
    default_model="openai/gpt-4o-mini",
    is_relay=True,
)

_YUNWU = ProviderInfo(
    name="yunwu",
    api_base="https://yunwu.ai/v1",
    env_key="YUNWU_API_KEY",
    default_model="openai/gpt-4o-mini",
    is_relay=True,
)

_SILICONFLOW = ProviderInfo(
    name="siliconflow",
    api_base="https://api.siliconflow.cn/v1",
    env_key="SILICONFLOW_API_KEY",
    default_model="openai/deepseek-ai/DeepSeek-V3",
    is_relay=True,
)

_OPENROUTER = ProviderInfo(
    name="openrouter",
    api_base="https://openrouter.ai/api/v1",
    env_key="OPENROUTER_API_KEY",
    default_model="openai/openai/gpt-4o-mini",
    is_relay=True,
)

_ZHIZENGZENG = ProviderInfo(
    name="zhizengzeng",
    api_base="https://api.zhizengzeng.com/v1",
    env_key="ZZZ_API_KEY",
    default_model="openai/deepseek-chat",
    is_relay=True,
)

# --- Registry ---

PROVIDERS: dict[str, ProviderInfo] = {
    p.name: p
    for p in [
        _OPENAI, _GOOGLE, _ANTHROPIC, _GLM, _MINIMAX, _DOUBAO, _DEEPSEEK,
        _PACKYCODE, _YUNWU, _SILICONFLOW, _OPENROUTER, _ZHIZENGZENG,
    ]
}


def get_provider(name: str) -> ProviderInfo | None:
    """Look up a provider by name (case-insensitive)."""
    return PROVIDERS.get(name.lower())


def list_providers() -> list[str]:
    """Return all registered provider names."""
    return list(PROVIDERS.keys())
