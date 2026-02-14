"""Output schema validation for generated files."""

from __future__ import annotations

import re


def _extract_headings(md: str) -> list[str]:
    """Return all markdown headings (any level) as lowercase strings."""
    return [
        re.sub(r"^#+\s*", "", line).strip().lower()
        for line in md.splitlines()
        if line.strip().startswith("#")
    ]


def _extract_bold_fields(md: str) -> list[str]:
    """Return **Field:** patterns as lowercase field names."""
    return [m.group(1).lower() for m in re.finditer(r"\*\*(\w[\w\s]*):\*\*", md)]


class SchemaError(Exception):
    """Raised when a generated file fails validation."""

    def __init__(self, file_name: str, missing: list[str]) -> None:
        self.file_name = file_name
        self.missing = missing
        super().__init__(
            f"{file_name} missing required elements: {', '.join(missing)}"
        )


def validate_identity(md: str) -> list[str]:
    """Validate IDENTITY.md contains required fields. Returns list of missing fields."""
    required = ["name", "creature", "vibe", "emoji"]
    fields = _extract_bold_fields(md)
    headings = _extract_headings(md)
    found = set(fields + headings)
    return [r for r in required if r not in found]


def validate_soul(md: str) -> list[str]:
    """Validate SOUL.md contains required sections. Returns list of missing sections."""
    required = ["core truths", "boundaries", "vibe", "continuity"]
    headings = _extract_headings(md)
    return [r for r in required if r not in headings]


def validate_all(
    identity_md: str, soul_md: str
) -> dict[str, list[str]]:
    """Validate both files. Returns dict of file_name -> missing elements."""
    errors: dict[str, list[str]] = {}
    missing = validate_identity(identity_md)
    if missing:
        errors["IDENTITY.md"] = missing
    missing = validate_soul(soul_md)
    if missing:
        errors["SOUL.md"] = missing
    return errors
