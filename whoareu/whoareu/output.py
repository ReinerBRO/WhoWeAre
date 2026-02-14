"""File output and installation utilities."""

from __future__ import annotations

from pathlib import Path

import click

from whoareu.models import GeneratedFiles


_FILE_MAP = {
    "IDENTITY.md": "identity_md",
    "SOUL.md": "soul_md",
    "AGENTS.md": "agents_md",
}


def write_files(files: GeneratedFiles, output_dir: str) -> list[Path]:
    """Write generated files to *output_dir*. Returns list of written paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, attr in _FILE_MAP.items():
        path = out / filename
        path.write_text(getattr(files, attr), encoding="utf-8")
        written.append(path)
    return written


def preview_files(files: GeneratedFiles) -> None:
    """Print all generated files to stdout for review."""
    for filename, attr in _FILE_MAP.items():
        content = getattr(files, attr)
        click.echo(f"\n{'=' * 60}")
        click.echo(f"  {filename}")
        click.echo(f"{'=' * 60}\n")
        click.echo(content)


def install_files(files: GeneratedFiles, install_path: str) -> list[Path]:
    """Write files directly into an OpenClaw workspace directory."""
    return write_files(files, install_path)
