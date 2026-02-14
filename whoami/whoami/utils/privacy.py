"""Privacy filter — strip sensitive information from scraped data."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")),
    ("phone", re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}")),
    ("id_card", re.compile(r"\b\d{17}[\dXx]\b")),
    ("ip_address", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
]


def strip_sensitive(text: str) -> str:
    """Remove emails, phone numbers, ID card numbers, and IPs from text."""
    for _name, pattern in _PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def clean_scraped_text(text: str | None) -> str | None:
    if text is None:
        return None
    return strip_sensitive(text.strip())
