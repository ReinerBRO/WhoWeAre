"""Base collector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from whoareu.models import AgentSpec


class BaseCollector(ABC):
    """All input collectors must implement this interface."""

    @abstractmethod
    def collect(self, **kwargs: object) -> AgentSpec:
        """Gather user intent and return a normalised AgentSpec."""
        ...
