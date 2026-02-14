"""Core data models for whoareu."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentSpec(BaseModel, frozen=True):
    """Normalised input — every collector produces one of these."""

    # Identity
    name: str | None = None
    creature: str | None = None
    emoji: str | None = None
    vibe_keywords: list[str] = Field(default_factory=list)

    # Personality
    personality: str | None = None
    communication_style: str | None = None
    opinionated: bool = True
    humor_style: str | None = None

    # Behaviour rules
    group_chat_style: str = "moderate"
    proactivity: str = "balanced"
    safety_level: str = "standard"
    heartbeat_tasks: list[str] = Field(default_factory=list)
    external_action_policy: str = "ask"

    # Meta
    language: str = "zh"
    reference_character: str | None = None
    template_base: str | None = None
    extra_instructions: str | None = None


class GeneratedFiles(BaseModel, frozen=True):
    """The two generated Markdown files."""

    identity_md: str
    soul_md: str
