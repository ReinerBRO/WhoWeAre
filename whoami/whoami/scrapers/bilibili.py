"""Bilibili scraper implementation."""

from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.parse
from typing import Any

import httpx

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_BILIBILI_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
}

# Lookup table for WBI mixin key derivation.
_MIXIN_KEY_ENC_TAB: list[int] = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def _extract_mid(url: str) -> str | None:
    """Extract user mid (UID) from a Bilibili URL."""
    m = re.search(r"space\.bilibili\.com/(\d+)", url)
    if m:
        return m.group(1)
    return None


def _get_mixin_key(orig: str) -> str:
    """Derive the mixin key used for WBI signing."""
    return "".join(orig[i] for i in _MIXIN_KEY_ENC_TAB)[:32]


def _sign_wbi(params: dict[str, Any], img_key: str, sub_key: str) -> dict[str, str]:
    """Sign request parameters using Bilibili WBI algorithm."""
    mixin_key = _get_mixin_key(img_key + sub_key)
    params["wts"] = round(time.time())
    params = dict(sorted(params.items()))
    # Strip characters that Bilibili filters out.
    params = {
        k: re.sub(r"[!'()*]", "", str(v)) for k, v in params.items()
    }
    query = urllib.parse.urlencode(params)
    wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = wbi_sign
    return params


def _parse_card(data: dict[str, Any]) -> tuple[
    str | None, str | None, list[ScrapedItem], dict[str, Any],
]:
    """Parse /x/web-interface/card response."""
    card = data.get("data", {}).get("card", {})
    extra = data.get("data", {})
    username = card.get("name")
    bio = card.get("sign") or None
    items: list[ScrapedItem] = []

    level_info = card.get("level_info", {})
    if level := level_info.get("current_level"):
        items.append(ScrapedItem(category="profile", key="level", value=level))
    if face := card.get("face"):
        items.append(ScrapedItem(category="profile", key="avatar", value=face))
    if sex := card.get("sex"):
        items.append(ScrapedItem(category="profile", key="sex", value=sex))
    if (archive_count := extra.get("archive_count")) is not None:
        items.append(ScrapedItem(
            category="stats", key="archive_count", value=archive_count,
        ))
    if (like_num := extra.get("like_num")) is not None:
        items.append(ScrapedItem(
            category="stats", key="total_likes", value=like_num,
        ))

    return username, bio, items, card


def _parse_videos(data: dict[str, Any], max_items: int) -> list[ScrapedItem]:
    """Parse video search API response into ScrapedItem list."""
    items: list[ScrapedItem] = []
    vlist = data.get("data", {}).get("list", {}).get("vlist", [])
    for v in vlist[:max_items]:
        title = v.get("title", "")
        bvid = v.get("bvid", "")
        play = v.get("play", 0)
        video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else None
        items.append(ScrapedItem(
            category="video",
            key=title,
            value={"views": play, "bvid": bvid},
            url=video_url,
        ))
    return items


