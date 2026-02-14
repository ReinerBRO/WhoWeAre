"""Tests for llmkit.workspace — OpenClaw workspace path resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmkit.workspace import (
    _find_config_path,
    _read_config,
    _resolve_home,
    _resolve_state_dir,
    resolve_workspace,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all OPENCLAW env vars so tests are isolated."""
    for key in (
        "OPENCLAW_HOME",
        "OPENCLAW_STATE_DIR",
        "CLAWDBOT_STATE_DIR",
        "OPENCLAW_CONFIG_PATH",
        "CLAWDBOT_CONFIG_PATH",
        "OPENCLAW_PROFILE",
    ):
        monkeypatch.delenv(key, raising=False)


class TestResolveHome:
    def test_default_is_user_home(self) -> None:
        assert _resolve_home() == Path.home()

    def test_openclaw_home_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        assert _resolve_home() == tmp_path.resolve()

    def test_openclaw_home_tilde(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", "~/custom")
        result = _resolve_home()
        assert result == (Path.home() / "custom").resolve()

    def test_whitespace_only_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", "   ")
        assert _resolve_home() == Path.home()


class TestResolveStateDir:
    def test_default_is_dot_openclaw(self) -> None:
        result = _resolve_state_dir()
        assert result == Path.home() / ".openclaw"

    def test_override_via_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
        assert _resolve_state_dir() == tmp_path.resolve()

    def test_legacy_env_var(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("CLAWDBOT_STATE_DIR", str(tmp_path))
        assert _resolve_state_dir() == tmp_path.resolve()

    def test_legacy_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        (tmp_path / ".clawdbot").mkdir()
        assert _resolve_state_dir() == tmp_path / ".clawdbot"

    def test_new_dir_preferred_over_legacy(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        (tmp_path / ".openclaw").mkdir()
        (tmp_path / ".clawdbot").mkdir()
        assert _resolve_state_dir() == tmp_path / ".openclaw"


class TestFindConfigPath:
    def test_none_when_no_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        assert _find_config_path() is None

    def test_finds_openclaw_json(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        state = tmp_path / ".openclaw"
        state.mkdir()
        cfg = state / "openclaw.json"
        cfg.write_text("{}", encoding="utf-8")
        assert _find_config_path() == cfg

    def test_finds_legacy_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        state = tmp_path / ".openclaw"
        state.mkdir()
        cfg = state / "clawdbot.json"
        cfg.write_text("{}", encoding="utf-8")
        assert _find_config_path() == cfg

    def test_searches_across_legacy_state_dirs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Config in a legacy state dir should be found even if .openclaw exists."""
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        # .openclaw exists but has no config
        (tmp_path / ".openclaw").mkdir()
        # Config lives in .moltbot
        legacy = tmp_path / ".moltbot"
        legacy.mkdir()
        cfg = legacy / "openclaw.json"
        cfg.write_text("{}", encoding="utf-8")
        assert _find_config_path() == cfg

    def test_override_via_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cfg = tmp_path / "custom.json"
        cfg.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(cfg))
        assert _find_config_path() == cfg.resolve()

    def test_override_nonexistent_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(tmp_path / "nope.json"))
        assert _find_config_path() is None

    def test_legacy_config_path_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cfg = tmp_path / "legacy.json"
        cfg.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("CLAWDBOT_CONFIG_PATH", str(cfg))
        assert _find_config_path() == cfg.resolve()


class TestReadConfig:
    def test_malformed_json_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        state = tmp_path / ".openclaw"
        state.mkdir()
        cfg = state / "openclaw.json"
        cfg.write_text("{invalid json!!!", encoding="utf-8")
        assert _read_config() == {}

    def test_non_dict_json_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        state = tmp_path / ".openclaw"
        state.mkdir()
        cfg = state / "openclaw.json"
        cfg.write_text('"just a string"', encoding="utf-8")
        assert _read_config() == {}

    def test_no_config_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        assert _read_config() == {}


class TestResolveWorkspace:
    def test_default_workspace(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        result = resolve_workspace()
        assert result == tmp_path / ".openclaw" / "workspace"

    def test_profile_workspace(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        monkeypatch.setenv("OPENCLAW_PROFILE", "dev")
        result = resolve_workspace()
        assert result == tmp_path / ".openclaw" / "workspace-dev"

    def test_profile_default_ignored(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        monkeypatch.setenv("OPENCLAW_PROFILE", "default")
        result = resolve_workspace()
        assert result == tmp_path / ".openclaw" / "workspace"

    def test_config_workspace_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        state = tmp_path / ".openclaw"
        state.mkdir()
        custom_ws = tmp_path / "my-workspace"
        cfg = state / "openclaw.json"
        cfg.write_text(
            json.dumps({"agents": {"defaults": {"workspace": str(custom_ws)}}}),
            encoding="utf-8",
        )
        assert resolve_workspace() == custom_ws.resolve()

    def test_config_takes_priority_over_profile(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        monkeypatch.setenv("OPENCLAW_PROFILE", "dev")
        state = tmp_path / ".openclaw"
        state.mkdir()
        custom_ws = tmp_path / "explicit-ws"
        cfg = state / "openclaw.json"
        cfg.write_text(
            json.dumps({"agents": {"defaults": {"workspace": str(custom_ws)}}}),
            encoding="utf-8",
        )
        assert resolve_workspace() == custom_ws.resolve()

    def test_tilde_in_config_workspace(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        state = tmp_path / ".openclaw"
        state.mkdir()
        cfg = state / "openclaw.json"
        cfg.write_text(
            json.dumps({"agents": {"defaults": {"workspace": "~/my-agents"}}}),
            encoding="utf-8",
        )
        assert resolve_workspace() == (Path.home() / "my-agents").resolve()

    def test_non_string_workspace_in_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """workspace: 42 or workspace: null should be ignored."""
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        state = tmp_path / ".openclaw"
        state.mkdir()
        cfg = state / "openclaw.json"
        cfg.write_text(
            json.dumps({"agents": {"defaults": {"workspace": 42}}}),
            encoding="utf-8",
        )
        assert resolve_workspace() == tmp_path / ".openclaw" / "workspace"

    def test_empty_workspace_in_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """workspace: "" should fall through to default."""
        monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
        state = tmp_path / ".openclaw"
        state.mkdir()
        cfg = state / "openclaw.json"
        cfg.write_text(
            json.dumps({"agents": {"defaults": {"workspace": "  "}}}),
            encoding="utf-8",
        )
        assert resolve_workspace() == tmp_path / ".openclaw" / "workspace"
