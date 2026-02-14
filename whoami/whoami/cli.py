"""CLI entry point for whoami."""

from __future__ import annotations

import asyncio
import sys
from functools import lru_cache
from pathlib import Path

import click

from whoami.config import Config
from whoami.models import ScrapedData, ScraperConfig


@lru_cache(maxsize=1)
def _build_router():
    """Build a LinkRouter with all available scrapers registered."""
    from whoami.router import LinkRouter
    from whoami.scrapers import get_all_scrapers

    router = LinkRouter()
    for scraper in get_all_scrapers():
        router.register(scraper)
    return router


async def _run(
    links: list[str],
    config: Config,
) -> list[ScrapedData]:
    """Scrape all links concurrently."""
    router = _build_router()
    scraper_config = ScraperConfig(
        timeout=config.http_timeout,
        max_items=config.max_items_per_platform,
        extra={
            "github_token": config.github_token,
            "youtube_api_key": config.youtube_api_key,
            "steam_api_key": config.steam_api_key,
        },
    )

    tasks = []
    from whoami.scrapers.generic import GenericScraper

    generic = GenericScraper()
    for url in links:
        scraper = router.resolve(url) or generic
        click.echo(f"  Scraping {scraper.get_platform_name()}: {url}")
        tasks.append(scraper.scrape(url, scraper_config))

    results: list[ScrapedData] = []
    for coro in asyncio.as_completed(tasks):
        try:
            data = await coro
            results.append(data)
            click.echo(f"  ✓ {data.platform} — {len(data.items)} items")
        except Exception as e:
            click.echo(f"  ✗ Error: {e}", err=True)
    return results


def _detect_platform(url: str) -> str:
    """Return the platform name for a URL, or 'unknown'."""
    router = _build_router()
    scraper = router.resolve(url)
    return scraper.get_platform_name() if scraper else "unknown"


def _interactive_collect() -> list[str]:
    """Interactive REPL for collecting URLs."""
    links: list[str] = []

    click.echo("whoami v0.1.0 — Interactive Mode")
    click.echo("Paste URLs to add them. Commands: list, remove <n>, go, quit\n")

    while True:
        try:
            raw = click.prompt("whoami", prompt_suffix="> ", default="", show_default=False)
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break

        text = raw.strip()
        if not text:
            continue

        cmd = text.lower()

        if cmd in ("quit", "exit", "q"):
            break

        if cmd == "list":
            if not links:
                click.echo("  (no links yet)")
            else:
                for i, url in enumerate(links, 1):
                    platform = _detect_platform(url)
                    click.echo(f"  {i}. [{platform}] {url}")
            continue

        if cmd.startswith("remove "):
            try:
                idx = int(cmd.split(None, 1)[1]) - 1
                removed = links.pop(idx)
                click.echo(f"  Removed: {removed}")
            except (ValueError, IndexError):
                click.echo("  Invalid index. Use 'list' to see entries.")
            continue

        if cmd in ("go", "generate"):
            if not links:
                click.echo("  No links to scrape. Add some URLs first.")
                continue
            break

        # Treat anything else as a URL
        if text.startswith(("http://", "https://")):
            platform = _detect_platform(text)
            links.append(text)
            click.echo(f"  Added [{platform}] ({len(links)} link(s) total)")
        else:
            click.echo(f"  Unknown command: {text}")
            click.echo("  Paste a URL or use: list, remove <n>, go, quit")

    return links


def _scrape_and_output(
    links: list[str],
    config: Config,
    output: str,
    no_llm: bool,
) -> None:
    """Scrape links and produce output."""
    results = asyncio.run(_run(links, config))

    if not results:
        click.echo("\nNo data collected.")
        sys.exit(1)

    if no_llm:
        for r in results:
            click.echo(f"\n=== {r.platform} ({r.source_url}) ===")
            if r.bio:
                click.echo(f"Bio: {r.bio}")
            for item in r.items:
                click.echo(f"  [{item.category}] {item.key}: {item.value}")
        return

    click.echo(f"\nSynthesizing with {config.llm.model}...")
    from whoami.synthesizer import synthesize

    md = asyncio.run(synthesize(results, llm=config.llm))
    Path(output).write_text(md, encoding="utf-8")
    click.echo(f"\n✓ Written to {output}")


@click.command()
@click.option("--link", "-l", multiple=True, help="URL to scrape")
@click.option("--links-file", "-f", type=click.Path(exists=True), help="File with URLs (one per line)")
@click.option("--output", "-o", default="USER.md", help="Output file path")
@click.option("--provider", default=None, help="LLM provider (openai/google/anthropic/glm/minimax/doubao/deepseek/packycode/yunwu/siliconflow/openrouter)")
@click.option("--model", "-m", default=None, help="LLM model (e.g. openai/gpt-4o-mini)")
@click.option("--api-base", default=None, help="LLM API base URL")
@click.option("--api-key", default=None, help="LLM API key")
@click.option("--no-llm", is_flag=True, help="Skip LLM synthesis, output raw data")
def main(
    link: tuple[str, ...],
    links_file: str | None,
    output: str,
    provider: str | None,
    model: str | None,
    api_base: str | None,
    api_key: str | None,
    no_llm: bool,
) -> None:
    """whoami — AI-Powered USER.md Generator."""
    from dataclasses import replace
    from llmkit import LLMConfig, get_provider

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

    all_links = list(link)
    if links_file:
        all_links.extend(
            line.strip()
            for line in Path(links_file).read_text().splitlines()
            if line.strip() and not line.startswith("#")
        )

    if not all_links:
        all_links = _interactive_collect()
        if not all_links:
            click.echo("No links collected. Bye!")
            return

    click.echo(f"whoami v0.1.0 — scraping {len(all_links)} link(s)...\n")
    _scrape_and_output(all_links, config, output, no_llm)


if __name__ == "__main__":
    main()
