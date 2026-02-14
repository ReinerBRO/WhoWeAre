"""Collector that structures a character reference for downstream synthesis."""

from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

import litellm
from llmkit import LLMConfig
from whoareu.collectors.base import BaseCollector
from whoareu.models import AgentSpec

_HTTP_TIMEOUT_SEC = 8
_MAX_ITEM_CHARS = 900
_MAX_CONTEXT_CHARS = 1800
_WIKI_USER_AGENT = "whoareu/0.1 (+https://github.com/ReinerBRO/WhoWeAre)"
_MAX_ALIAS_CANDIDATES = 5
_ALIAS_RESOLVE_TIMEOUT_SEC = 20


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _normalize_whitespace(value).strip(" \"'")
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def _clip_text(text: str, max_chars: int) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars].rstrip()}..."


def _looks_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))


def _is_http_url(text: str) -> bool:
    try:
        parsed = urlparse(text.strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _safe_fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": _WIKI_USER_AGENT})
    with urlopen(request, timeout=_HTTP_TIMEOUT_SEC) as response:
        return json.load(response)


def _parse_alias_candidates(raw: str, original: str) -> list[str]:
    text = raw.strip()
    if not text:
        return [original]

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()

    candidates: list[str] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            candidates.extend(str(item) for item in parsed if isinstance(item, str))
        elif isinstance(parsed, dict):
            for key in ("candidates", "aliases", "names"):
                values = parsed.get(key)
                if isinstance(values, list):
                    candidates.extend(str(item) for item in values if isinstance(item, str))
                    break
    except json.JSONDecodeError:
        pass

    if not candidates:
        for line in text.splitlines():
            cleaned = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip().strip("\"'")
            if cleaned:
                candidates.append(cleaned)

    combined = _dedupe_strings([original, *candidates])
    return combined[:_MAX_ALIAS_CANDIDATES]


def _expand_reference_queries_with_llm(
    character: str,
    language: str,
    llm: LLMConfig,
) -> list[str]:
    """Ask the configured LLM for multilingual alias candidates for encyclopedia lookup."""
    kwargs = llm.to_litellm_kwargs()
    kwargs.update({
        "messages": [
            {
                "role": "system",
                "content": (
                    "You normalize character/entity names for encyclopedia lookup.\n"
                    "Return JSON only.\n"
                    "Output format: {\"candidates\": [\"name1\", \"name2\", ...]}.\n"
                    "Rules:\n"
                    "- Include the original input.\n"
                    "- Include likely aliases across Chinese/English/Japanese if relevant.\n"
                    "- Keep 1-5 short candidates only.\n"
                    "- No explanations."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Input name: {character}\n"
                    f"Preferred language: {language}\n"
                    "Return candidates for searching Wikipedia / Moegirl."
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 160,
        "timeout": _ALIAS_RESOLVE_TIMEOUT_SEC,
        "num_retries": 1,
    })

    try:
        response = litellm.completion(**kwargs)
    except Exception:
        return [character]

    if not response.choices:
        return [character]

    content = response.choices[0].message.content
    if not isinstance(content, str):
        return [character]
    return _parse_alias_candidates(content, character)


def _extract_wiki_title_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path or ""
    marker = "/wiki/"
    if marker not in path:
        return None
    title = path.split(marker, 1)[1].strip("/")
    if not title:
        return None
    return unquote(title)


def _extract_moegirl_title_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    title = (parsed.path or "").strip("/")
    if not title:
        return None
    return unquote(title)


def _fetch_wikipedia_summary_by_title(title: str, lang: str) -> str | None:
    summary_url = (
        f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
        f"{quote(title, safe='')}"
    )
    payload = _safe_fetch_json(summary_url)
    extract = payload.get("extract")
    if isinstance(extract, str) and extract.strip():
        return _clip_text(extract, _MAX_ITEM_CHARS)
    return None


def _search_wikipedia_title(query: str, lang: str) -> str | None:
    search_url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={quote(query)}&srlimit=1&format=json"
    )
    payload = _safe_fetch_json(search_url)
    query_obj = payload.get("query")
    if not isinstance(query_obj, dict):
        return None
    results = query_obj.get("search")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    title = first.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def _fetch_moegirl_summary_by_title(title: str) -> str | None:
    api_url = (
        "https://zh.moegirl.org.cn/api.php"
        f"?action=query&prop=extracts&explaintext=1&exintro=1&redirects=1&titles={quote(title)}"
        "&format=json&formatversion=2"
    )
    payload = _safe_fetch_json(api_url)
    query_obj = payload.get("query")
    if not isinstance(query_obj, dict):
        return None
    pages = query_obj.get("pages")
    if not isinstance(pages, list) or not pages:
        return None
    first = pages[0]
    if not isinstance(first, dict):
        return None
    extract = first.get("extract")
    if isinstance(extract, str) and extract.strip():
        return _clip_text(extract, _MAX_ITEM_CHARS)
    return None


def _search_moegirl_title(query: str) -> str | None:
    search_url = (
        "https://zh.moegirl.org.cn/api.php"
        f"?action=query&list=search&srsearch={quote(query)}&srlimit=1&format=json&formatversion=2"
    )
    payload = _safe_fetch_json(search_url)
    query_obj = payload.get("query")
    if not isinstance(query_obj, dict):
        return None
    results = query_obj.get("search")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    title = first.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def _preferred_wiki_lang_order(language: str, query_candidates: list[str]) -> list[str]:
    joined = " ".join(query_candidates)
    if language.startswith("zh") or _looks_cjk(joined):
        return ["zh", "en"]
    return ["en", "zh"]


def _fetch_reference_context(
    character: str,
    language: str,
    *,
    query_candidates: list[str] | None = None,
) -> str:
    """Best-effort context fetch from Wikipedia/Moegirl for richer reference mode."""
    entries: list[str] = []
    trimmed = character.strip()
    if not trimmed:
        return ""

    candidates = _dedupe_strings([trimmed, *(query_candidates or [])])

    def safe_call(fn, *args):
        try:
            return fn(*args)
        except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError):
            return None

    got_wikipedia = False
    got_moegirl = False

    if _is_http_url(trimmed):
        parsed = urlparse(trimmed)
        host = parsed.netloc.lower()
        if "wikipedia.org" in host:
            title = _extract_wiki_title_from_url(trimmed)
            lang = host.split(".wikipedia.org")[0] or ("zh" if _looks_cjk(trimmed) else "en")
            if title:
                summary = safe_call(_fetch_wikipedia_summary_by_title, title, lang)
                if summary:
                    entries.append(f"[Wikipedia/{lang}] {summary}")
                    got_wikipedia = True
                candidates = _dedupe_strings([title.replace("_", " "), title, *candidates])
        elif "moegirl.org.cn" in host:
            title = _extract_moegirl_title_from_url(trimmed)
            if title:
                summary = safe_call(_fetch_moegirl_summary_by_title, title)
                if summary:
                    entries.append(f"[Moegirl] {summary}")
                    got_moegirl = True
                candidates = _dedupe_strings([title.replace("_", " "), title, *candidates])

    if not got_wikipedia:
        wiki_lang_order = _preferred_wiki_lang_order(language, candidates)
        for query in candidates:
            for lang in wiki_lang_order:
                title = safe_call(_search_wikipedia_title, query, lang)
                if not title:
                    continue
                summary = safe_call(_fetch_wikipedia_summary_by_title, title, lang)
                if summary:
                    entries.append(f"[Wikipedia/{lang}] {summary}")
                    got_wikipedia = True
                    break
            if got_wikipedia:
                break

    if not got_moegirl:
        for query in candidates:
            title = safe_call(_search_moegirl_title, query)
            if not title:
                continue
            summary = safe_call(_fetch_moegirl_summary_by_title, title)
            if summary:
                entries.append(f"[Moegirl] {summary}")
                got_moegirl = True
                break

    if not entries:
        return ""
    return _clip_text("\n".join(entries), _MAX_CONTEXT_CHARS)


class ReferenceCollector(BaseCollector):
    """Captures a reference character and enriches it with public encyclopedia context."""

    def collect(
        self,
        *,
        character: str,
        agent_name: str | None = None,
        language: str = "zh",
        llm: LLMConfig | None = None,
        resolve_alias: bool = True,
        **kwargs: object,
    ) -> AgentSpec:
        """Return an AgentSpec seeded from a character reference."""
        query_candidates = [character]
        if resolve_alias and llm is not None and not _is_http_url(character):
            query_candidates = _expand_reference_queries_with_llm(character, language, llm)

        reference_context = _fetch_reference_context(
            character,
            language,
            query_candidates=query_candidates,
        )
        personality = (
            f"Based on the reference character '{character}', "
            "extract and adopt their core personality traits, "
            "speech patterns, and behavioral tendencies."
        )
        alias_hint = ""
        if len(query_candidates) > 1:
            alias_hint = f"Reference name candidates: {', '.join(query_candidates)}"

        extra_instructions = None
        if reference_context:
            personality += " Ground your output in the provided reference context when available."
            context_block = (
                "Reference encyclopedia context (for trait grounding, avoid verbatim copying):\n"
                f"{reference_context}"
            )
            extra_instructions = (
                f"{alias_hint}\n\n{context_block}" if alias_hint else context_block
            )
        elif alias_hint:
            extra_instructions = alias_hint

        return AgentSpec(
            name=agent_name,
            reference_character=character,
            personality=personality,
            extra_instructions=extra_instructions,
        )
