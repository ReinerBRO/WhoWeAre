"""Steam community profile scraper."""

from __future__ import annotations

import html as html_mod
import re
from urllib.parse import urlparse

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper
from whoami.utils.http import fetch_text


class SteamScraper(BaseScraper):
    """Scrape public Steam community profiles (no API key needed)."""

    url_patterns: list[str] = [
        "store.steampowered.com/*",
        "steamcommunity.com/*",
    ]

    def get_platform_name(self) -> str:
        return "Steam"

    async def scrape(self, url: str, config: ScraperConfig) -> ScrapedData:
        profile_url = self._resolve_profile_url(url)
        raw_html = await fetch_text(profile_url, timeout=config.timeout)

        username = self._parse_username(raw_html)
        bio = self._parse_bio(raw_html)
        items: list[ScrapedItem] = []

        if "This profile is private" in raw_html:
            items.append(
                ScrapedItem(
                    category="profile",
                    key="visibility",
                    value="private",
                )
            )
            return ScrapedData(
                platform=self.get_platform_name(),
                username=username,
                bio=None,
                items=items,
                raw={"profile_url": profile_url},
                source_url=profile_url,
            )

        # Real name and location
        real_name = self._parse_real_name(raw_html)
        if real_name:
            items.append(
                ScrapedItem(category="profile", key="real_name", value=real_name)
            )

        location = self._parse_location(raw_html)
        if location:
            items.append(
                ScrapedItem(category="profile", key="location", value=location)
            )

        # Level
        level = self._parse_level(raw_html)
        if level is not None:
            items.append(
                ScrapedItem(category="stats", key="level", value=level)
            )

        # Game count
        game_count = self._parse_game_count(raw_html)
        if game_count is not None:
            items.append(
                ScrapedItem(category="stats", key="game_count", value=game_count)
            )

        # Recent games
        recent_games = self._parse_recent_games(raw_html)
        for game in recent_games[: config.max_items]:
            items.append(
                ScrapedItem(
                    category="game",
                    key=game["name"],
                    value=game.get("hours", "unknown"),
                    url=game.get("url"),
                )
            )

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=bio,
            items=items,
            raw={"profile_url": profile_url},
            source_url=profile_url,
        )

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_profile_url(url: str) -> str:
        """Convert any Steam URL into a community profile URL."""
        if "://" not in url:
            url = f"https://{url}"
        parsed = urlparse(url)

        # Already a community profile URL
        if "steamcommunity.com" in parsed.netloc:
            # Strip query/fragment, keep path
            path = parsed.path.rstrip("/")
            return f"https://steamcommunity.com{path}"

        # store.steampowered.com -- can't auto-redirect to a profile,
        # but treat the path as a hint if it looks like /id/ or /profiles/
        if "store.steampowered.com" in parsed.netloc:
            path = parsed.path.rstrip("/")
            return f"https://steamcommunity.com{path}"

        return url

    # ------------------------------------------------------------------
    # HTML parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_tags(text: str) -> str:
        """Remove HTML tags and decode entities."""
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html_mod.unescape(text)
        return text.strip()

    def _parse_username(self, raw_html: str) -> str | None:
        m = re.search(
            r'<span class="actual_persona_name">(.*?)</span>', raw_html
        )
        return self._strip_tags(m.group(1)) if m else None

    def _parse_bio(self, raw_html: str) -> str | None:
        m = re.search(
            r'<div class="profile_summary[^"]*"[^>]*>(.*?)</div>',
            raw_html,
            re.DOTALL,
        )
        if not m:
            return None
        text = self._strip_tags(m.group(1))
        return text if text else None

    def _parse_real_name(self, raw_html: str) -> str | None:
        m = re.search(
            r'header_real_name[^>]*>.*?<bdi>(.*?)</bdi>',
            raw_html,
            re.DOTALL,
        )
        return self._strip_tags(m.group(1)) if m else None

    def _parse_location(self, raw_html: str) -> str | None:
        m = re.search(
            r'<div class="header_location">(.*?)</div>',
            raw_html,
            re.DOTALL,
        )
        if not m:
            return None
        text = self._strip_tags(m.group(1))
        return text if text else None

    def _parse_level(self, raw_html: str) -> int | None:
        m = re.search(
            r'<span class="friendPlayerLevelNum">(\d+)</span>', raw_html
        )
        return int(m.group(1)) if m else None

    def _parse_game_count(self, raw_html: str) -> int | None:
        # Appears in badge tooltip: "104 games owned"
        m = re.search(r"(\d+)\s+games?\s+owned", raw_html)
        if m:
            return int(m.group(1))
        # Fallback: profile count link
        m = re.search(
            r'Games</span>\s*&nbsp;\s*<span class="profile_count_link_total">'
            r"\s*(\d+)",
            raw_html,
            re.DOTALL,
        )
        return int(m.group(1)) if m else None

    def _parse_recent_games(self, raw_html: str) -> list[dict[str, str]]:
        games: list[dict[str, str]] = []
        # Each recent game lives in a <div class="recent_game"> block
        for block in re.finditer(
            r'<div class="recent_game">(.*?)</div>\s*</div>\s*</div>',
            raw_html,
            re.DOTALL,
        ):
            content = block.group(1)
            game: dict[str, str] = {}

            # Game name: <a ...>Name</a> inside game_name div
            name_m = re.search(
                r'class="game_name"[^>]*>\s*<a[^>]*>(.*?)</a>',
                content,
                re.DOTALL,
            )
            if name_m:
                game["name"] = self._strip_tags(name_m.group(1))

            # Hours played
            hours_m = re.search(
                r'([\d,.]+)\s+hrs?\s+on\s+record', content
            )
            if hours_m:
                game["hours"] = hours_m.group(1)

            # Game URL from capsule link
            url_m = re.search(
                r'href="(https://steamcommunity\.com/app/\d+)"', content
            )
            if url_m:
                game["url"] = url_m.group(1)

            if game.get("name"):
                games.append(game)

        return games
