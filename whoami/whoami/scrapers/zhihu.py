"""Zhihu scraper implementation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from whoami.models import ScrapedData, ScrapedItem, ScraperConfig
from whoami.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_ZHIHU_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.zhihu.com/",
    "Accept": "application/json, text/plain, */*",
}


def _extract_url_token(url: str) -> str | None:
    """Extract user URL token from a Zhihu URL."""
    m = re.search(r"zhihu\.com/people/([^/?#]+)", url)
    if m:
        return m.group(1)
    return None


def _parse_api_response(data: dict[str, Any]) -> tuple[
    str | None, str | None, list[ScrapedItem],
]:
    """Parse Zhihu API response into username, bio, and items."""
    username = data.get("name")
    bio = data.get("headline") or None
    items: list[ScrapedItem] = []

    if avatar_url := data.get("avatar_url"):
        items.append(ScrapedItem(
            category="profile",
            key="avatar",
            value=avatar_url,
        ))

    if gender := data.get("gender"):
        gender_map = {-1: "unknown", 0: "female", 1: "male"}
        items.append(ScrapedItem(
            category="profile",
            key="gender",
            value=gender_map.get(gender, "unknown"),
        ))

    if follower_count := data.get("follower_count"):
        items.append(ScrapedItem(
            category="stats",
            key="followers",
            value=follower_count,
        ))

    if following_count := data.get("following_count"):
        items.append(ScrapedItem(
            category="stats",
            key="following",
            value=following_count,
        ))

    if answer_count := data.get("answer_count"):
        items.append(ScrapedItem(
            category="stats",
            key="answers",
            value=answer_count,
        ))

    if articles_count := data.get("articles_count"):
        items.append(ScrapedItem(
            category="stats",
            key="articles",
            value=articles_count,
        ))

    if question_count := data.get("question_count"):
        items.append(ScrapedItem(
            category="stats",
            key="questions",
            value=question_count,
        ))

    if voteup_count := data.get("voteup_count"):
        items.append(ScrapedItem(
            category="stats",
            key="total_upvotes",
            value=voteup_count,
        ))

    return username, bio, items


def _parse_html_embedded_data(html: str) -> dict[str, Any] | None:
    """Extract embedded JSON data from Zhihu profile page HTML."""
    match = re.search(
        r'<script id="js-initialData" type="text/json">(.+?)</script>',
        html,
        re.DOTALL,
    )
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


class ZhihuScraper(BaseScraper):
    """Scraper for Zhihu user profiles."""

    url_patterns: list[str] = ["*zhihu.com/*"]

    def get_platform_name(self) -> str:
        return "Zhihu"

    async def scrape(
        self, url: str, config: ScraperConfig,
    ) -> ScrapedData:
        url_token = _extract_url_token(url)
        if not url_token:
            return ScrapedData(
                platform=self.get_platform_name(),
                source_url=url,
                raw={"error": "Could not extract user URL token from URL"},
            )

        items: list[ScrapedItem] = []
        username: str | None = None
        bio: str | None = None
        raw: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=config.timeout, follow_redirects=True,
        ) as client:
            # Try API first
            api_success = False
            try:
                include_params = (
                    "locations,employments,gender,educations,business,"
                    "voteup_count,thanked_Count,follower_count,following_count,"
                    "cover_url,following_topic_count,following_question_count,"
                    "following_favlists_count,following_columns_count,"
                    "answer_count,articles_count,pins_count,question_count,"
                    "columns_count,commercial_question_count,favorite_count,"
                    "favorited_count,logs_count,marked_answers_count,"
                    "marked_answers_text,message_thread_token,account_status,"
                    "is_active,is_force_renamed,is_bind_sina,sina_weibo_url,"
                    "sina_weibo_name,show_sina_weibo,is_blocking,is_blocked,"
                    "is_following,is_followed,mutual_followees_count,"
                    "vote_to_count,vote_from_count,thank_to_count,"
                    "thank_from_count,thanked_count,description,hosted_live_count,"
                    "participated_live_count,allow_message,industry_category,"
                    "org_name,org_homepage,badge[?(type=best_answerer)].topics"
                )
                api_url = f"https://www.zhihu.com/api/v4/members/{url_token}"
                resp = await client.get(
                    api_url,
                    headers=_ZHIHU_HEADERS,
                    params={"include": include_params},
                )
                resp.raise_for_status()
                api_data = resp.json()

                if "error" not in api_data:
                    username, bio, api_items = _parse_api_response(api_data)
                    items.extend(api_items)
                    raw["api"] = api_data
                    api_success = True

                    # Extract topics if available
                    if badge_list := api_data.get("badge"):
                        for badge in badge_list[:config.max_items]:
                            if badge.get("type") == "best_answerer":
                                for topic in badge.get("topics", []):
                                    topic_name = topic.get("name")
                                    topic_url = topic.get("url")
                                    if topic_name:
                                        items.append(ScrapedItem(
                                            category="topic",
                                            key=topic_name,
                                            value=topic.get("id"),
                                            url=topic_url,
                                        ))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Zhihu API failed: %s", exc)

            # Fallback: try HTML scraping
            if not api_success:
                try:
                    profile_url = f"https://www.zhihu.com/people/{url_token}"
                    resp = await client.get(
                        profile_url,
                        headers={
                            "User-Agent": _ZHIHU_HEADERS["User-Agent"],
                            "Accept": "text/html",
                        },
                    )
                    resp.raise_for_status()
                    html = resp.text

                    embedded_data = _parse_html_embedded_data(html)
                    if embedded_data:
                        raw["html_embedded"] = embedded_data
                        # Try to extract user data from embedded JSON
                        entities = embedded_data.get("initialState", {}).get("entities", {})
                        users = entities.get("users", {})
                        if url_token in users:
                            user_data = users[url_token]
                            username, bio, html_items = _parse_api_response(user_data)
                            items.extend(html_items)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Zhihu HTML scraping failed: %s", exc)

        # If we still don't have a username, use the URL token
        if not username:
            username = url_token

        return ScrapedData(
            platform=self.get_platform_name(),
            username=username,
            bio=bio,
            items=items,
            raw=raw,
            source_url=url,
        )

