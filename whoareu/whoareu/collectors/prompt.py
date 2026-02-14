"""Collector that parses a natural-language prompt into an AgentSpec."""

from __future__ import annotations

import re

from whoareu.collectors.base import BaseCollector
from whoareu.models import AgentSpec


_EMOJI_RE = re.compile(
    r"[\U0001f300-\U0001f9ff\U00002600-\U000027bf\U0000fe00-\U0000feff]"
)
_NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:叫|名字是|名为|called|named)\s*[\"'「]?(\S+)[\"'」]?", re.I),
]
_CREATURE_KEYWORDS: dict[str, str] = {
    "猫": "机器猫",
    "cat": "机器猫",
    "精灵": "赛博精灵",
    "elf": "赛博精灵",
    "助手": "AI助手",
    "assistant": "AI助手",
}


def _extract_name(text: str) -> str | None:
    for pat in _NAME_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip(".,!?;:。，！？；：")
    return None


def _extract_emoji(text: str) -> str | None:
    m = _EMOJI_RE.search(text)
    return m.group(0) if m else None


def _extract_creature(text: str) -> str | None:
    lower = text.lower()
    for keyword, creature in _CREATURE_KEYWORDS.items():
        if keyword in lower:
            return creature
    return None


def _extract_vibe_keywords(text: str) -> list[str]:
    """Extract vibe-related adjectives from common descriptor patterns."""
    patterns = [
        re.compile(r"(?:风格|性格|特点|vibe)[是为：:\s]+(.+?)(?:[。.!！\n]|$)"),
        re.compile(r"(?:关键词|keywords?)[是为：:\s]+(.+?)(?:[。.!！\n]|$)", re.I),
    ]
    for pat in patterns:
        m = pat.search(text)
        if m:
            raw = m.group(1)
            return [w.strip() for w in re.split(r"[,，、/\s]+", raw) if w.strip()][:5]
    return []


class PromptCollector(BaseCollector):
    """Parses a free-form natural-language prompt into an AgentSpec.

    Uses lightweight regex/keyword extraction -- no LLM call.
    """

    def collect(self, *, prompt: str, **kwargs: object) -> AgentSpec:
        """Extract obvious fields from *prompt* and return an AgentSpec.

        Parameters
        ----------
        prompt:
            A natural-language description of the desired agent persona.
        """
        return AgentSpec(
            name=_extract_name(prompt),
            creature=_extract_creature(prompt),
            emoji=_extract_emoji(prompt),
            vibe_keywords=_extract_vibe_keywords(prompt),
            personality=prompt,
        )
