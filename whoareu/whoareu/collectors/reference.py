"""Collector that structures a character reference for downstream synthesis."""

from __future__ import annotations

from whoareu.collectors.base import BaseCollector
from whoareu.models import AgentSpec


class ReferenceCollector(BaseCollector):
    """Captures a reference character and prepares it for the synthesizer.

    No LLM call is made here -- the collector simply structures the input so
    the synthesizer can later extract personality traits from the reference.
    """

    def collect(
        self,
        *,
        character: str,
        agent_name: str | None = None,
        **kwargs: object,
    ) -> AgentSpec:
        """Return an AgentSpec seeded from a character reference.

        Parameters
        ----------
        character:
            Name or description of the reference character (e.g. "Jarvis from
            Iron Man" or a multi-sentence character sketch).
        agent_name:
            Optional explicit name for the agent. Falls back to *None* so the
            synthesizer can decide.
        """
        personality = (
            f"Based on the reference character '{character}', "
            "extract and adopt their core personality traits, "
            "speech patterns, and behavioral tendencies."
        )
        return AgentSpec(
            name=agent_name,
            reference_character=character,
            personality=personality,
        )
