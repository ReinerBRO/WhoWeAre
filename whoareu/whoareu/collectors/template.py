"""Collector that reads a TOML template file and maps it to an AgentSpec."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from whoareu.collectors.base import BaseCollector
from whoareu.models import AgentSpec

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Maps TOML section.key -> AgentSpec field name.
_SECTION_MAP: dict[str, dict[str, str]] = {
    "identity": {
        "name": "name",
        "creature": "creature",
        "emoji": "emoji",
        "vibe_keywords": "vibe_keywords",
        "language": "language",
    },
    "personality": {
        "personality": "personality",
        "communication_style": "communication_style",
        "opinionated": "opinionated",
        "humor_style": "humor_style",
        "reference_character": "reference_character",
    },
    "behavior": {
        "group_chat_style": "group_chat_style",
        "proactivity": "proactivity",
        "safety_level": "safety_level",
        "heartbeat_tasks": "heartbeat_tasks",
        "external_action_policy": "external_action_policy",
    },
}


def _flatten_toml(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten TOML sections into a flat dict keyed by AgentSpec field names."""
    flat: dict[str, Any] = {}
    for section, mapping in _SECTION_MAP.items():
        section_data = data.get(section, {})
        for toml_key, spec_field in mapping.items():
            if toml_key in section_data:
                flat[spec_field] = section_data[toml_key]
    return flat


class TemplateCollector(BaseCollector):
    """Loads a TOML template and optionally merges an extra prompt overlay."""

    def collect(
        self,
        *,
        template_name: str,
        extra_prompt: str | None = None,
        **kwargs: object,
    ) -> AgentSpec:
        """Read *template_name*.toml and return an AgentSpec.

        Parameters
        ----------
        template_name:
            Filename (without extension) inside the ``templates/`` directory.
        extra_prompt:
            Optional free-text that overrides ``extra_instructions`` and is
            appended to ``personality`` when present.
        """
        path = (_TEMPLATES_DIR / f"{template_name}.toml").resolve()
        if not path.is_relative_to(_TEMPLATES_DIR.resolve()):
            raise ValueError(f"Template name escapes templates directory: {template_name}")
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path}")

        with path.open("rb") as fh:
            data = tomllib.load(fh)

        fields = _flatten_toml(data)
        fields["template_base"] = template_name

        if extra_prompt:
            base_personality = fields.get("personality", "") or ""
            merged = (
                f"{base_personality}\n{extra_prompt}" if base_personality else extra_prompt
            )
            fields["personality"] = merged
            fields["extra_instructions"] = extra_prompt

        return AgentSpec(**fields)
