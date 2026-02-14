"""Weibo scraper implementation."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_WEIBO_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Mobile/15E148"
    ),
    "Referer": "https://m.weibo.cn/",
    "Accept": "application/json, text/plain, */*",
}


def _extract_uid(url: str) -> str | None:
    """Extract user ID from a Weibo URL."""
    # Match patterns like: weibo.com/u/1234567890 or weibo.com/1234567890
    m = re.search(r"weibo\.com/(?:u/)?(\d+)", url)
    if m:
        return m.group(1)
    # Match username patterns like: weibo.com/username
    m = re.search(r"weibo\.com/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def _parse_mobile_api(data: dict[str, Any]) -> tuple[
    str | None, str | None, list[ScrapedItem], dict[str, Any],
]:
    """Parse mobile API response from m.weibo.cn."""
    userInfo = data.get("data", {}).get("userInfo", {})
    username = userInfo.get("screen_name")
    bio = userInfo.get("description") or None
    items: list[ScrapedItem] = []

    if avatar := userInfo.get("profile_image_url"):
        items.append(ScrapedItem(category="profile", key="avatar", value=avatar))
    if verified := userInfo.get("verified"):
        items.append(ScrapedItem(category="profile", key="verified", value=verified))
    if verified_type := userInfo.get("verified_type"):
        items.append(ScrapedItem(category="profile", key="verified_type", value=verified_type))
    if verified_reason := userInfo.get("verified_reason"):
        items.append(ScrapedItem(category="profile", key="verified_reason", value=verified_reason))
    if followers := userInfo.get("followers_count"):
        items.append(ScrapedItem(category="stats", key="followers", value=followers))
    if following := userInfo.get("follow_count"):
        items.append(ScrapedItem(category="stats", key="following", value=following))
    if posts := userInfo.get("statuses_count"):
        items.append(ScrapedItem(category="stats", key="posts", value=posts))

    return username, bio, items, userInfo


def _parse_ajax_api(data: dict[str, Any]) -> tuple[
    str | None, str | None, list[ScrapedItem], dict[str, Any],
]:
    """Parse ajax API response from weibo.com/ajax."""
    user_data = data.get("data", {})
    username = user_data.get("screen_name")
    bio = user_data.get("description") or None
    items: list[ScrapedItem] = []

    if avatar := user_data.get("avatar_hd"):
        items.append(ScrapedItem(category="profile", key="avatar", value=avatar))
    if verified := user_data.get("verified"):
        items.append(ScrapedItem(category="profile", key="verified", value=verified))
    if verified_type := user_data.get("verified_type"):
        items.append(ScrapedItem(category="profile", key="verified_type", value=verified_type))
    if verified_reason := user_data.get("verified_reason"):
        items.append(ScrapedItem(category="profile", key="verified_reason", value=verified_reason))
    if followers := user_data.get("followers_count"):
        items.append(ScrapedItem(category="stats", key="followers", value=followers))
    if following := user_data.get("follow_count"):
        items.append(ScrapedItem(category="stats", key="following", value=following))
    if posts := user_data.get("statuses_count"):
        items.append(ScrapedItem(category="stats", key="posts", value=posts))

    return username, bio, items, user_data


class WeiboScraper(BaseScraper):
    """Scraper for Weibo user profiles."""

    url_patterns: list[str] = ["*weibo.com/*"]

    def get_platform_name(self) -> str:
        return "Weibo"

    async def scrape(
        self, url: str, config: ScraperConfig,
    ) -> ScrapedData:
        uid = _extract_uid(url)
        if not uid:
            return ScrapedData(
                platform=self.get_platform_name(),
                source_url=url,
                raw={"error": "Could not extract user ID from URL"},
            )

        items: list[ScrapedItem] = []
        username: str | None = None
        bio: str | None = None
        raw: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=config.timeout, follow_redirects=True,
        ) as client:
            # Try mobile API with containerid (more reliable)
            try:
                containerid = f"100505{uid}"
                resp = await client.get(
                    "https://m.weibo.cn/api/container/getIndex",
                    headers=_WEIBO_HEADERS,
                    params={"containerid": containerid},
                )
                mobile_data = resp.json()
                if mobile_data.get("ok") == 1:
                    username, bio, profile_items, user_raw = _parse_mobile_api(
                        mobile_data,
                    )
                    items.extend(profile_items)
                    raw["mobile_api"] = user_raw
                    logger.debug("Mobile API succeeded for uid=%s", uid)
            except httpx.HTTPStatusError as exc:
                logger.debug("Mobile API HTTP error: %s", exc)
                raw["mobile_api_error"] = f"HTTP {exc.response.status_code}"
            except Exception as exc:
                logger.debug("Mobile API failed: %s", exc)
                raw["mobile_api_error"] = str(exc)

            # Fallback to ajax API if mobile API failed or returned no data
            if not username:
                try:
                    resp = await client.get(
                        "https://weibo.com/ajax/profile/info",
                        headers={
                            **_WEIBO_HEADERS,
                            "User-Agent": (
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/125.0.0.0 Safari/537.36"
                            ),
                            "Referer": f"https://weibo.com/u/{uid}",
                        },
                        params={"uid": uid},
                    )
                    ajax_data = resp.json()
                    if ajax_data.get("ok") == 1:
                        username, bio, profile_items, user_raw = _parse_ajax_api(
                            ajax_data,
                        )
                        items.extend(profile_items)
                        raw["ajax_api"] = user_raw
                        logger.debug("Ajax API succeeded for uid=%s", uid)
                    else:
                        raw["ajax_api_error"] = f"API returned ok={ajax_data.get('ok')}"
                except Exception as exc:
                    logger.debug("Ajax API failed: %s", exc)
                    raw["ajax_api_error"] = str(exc)

            # If both APIs failed, add a helpful message
            if not username and not items:
                raw["message"] = (
                    "Weibo requires authentication or has blocked this request. "
                    "This is expected behavior due to Weibo's anti-scraping measures."
                )

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=bio,
            items=items,
            raw=raw,
            source_url=url,
        )
