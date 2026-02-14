"""Tests for the LLM synthesizer (mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from whoareu.models import AgentSpec
from whoareu.synthesizer import _build_spec_description, _strip_code_fences, synthesize


class TestStripCodeFences:
    def test_no_fences(self) -> None:
        assert _strip_code_fences("# Hello") == "# Hello"

    def test_markdown_fence(self) -> None:
        text = "```markdown\n# Hello\nWorld\n```"
        assert _strip_code_fences(text) == "# Hello\nWorld"

    def test_md_fence(self) -> None:
        text = "```md\n# Hello\n```"
        assert _strip_code_fences(text) == "# Hello"

    def test_plain_fence(self) -> None:
        text = "```\n# Hello\n```"
        assert _strip_code_fences(text) == "# Hello"


class TestBuildSpecDescription:
    def test_basic_spec(self) -> None:
        spec = AgentSpec(name="Neko", creature="猫娘")
        desc = _build_spec_description(spec)
        assert "名字: Neko" in desc
        assert "物种/类型: 猫娘" in desc

    def test_skips_none(self) -> None:
        spec = AgentSpec()
        desc = _build_spec_description(spec)
        assert "名字" not in desc

    def test_bool_formatting(self) -> None:
        spec = AgentSpec(opinionated=True)
        desc = _build_spec_description(spec)
        assert "是否有主见: 是" in desc

    def test_list_formatting(self) -> None:
        spec = AgentSpec(vibe_keywords=["冷静", "毒舌"])
        desc = _build_spec_description(spec)
        assert "气质关键词: 冷静, 毒舌" in desc


# ---------------------------------------------------------------------------
# Synthesize (mocked LLM)
# ---------------------------------------------------------------------------

_MOCK_IDENTITY = """\
# IDENTITY.md
- **Name:** TestBot
- **Creature:** AI 助手
- **Vibe:** 冷静、可靠
- **Emoji:** 🤖
"""

_MOCK_SOUL = """\
# SOUL.md
## Core Truths
- Be helpful
## Boundaries
- Never leak data
## Vibe
Calm and reliable.
## Continuity
Read memory files.
"""


def _make_mock_response(content: str) -> AsyncMock:
    """Create a mock litellm response."""
    mock = AsyncMock()
    mock.choices = [AsyncMock()]
    mock.choices[0].message.content = content
    return mock


@pytest.mark.asyncio
async def test_synthesize_calls_llm_twice() -> None:
    responses = [_MOCK_IDENTITY, _MOCK_SOUL]
    call_count = 0

    async def mock_acompletion(**kwargs: object) -> AsyncMock:
        nonlocal call_count
        resp = _make_mock_response(responses[call_count])
        call_count += 1
        return resp

    spec = AgentSpec(name="TestBot", creature="AI 助手")

    with patch("whoareu.synthesizer.litellm.acompletion", side_effect=mock_acompletion):
        files = await synthesize(spec)

    assert call_count == 2
    assert "TestBot" in files.identity_md
    assert "Core Truths" in files.soul_md


@pytest.mark.asyncio
async def test_synthesize_strips_code_fences() -> None:
    fenced = f"```markdown\n{_MOCK_IDENTITY}\n```"
    responses = [fenced, _MOCK_SOUL]
    idx = 0

    async def mock_acompletion(**kwargs: object) -> AsyncMock:
        nonlocal idx
        resp = _make_mock_response(responses[idx])
        idx += 1
        return resp

    spec = AgentSpec(name="TestBot")

    with patch("whoareu.synthesizer.litellm.acompletion", side_effect=mock_acompletion):
        files = await synthesize(spec)

    assert not files.identity_md.startswith("```")
