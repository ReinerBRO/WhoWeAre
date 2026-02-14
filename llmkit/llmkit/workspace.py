"""OpenClaw workspace path resolution.

Replicates the TypeScript resolution logic from:
  src/infra/home-dir.ts        — home directory
  src/config/paths.ts           — state dir & config file
  src/agents/workspace.ts       — default workspace directory
  src/agents/agent-scope.ts     — config-aware workspace resolution
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_LEGACY_STATE_DIRNAMES = (".clawdbot", ".moltbot", ".moldbot")
_NEW_STATE_DIRNAME = ".openclaw"
_CONFIG_FILENAME = "openclaw.json"
_LEGACY_CONFIG_FILENAMES = ("clawdbot.json", "moltbot.json", "moldbot.json")

# Workspace file constants (mirrors DEFAULT_*_FILENAME in workspace.ts)
AGENTS_FILENAME = "AGENTS.md"
SOUL_FILENAME = "SOUL.md"
IDENTITY_FILENAME = "IDENTITY.md"
USER_FILENAME = "USER.md"
TOOLS_FILENAME = "TOOLS.md"
HEARTBEAT_FILENAME = "HEARTBEAT.md"
BOOTSTRAP_FILENAME = "BOOTSTRAP.md"
MEMORY_FILENAME = "MEMORY.md"
MEMORY_ALT_FILENAME = "memory.md"

__all__ = [
    "AGENTS_FILENAME",
    "BOOTSTRAP_FILENAME",
    "HEARTBEAT_FILENAME",
    "IDENTITY_FILENAME",
    "MEMORY_ALT_FILENAME",
    "MEMORY_FILENAME",
    "SOUL_FILENAME",
    "TOOLS_FILENAME",
    "USER_FILENAME",
    "resolve_workspace",
]


def _expand_path(raw: str) -> Path:
    """Expand ~ prefix and resolve to absolute path.

    Returns cwd-relative resolution for non-empty strings,
    or raises ValueError for empty/whitespace-only input.
    """
    trimmed = raw.strip()
    if not trimmed:
        raise ValueError("empty path")
    p = Path(trimmed)
    if trimmed.startswith("~"):
        p = p.expanduser()
    return p.resolve()


def _resolve_home() -> Path:
    """Resolve effective home directory, respecting OPENCLAW_HOME.

    Mirrors: src/infra/home-dir.ts → resolveRequiredHomeDir
    (always returns a path; falls back to Path.home()).
    """
    explicit = os.environ.get("OPENCLAW_HOME", "").strip()
    if explicit:
        return _expand_path(explicit)
    return Path.home()


def _all_state_dirs() -> list[Path]:
    """Return all candidate state directories (new + legacy), in priority order."""
    home = _resolve_home()
    return [home / _NEW_STATE_DIRNAME] + [home / d for d in _LEGACY_STATE_DIRNAMES]


def _resolve_state_dir() -> Path:
    """Resolve OpenClaw state directory.

    Mirrors: src/config/paths.ts → resolveStateDir
    """
    override = (
        os.environ.get("OPENCLAW_STATE_DIR", "").strip()
        or os.environ.get("CLAWDBOT_STATE_DIR", "").strip()
    )
    if override:
        return _expand_path(override)

    for d in _all_state_dirs():
        if d.exists():
            return d

    # Default to new dir even if it doesn't exist yet
    return _all_state_dirs()[0]


def _find_config_path() -> Path | None:
    """Find the OpenClaw config file.

    Mirrors: src/config/paths.ts → resolveDefaultConfigCandidates
    Searches across ALL state directories (new + legacy), each with
    all config filenames, matching the TS behavior.
    """
    override = (
        os.environ.get("OPENCLAW_CONFIG_PATH", "").strip()
        or os.environ.get("CLAWDBOT_CONFIG_PATH", "").strip()
    )
    if override:
        p = Path(override).expanduser().resolve()
        return p if p.is_file() else None

    # Search all state dirs × all config filenames
    for state_dir in _all_state_dirs():
        for filename in (_CONFIG_FILENAME, *_LEGACY_CONFIG_FILENAMES):
            candidate = state_dir / filename
            if candidate.is_file():
                return candidate

    return None


def _read_config() -> dict[str, Any]:
    """Read and parse the OpenClaw config file (JSON)."""
    config_path = _find_config_path()
    if not config_path:
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_workspace() -> Path:
    """Resolve the OpenClaw agent workspace directory.

    Combines logic from:
      - src/agents/agent-scope.ts → resolveAgentWorkspaceDir (config reading)
      - src/agents/workspace.ts → resolveDefaultAgentWorkspaceDir (default path)

    Resolution order:
      1. Config file ``agents.defaults.workspace`` (JSON key path)
      2. ``OPENCLAW_PROFILE`` env → ``~/.openclaw/workspace-{profile}``
      3. Default → ``~/.openclaw/workspace``

    Returns:
        Absolute Path to the workspace directory.
    """
    cfg = _read_config()

    workspace_raw = cfg.get("agents", {}).get("defaults", {}).get("workspace", "")
    if isinstance(workspace_raw, str) and workspace_raw.strip():
        return _expand_path(workspace_raw)

    home = _resolve_home()
    profile = os.environ.get("OPENCLAW_PROFILE", "").strip()
    if profile and profile.lower() != "default":
        return home / _NEW_STATE_DIRNAME / f"workspace-{profile}"

    return home / _NEW_STATE_DIRNAME / "workspace"
