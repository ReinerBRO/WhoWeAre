"""Interactive CLI collector using click prompts."""

from __future__ import annotations

import click

from whoareu.collectors.base import BaseCollector
from whoareu.models import AgentSpec

_CREATURE_CHOICES = ["AI助手", "赛博精灵", "机器猫", "自定义"]
_COMM_STYLE_CHOICES = ["正式", "随意", "毒舌", "温暖", "中二"]
_GROUP_CHAT_CHOICES = ["active", "moderate", "reserved"]
_SAFETY_CHOICES = ["strict", "standard", "relaxed"]
_ACTION_POLICY_CHOICES = ["ask", "autonomous", "forbidden"]


class InteractiveCollector(BaseCollector):
    """Walks the user through a three-phase CLI questionnaire."""

    def collect(self, **kwargs: object) -> AgentSpec:
        """Run the interactive questionnaire and return an AgentSpec."""
        # --- Phase 1: Identity ---
        click.echo("\n--- Phase 1: Identity ---")
        name: str = click.prompt("Agent name")
        creature: str = click.prompt(
            "Creature type",
            type=click.Choice(_CREATURE_CHOICES, case_sensitive=False),
        )
        if creature == "自定义":
            creature = click.prompt("Enter custom creature type")
        emoji: str = click.prompt("Emoji")
        vibe_raw: str = click.prompt("3 vibe keywords (comma-separated)")
        vibe_keywords: list[str] = [
            w.strip() for w in vibe_raw.split(",") if w.strip()
        ][:3]

        # --- Phase 2: Personality ---
        click.echo("\n--- Phase 2: Personality ---")
        communication_style: str = click.prompt(
            "Communication style",
            type=click.Choice(_COMM_STYLE_CHOICES, case_sensitive=False),
        )
        opinionated: bool = click.confirm("Opinionated?", default=True)
        humor_style: str = click.prompt("Humor style", default="")

        # --- Phase 3: Behavior ---
        click.echo("\n--- Phase 3: Behavior ---")
        group_chat_style: str = click.prompt(
            "Group chat style",
            type=click.Choice(_GROUP_CHAT_CHOICES, case_sensitive=False),
        )
        safety_level: str = click.prompt(
            "Safety level",
            type=click.Choice(_SAFETY_CHOICES, case_sensitive=False),
        )
        external_action_policy: str = click.prompt(
            "External action policy",
            type=click.Choice(_ACTION_POLICY_CHOICES, case_sensitive=False),
        )
        heartbeat_raw: str = click.prompt(
            "Heartbeat tasks (comma-separated, optional)", default=""
        )
        heartbeat_tasks: list[str] = [
            t.strip() for t in heartbeat_raw.split(",") if t.strip()
        ]

        return AgentSpec(
            name=name,
            creature=creature,
            emoji=emoji,
            vibe_keywords=vibe_keywords,
            communication_style=communication_style,
            opinionated=opinionated,
            humor_style=humor_style or None,
            group_chat_style=group_chat_style,
            safety_level=safety_level,
            external_action_policy=external_action_policy,
            heartbeat_tasks=heartbeat_tasks,
        )
