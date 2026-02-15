"""CLI entry point for whoareu."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

import click

from whoareu.config import Config
from whoareu.models import AgentSpec

if TYPE_CHECKING:
    from llmkit import LLMConfig


def _collect_spec(
    prompt: str | None,
    template: str | None,
    interactive: bool,
    reference: str | None,
    name: str | None,
    language: str,
    llm: LLMConfig | None = None,
    resolve_reference_alias: bool = True,
    query_candidates: list[str] | None = None,
) -> AgentSpec:
    """Build an AgentSpec from the chosen input mode."""
    specs: list[AgentSpec] = []

    if template:
        from whoareu.collectors.template import TemplateCollector

        specs.append(TemplateCollector().collect(template_name=template))

    if interactive:
        from whoareu.collectors.interactive import InteractiveCollector

        specs.append(InteractiveCollector().collect())

    if reference:
        from whoareu.collectors.reference import ReferenceCollector

        specs.append(ReferenceCollector().collect(
            character=reference,
            agent_name=name,
            language=language,
            llm=llm,
            resolve_alias=resolve_reference_alias,
            query_candidates=query_candidates,
        ))

    if prompt:
        from whoareu.collectors.prompt import PromptCollector

        specs.append(PromptCollector().collect(prompt=prompt))

    if not specs:
        # No input mode selected — fall back to a bare spec
        return AgentSpec(language=language, name=name)

    # Merge specs: later values override earlier ones (template < reference < prompt)
    return _merge_specs(specs, language=language, name_override=name)


def _merge_specs(
    specs: list[AgentSpec], *, language: str, name_override: str | None
) -> AgentSpec:
    """Merge multiple AgentSpecs. Later specs take priority for non-None fields."""
    merged: dict[str, object] = {}
    for spec in specs:
        for field_name, value in spec.model_dump(exclude_defaults=True).items():
            if value is None or value == [] or value == "":
                continue
            # For list fields, extend rather than replace
            if isinstance(value, list) and field_name in merged:
                existing = merged[field_name]
                if isinstance(existing, list):
                    merged[field_name] = existing + value
                    continue
            merged[field_name] = value
    merged["language"] = language
    if name_override:
        merged["name"] = name_override
    return AgentSpec(**merged)


@click.command()
@click.option("--prompt", "-p", default=None, help="Natural language description of your agent")
@click.option("--template", "-t", default=None, help="Preset template name (professional/casual/otaku/minimalist/chaotic)")
@click.option("--interactive", "-i", is_flag=True, help="Interactive questionnaire mode")
@click.option("--reference", "-r", default=None, help="Reference character for personality extraction")
@click.option("--name", "-n", default=None, help="Agent name")
@click.option("--output", "-o", default=".", help="Output directory")
@click.option("--provider", default=None, help="LLM provider (openai/google/anthropic/glm/minimax/doubao/deepseek/packycode/yunwu/siliconflow/openrouter)")
@click.option("--model", "-m", default=None, help="LLM model (e.g. openai/gpt-4o-mini)")
@click.option("--api-base", default=None, help="LLM API base URL")
@click.option("--api-key", default=None, help="LLM API key")
@click.option("--language", default="zh", help="Output language (zh/en)")
@click.option("--preview", is_flag=True, help="Preview without writing files")
@click.option("--dry-run", is_flag=True, help="Show AgentSpec without calling LLM")
@click.option("--dump-spec", is_flag=True, help="Output spec description text for external synthesis (no LLM call)")
@click.option("--query-candidates", default=None, help="Comma-separated alias candidates for wiki search (used with --dump-spec)")
@click.option("--install", default=None, help="Install directly to OpenClaw workspace path")
def main(
    prompt: str | None,
    template: str | None,
    interactive: bool,
    reference: str | None,
    name: str | None,
    output: str,
    provider: str | None,
    model: str | None,
    api_base: str | None,
    api_key: str | None,
    language: str,
    preview: bool,
    dry_run: bool,
    dump_spec: bool,
    query_candidates: str | None,
    install: str | None,
) -> None:
    """whoareu — AI Agent Persona Generator."""
    from dataclasses import replace
    from llmkit import get_provider

    config = Config.from_env()

    # Build LLM overrides from CLI flags
    llm_overrides: dict[str, object] = {}
    if provider:
        pinfo = get_provider(provider)
        if not pinfo:
            click.echo(f"Unknown provider: {provider}")
            from llmkit import list_providers
            click.echo(f"Available: {', '.join(list_providers())}")
            sys.exit(1)
        if pinfo.api_base:
            llm_overrides["api_base"] = pinfo.api_base
        if not model:
            llm_overrides["model"] = pinfo.default_model
        llm_overrides["provider"] = provider
    if model:
        llm_overrides["model"] = model
    if api_base:
        llm_overrides["api_base"] = api_base
    if api_key:
        llm_overrides["api_key"] = api_key
    if llm_overrides:
        config = replace(config, llm=replace(config.llm, **llm_overrides))

    if not any([prompt, template, interactive, reference]):
        click.echo("No input mode selected. Use --prompt, --template, --interactive, or --reference.")
        sys.exit(1)

    if dump_spec:
        candidates = (
            [c.strip() for c in query_candidates.split(",") if c.strip()]
            if query_candidates
            else None
        )
        spec = _collect_spec(
            prompt,
            template,
            interactive,
            reference,
            name,
            language,
            llm=config.llm,
            resolve_reference_alias=False,
            query_candidates=candidates,
        )
        from whoareu.synthesizer import _build_spec_description

        click.echo(_build_spec_description(spec))
        return

    click.echo("whoareu v0.1.0 — generating agent persona...\n")

    spec = _collect_spec(
        prompt,
        template,
        interactive,
        reference,
        name,
        language,
        llm=config.llm,
        resolve_reference_alias=not dry_run,
    )

    if dry_run:
        click.echo("AgentSpec (dry-run):\n")
        for field_name, value in spec.model_dump().items():
            if value is not None and value != [] and value != "":
                click.echo(f"  {field_name}: {value}")
        return

    click.echo(f"Synthesizing with {config.llm.model}...\n")

    from whoareu.synthesizer import synthesize

    files = asyncio.run(synthesize(spec, llm=config.llm))

    # Validate
    from whoareu.schemas import validate_all

    errors = validate_all(files.identity_md, files.soul_md)
    if errors:
        click.echo("Warning: validation issues detected:", err=True)
        for fname, missing in errors.items():
            click.echo(f"  {fname}: missing {', '.join(missing)}", err=True)
        click.echo("")

    if preview:
        from whoareu.output import preview_files

        preview_files(files)
        return

    from whoareu.output import write_files, install_files

    if install:
        paths = install_files(files, install)
        click.echo(f"Installed to {install}:")
    else:
        paths = write_files(files, output)
        click.echo("Generated files:")

    for p in paths:
        click.echo(f"  ✓ {p}")


if __name__ == "__main__":
    main()
