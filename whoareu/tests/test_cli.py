"""Tests for the CLI entry point."""

from __future__ import annotations

from click.testing import CliRunner

from whoareu.cli import main


def test_no_input_mode_exits() -> None:
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code != 0
    assert "No input mode" in result.output


def test_dry_run_with_prompt() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--prompt", "一个叫Neko的猫娘", "--dry-run"])
    assert result.exit_code == 0
    assert "AgentSpec" in result.output
    assert "personality" in result.output


def test_dry_run_with_template() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--template", "professional", "--dry-run"])
    assert result.exit_code == 0
    assert "creature" in result.output
    assert "AI 助手" in result.output


def test_dry_run_with_reference() -> None:
    runner = CliRunner()
    result = runner.invoke(main, [
        "--reference", "贾维斯",
        "--name", "Friday",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "Friday" in result.output
    assert "贾维斯" in result.output


def test_dry_run_template_plus_prompt() -> None:
    runner = CliRunner()
    result = runner.invoke(main, [
        "--template", "otaku",
        "--prompt", "但要更毒舌",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "数字精灵" in result.output
    assert "但要更毒舌" in result.output
