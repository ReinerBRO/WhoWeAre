"""Xiaohongshu (小红书) scraper implementation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_XHS_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.xiaohongshu.com/",
}


def _extract_user_id(url: str) -> str | None:
    """Extract user ID from a Xiaohongshu URL."""
    m = re.search(r"xiaohongshu\.com/user/profile/([a-zA-Z0-9]+)", url)
    if m:
        return m.group(1)
    return None


def _parse_initial_state(html: str) -> dict[str, Any] | None:
    """Extract __INITIAL_STATE__ JSON from the HTML page."""
    m = re.search(
        r"window\.__INITIAL_STATE__\s*=\s*({.+?})\s*</script>",
        html,
        re.DOTALL,
    )
    if not m:
        return None
    raw = m.group(1)
    # Xiaohongshu uses `undefined` in JSON which is invalid — replace with null
    raw = re.sub(r"\bundefined\b", "null", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("Failed to parse __INITIAL_STATE__ JSON")
        return None


def _build_items(user: dict[str, Any]) -> list[ScrapedItem]:
    """Build ScrapedItem list from user data dict."""
    items: list[ScrapedItem] = []

    if avatar := user.get("imageb") or user.get("images"):
        items.append(ScrapedItem(category="profile", key="avatar", value=avatar))
    if location := user.get("ipLocation"):
        items.append(ScrapedItem(category="profile", key="location", value=location))
    if gender := user.get("gender"):
        label = {"0": "male", "1": "female"}.get(str(gender), str(gender))
        items.append(ScrapedItem(category="profile", key="gender", value=label))

    if (fans := user.get("fans")) is not None:
        items.append(ScrapedItem(category="stats", key="followers", value=fans))
    if (follows := user.get("follows")) is not None:
        items.append(ScrapedItem(category="stats", key="following", value=follows))
    if (collected := user.get("collected")) is not None:
        items.append(ScrapedItem(category="stats", key="likes_collected", value=collected))
    if (liked := user.get("liked")) is not None:
        items.append(ScrapedItem(category="stats", key="likes", value=liked))

    # Tags / interests
    for tag in user.get("tags") or []:
        if isinstance(tag, dict):
            tag_name = tag.get("name") or tag.get("tagType")
        else:
            tag_name = str(tag)
        if tag_name:
            items.append(ScrapedItem(category="interests", key="tag", value=tag_name))

    return items


def _extract_notes(
    state: dict[str, Any], max_items: int,
) -> list[ScrapedItem]:
    """Extract recent notes from the initial state."""
    items: list[ScrapedItem] = []
    notes_data = state.get("user", {}).get("notes", [])
    if not notes_data:
        notes_data = state.get("user", {}).get("notesDetail", [])

    for note in notes_data[:max_items]:
        if not isinstance(note, dict):
            continue
        title = note.get("displayTitle") or note.get("title") or ""
        note_id = note.get("noteId") or note.get("id") or ""
        likes = note.get("likes") or note.get("likedCount") or 0
        note_type = note.get("type") or "normal"

        if title:
            url = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else None
            items.append(ScrapedItem(
                category="content",
                key="note",
                value={"title": title, "likes": likes, "type": note_type},
                url=url,
            ))

    return items


class XiaohongshuScraper(BaseScraper):
    """Scraper for Xiaohongshu (小红书) user profiles."""

    url_patterns: list[str] = [
        "*xiaohongshu.com/user/profile/*",
        "*xhslink.com/*",
    ]

    def get_platform_name(self) -> str:
        return "Xiaohongshu"

    async def scrape(
        self, url: str, config: ScraperConfig,
    ) -> ScrapedData:
        user_id = _extract_user_id(url)
        if not user_id:
            return ScrapedData(
                platform=self.get_platform_name(),
                source_url=url,
                raw={"error": "Could not extract user ID from URL"},
            )

        profile_url = f"https://www.xiaohongshu.com/user/profile/{user_id}"
        raw: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=config.timeout, follow_redirects=True,
        ) as client:
            try:
                resp = await client.get(profile_url, headers=_XHS_HEADERS)
                resp.raise_for_status()
                html = resp.text
            except Exception as exc:
                logger.debug("Failed to fetch Xiaohongshu profile: %s", exc)
                return ScrapedData(
                    platform=self.get_platform_name(),
                    source_url=url,
                    raw={"error": str(exc)},
                )

        state = _parse_initial_state(html)
        if not state:
            return ScrapedData(
                platform=self.get_platform_name(),
                source_url=url,
                raw={"error": "Could not parse page data. Xiaohongshu may require login."},
            )

        user = state.get("user", {}).get("userPageData", {})
        if not user:
            user = state.get("user", {})

        username = user.get("nickname") or user.get("name")
        bio = user.get("desc") or user.get("description") or None
        raw["user"] = {
            k: v for k, v in user.items()
            if isinstance(v, (str, int, float, bool, list)) and k not in ("imageb",)
        }

        items = _build_items(user)
        items.extend(_extract_notes(state, config.max_items))

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=bio,
            items=items,
            raw=raw,
            source_url=url,
        )