class BilibiliScraper(BaseScraper):
    """Scraper for Bilibili user spaces and videos."""

    url_patterns: list[str] = [
        "*space.bilibili.com/*",
        "*bilibili.com/video/*",
    ]

    def get_platform_name(self) -> str:
        return "Bilibili"

    async def _get_wbi_keys(
        self, client: httpx.AsyncClient,
    ) -> tuple[str, str]:
        """Fetch WBI img_key and sub_key from the nav endpoint."""
        resp = await client.get(
            "https://api.bilibili.com/x/web-interface/nav",
            headers=_BILIBILI_HEADERS,
        )
        nav = resp.json()
        wbi_img = nav.get("data", {}).get("wbi_img", {})
        img_url = wbi_img.get("img_url", "")
        sub_url = wbi_img.get("sub_url", "")
        img_key = img_url.rsplit("/", 1)[-1].split(".")[0] if img_url else ""
        sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0] if sub_url else ""
        return img_key, sub_key

    async def _init_session(
        self, client: httpx.AsyncClient,
    ) -> None:
        """Warm up the session with cookies (buvid3/buvid4)."""
        await client.get(
            "https://www.bilibili.com/",
            headers={"User-Agent": _BILIBILI_HEADERS["User-Agent"]},
        )
        try:
            spi = await client.get(
                "https://api.bilibili.com/x/frontend/finger/spi",
                headers=_BILIBILI_HEADERS,
            )
            spi_data = spi.json().get("data", {})
            client.cookies.set("buvid3", spi_data.get("b_3", ""))
            client.cookies.set("buvid4", spi_data.get("b_4", ""))
        except Exception:  # noqa: BLE001
            pass

    async def scrape(
        self, url: str, config: ScraperConfig,
    ) -> ScrapedData:
        mid = _extract_mid(url)
        if not mid:
            return ScrapedData(
                platform=self.get_platform_name(),
                source_url=url,
                raw={"error": "Could not extract user mid from URL"},
            )

        items: list[ScrapedItem] = []
        username: str | None = None
        bio: str | None = None
        raw: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=config.timeout, follow_redirects=True,
        ) as client:
            # Warm up session for cookies.
            await self._init_session(client)

            # --- user info via card API ---
            try:
                resp = await client.get(
                    "https://api.bilibili.com/x/web-interface/card",
                    headers=_BILIBILI_HEADERS,
                    params={"mid": mid, "photo": "true"},
                )
                card_data = resp.json()
                if card_data.get("code") == 0:
                    username, bio, profile_items, card_raw = _parse_card(
                        card_data,
                    )
                    items.extend(profile_items)
                    raw["card"] = card_raw
            except Exception as exc:  # noqa: BLE001
                logger.debug("Card API failed: %s", exc)

            # --- follower / following stats ---
            try:
                resp = await client.get(
                    "https://api.bilibili.com/x/relation/stat",
                    headers=_BILIBILI_HEADERS,
                    params={"vmid": mid},
                )
                stat_data = resp.json()
                if stat_data.get("code") == 0:
                    sd = stat_data.get("data", {})
                    items.append(ScrapedItem(
                        category="stats",
                        key="followers",
                        value=sd.get("follower", 0),
                    ))
                    items.append(ScrapedItem(
                        category="stats",
                        key="following",
                        value=sd.get("following", 0),
                    ))
                    raw["stat"] = sd
            except Exception as exc:  # noqa: BLE001
                logger.debug("Stat API failed: %s", exc)

            # --- videos via WBI-signed endpoint (with fallback) ---
            video_fetched = False
            try:
                img_key, sub_key = await self._get_wbi_keys(client)
                if img_key and sub_key:
                    signed = _sign_wbi(
                        {"mid": mid, "ps": 20, "pn": 1},
                        img_key,
                        sub_key,
                    )
                    resp = await client.get(
                        "https://api.bilibili.com/x/space/wbi/arc/search",
                        headers=_BILIBILI_HEADERS,
                        params=signed,
                    )
                    video_data = resp.json()
                    if video_data.get("code") == 0:
                        items.extend(
                            _parse_videos(video_data, config.max_items),
                        )
                        raw["videos"] = video_data.get("data", {})
                        video_fetched = True
            except Exception as exc:  # noqa: BLE001
                logger.debug("WBI video search failed: %s", exc)

            # Fallback: try non-wbi arc/search endpoint.
            if not video_fetched:
                try:
                    resp = await client.get(
                        "https://api.bilibili.com/x/space/arc/search",
                        headers=_BILIBILI_HEADERS,
                        params={"mid": mid, "ps": "20", "pn": "1"},
                    )
                    video_data = resp.json()
                    if video_data.get("code") == 0:
                        items.extend(
                            _parse_videos(video_data, config.max_items),
                        )
                        raw["videos"] = video_data.get("data", {})
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Fallback video search failed: %s", exc)

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=bio,
            items=items,
            raw=raw,
            source_url=url,
        )
