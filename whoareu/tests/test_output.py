"""Tests for file output utilities."""

from __future__ import annotations

from pathlib import Path

from whoareu.models import GeneratedFiles
from whoareu.output import write_files


_FILES = GeneratedFiles(
    identity_md="# IDENTITY\nTest",
    soul_md="# SOUL\nTest",
)


def test_write_files(tmp_path: Path) -> None:
    paths = write_files(_FILES, str(tmp_path))
    assert len(paths) == 2
    names = {p.name for p in paths}
    assert names == {"IDENTITY.md", "SOUL.md"}
    for p in paths:
        assert p.exists()
        assert p.read_text().startswith("#")


def test_write_creates_directory(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "dir"
    paths = write_files(_FILES, str(out))
    assert out.exists()
    assert len(paths) == 2
