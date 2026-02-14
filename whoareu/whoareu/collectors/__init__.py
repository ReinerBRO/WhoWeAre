"""Collector implementations for whoareu."""

from whoareu.collectors.interactive import InteractiveCollector
from whoareu.collectors.prompt import PromptCollector
from whoareu.collectors.reference import ReferenceCollector
from whoareu.collectors.template import TemplateCollector

__all__: list[str] = [
    "InteractiveCollector",
    "PromptCollector",
    "ReferenceCollector",
    "TemplateCollector",
]
