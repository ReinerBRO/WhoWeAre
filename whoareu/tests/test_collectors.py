"""Tests for whoareu collectors."""

from __future__ import annotations

import pytest

from whoareu.collectors.prompt import (
    PromptCollector,
    _extract_creature,
    _extract_emoji,
    _extract_name,
    _extract_vibe_keywords,
)
from whoareu.collectors.reference import ReferenceCollector
from whoareu.collectors.template import TemplateCollector


# ---------------------------------------------------------------------------
# PromptCollector
# ---------------------------------------------------------------------------


class TestExtractName:
    def test_chinese_pattern(self) -> None:
        assert _extract_name("一个叫小夜的助手") == "小夜的助手"

    def test_named_pattern(self) -> None:
        assert _extract_name("an agent named Friday") == "Friday"

    def test_called_pattern(self) -> None:
        assert _extract_name("called Neko") == "Neko"

    def test_no_match(self) -> None:
        assert _extract_name("a cool agent") is None


class TestExtractEmoji:
    def test_finds_emoji(self) -> None:
        assert _extract_emoji("签名是🌙") == "🌙"

    def test_no_emoji(self) -> None:
        assert _extract_emoji("no emoji here") is None


class TestExtractCreature:
    def test_cat(self) -> None:
        assert _extract_creature("一只猫娘") == "机器猫"

    def test_assistant(self) -> None:
        assert _extract_creature("an AI assistant") == "AI助手"

    def test_no_match(self) -> None:
        assert _extract_creature("a mysterious being") is None


class TestExtractVibeKeywords:
    def test_chinese_pattern(self) -> None:
        result = _extract_vibe_keywords("性格是冷静、毒舌、可靠")
        assert result == ["冷静", "毒舌", "可靠"]

    def test_english_pattern(self) -> None:
        result = _extract_vibe_keywords("vibe: calm, sharp, reliable")
        assert result == ["calm", "sharp", "reliable"]

    def test_no_match(self) -> None:
        assert _extract_vibe_keywords("just a normal description") == []


class TestPromptCollector:
    def test_basic_prompt(self) -> None:
        spec = PromptCollector().collect(prompt="一个叫Neko的猫娘助手🐱")
        assert spec.name == "Neko的猫娘助手🐱"  # regex captures greedily
        assert spec.creature == "机器猫"
        assert spec.emoji == "🐱"
        assert spec.personality == "一个叫Neko的猫娘助手🐱"

    def test_minimal_prompt(self) -> None:
        spec = PromptCollector().collect(prompt="a cool agent")
        assert spec.name is None
        assert spec.creature is None
        assert spec.personality == "a cool agent"


# ---------------------------------------------------------------------------
# TemplateCollector
# ---------------------------------------------------------------------------


class TestTemplateCollector:
    def test_load_professional(self) -> None:
        spec = TemplateCollector().collect(template_name="professional")
        assert spec.creature == "AI 助手"
        assert spec.safety_level == "strict"
        assert spec.template_base == "professional"

    def test_load_otaku(self) -> None:
        spec = TemplateCollector().collect(template_name="otaku")
        assert spec.creature == "数字精灵"
        assert spec.group_chat_style == "active"

    def test_extra_prompt_overlay(self) -> None:
        spec = TemplateCollector().collect(
            template_name="casual",
            extra_prompt="但要更毒舌一点",
        )
        assert "但要更毒舌一点" in (spec.personality or "")
        assert spec.extra_instructions == "但要更毒舌一点"

    def test_missing_template(self) -> None:
        with pytest.raises(FileNotFoundError):
            TemplateCollector().collect(template_name="nonexistent")

    def test_path_traversal_blocked(self) -> None:
        with pytest.raises(ValueError, match="escapes"):
            TemplateCollector().collect(template_name="../../etc/passwd")


# ---------------------------------------------------------------------------
# ReferenceCollector
# ---------------------------------------------------------------------------


class TestReferenceCollector:
    def test_basic_reference(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "whoareu.collectors.reference._fetch_reference_context",
            lambda *_args, **_kwargs: "",
        )
        spec = ReferenceCollector().collect(character="贾维斯")
        assert spec.reference_character == "贾维斯"
        assert "贾维斯" in (spec.personality or "")
        assert spec.name is None

    def test_with_agent_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "whoareu.collectors.reference._fetch_reference_context",
            lambda *_args, **_kwargs: "",
        )
        spec = ReferenceCollector().collect(
            character="Jarvis from Iron Man",
            agent_name="Friday",
        )
        assert spec.name == "Friday"
        assert spec.reference_character == "Jarvis from Iron Man"

    def test_reference_with_wiki_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "whoareu.collectors.reference._fetch_reference_context",
            lambda *_args, **_kwargs: "[Wikipedia/zh] 贾维斯是托尼的智能管家。",
        )
        spec = ReferenceCollector().collect(character="贾维斯", language="zh")
        assert "Ground your output" in (spec.personality or "")
        assert spec.extra_instructions is not None
        assert "Wikipedia/zh" in spec.extra_instructions

    def test_reference_uses_alias_candidates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "whoareu.collectors.reference._expand_reference_queries_with_llm",
            lambda *_args, **_kwargs: ["Hatsune Miku", "初音未来"],
        )

        captured: dict[str, object] = {}

        def fake_fetch(
            character: str,
            language: str,
            *,
            query_candidates: list[str] | None = None,
        ) -> str:
            captured["character"] = character
            captured["language"] = language
            captured["query_candidates"] = query_candidates
            return ""

        monkeypatch.setattr(
            "whoareu.collectors.reference._fetch_reference_context",
            fake_fetch,
        )

        spec = ReferenceCollector().collect(
            character="初音未来",
            language="zh",
            llm=object(),  # patched resolver ignores actual LLMConfig usage
            resolve_alias=True,
        )

        assert captured["character"] == "初音未来"
        assert captured["language"] == "zh"
        assert captured["query_candidates"] == ["Hatsune Miku", "初音未来"]
        assert spec.extra_instructions is not None
        assert "Reference name candidates" in spec.extra_instructions
