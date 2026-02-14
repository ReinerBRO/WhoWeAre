"""Tests for output schema validation."""

from __future__ import annotations

from whoareu.schemas import validate_agents, validate_all, validate_identity, validate_soul


_VALID_IDENTITY = """\
# IDENTITY.md

- **Name:** 小夜
- **Creature:** 赛博幽灵
- **Vibe:** 冷静、毒舌、可靠
- **Emoji:** 🌙
"""

_VALID_SOUL = """\
# SOUL.md

## Core Truths
- Be helpful

## Boundaries
- Never leak data

## Vibe
Calm and sharp.

## Continuity
Read memory files each session.
"""

_VALID_AGENTS = """\
# AGENTS.md

## First Run
Read BOOTSTRAP.md.

## Every Session
1. Read SOUL.md
2. Read USER.md

## Memory
Use daily notes.

## Safety
Don't run destructive commands.

## External vs Internal
Ask before sending emails.
"""


class TestValidateIdentity:
    def test_valid(self) -> None:
        assert validate_identity(_VALID_IDENTITY) == []

    def test_missing_name(self) -> None:
        md = "# IDENTITY\n- **Creature:** bot\n- **Vibe:** cool\n- **Emoji:** 🤖"
        missing = validate_identity(md)
        assert "name" in missing

    def test_heading_counts(self) -> None:
        md = "# IDENTITY\n## Name\nFoo\n## Creature\nBot\n## Vibe\ncool\n## Emoji\n🤖"
        assert validate_identity(md) == []


class TestValidateSoul:
    def test_valid(self) -> None:
        assert validate_soul(_VALID_SOUL) == []

    def test_missing_boundaries(self) -> None:
        md = "## Core Truths\nBe good\n## Vibe\nCool\n## Continuity\nRemember"
        missing = validate_soul(md)
        assert "boundaries" in missing


class TestValidateAgents:
    def test_valid(self) -> None:
        assert validate_agents(_VALID_AGENTS) == []

    def test_missing_safety(self) -> None:
        md = "## First Run\nOK\n## Every Session\nOK\n## Memory\nOK"
        missing = validate_agents(md)
        assert "safety" in missing


class TestValidateAll:
    def test_all_valid(self) -> None:
        errors = validate_all(_VALID_IDENTITY, _VALID_SOUL, _VALID_AGENTS)
        assert errors == {}

    def test_mixed_errors(self) -> None:
        errors = validate_all("# empty", _VALID_SOUL, _VALID_AGENTS)
        assert "IDENTITY.md" in errors
        assert "SOUL.md" not in errors
