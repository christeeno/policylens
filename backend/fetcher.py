import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import aiohttp
import feedparser
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

OFFICIAL_REFRESH_SECONDS = 15 * 60
NEWS_REFRESH_SECONDS = 30 * 60
FEED_LIMIT = 15
REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class FeedAdapter:
    key: str
    source: str
    source_type: str
    publisher: str
    url: str
    refresh_seconds: int


ADAPTERS = [
    FeedAdapter(
        key="rbi_press_releases",
        source="RBI",
        source_type="OFFICIAL",
        publisher="Reserve Bank of India",
        url="https://www.rbi.org.in/pressreleases_rss.xml",
        refresh_seconds=OFFICIAL_REFRESH_SECONDS,
    ),
    FeedAdapter(
        key="rbi_notifications",
        source="RBI",
        source_type="OFFICIAL",
        publisher="Reserve Bank of India",
        url="https://www.rbi.org.in/notifications_rss.xml",
        refresh_seconds=OFFICIAL_REFRESH_SECONDS,
    ),
    FeedAdapter(
        key="pib_releases",
        source="PIB",
        source_type="OFFICIAL",
        publisher="Press Information Bureau",
        url="https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
        refresh_seconds=OFFICIAL_REFRESH_SECONDS,
    ),
    FeedAdapter(
        key="sebi_updates",
        source="SEBI",
        source_type="OFFICIAL",
        publisher="Securities and Exchange Board of India",
        url="https://www.sebi.gov.in/sebirss.xml",
        refresh_seconds=OFFICIAL_REFRESH_SECONDS,
    ),
    FeedAdapter(
        key="google_rbi",
        source="RBI",
        source_type="NEWS",
        publisher="Google News",
        url="https://news.google.com/rss/search?q=RBI+policy&hl=en-IN&gl=IN&ceid=IN:en",
        refresh_seconds=NEWS_REFRESH_SECONDS,
    ),
    FeedAdapter(
        key="google_sebi",
        source="SEBI",
        source_type="NEWS",
        publisher="Google News",
        url="https://news.google.com/rss/search?q=SEBI+circular+OR+policy&hl=en-IN&gl=IN&ceid=IN:en",
        refresh_seconds=NEWS_REFRESH_SECONDS,
    ),
    FeedAdapter(
        key="google_govt",
        source="Govt",
        source_type="NEWS",
        publisher="Google News",
        url="https://news.google.com/rss/search?q=India+finance+ministry+policy&hl=en-IN&gl=IN&ceid=IN:en",
        refresh_seconds=NEWS_REFRESH_SECONDS,
    ),
]

_ADAPTER_CACHE: dict[str, dict] = {}


def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()[:2000]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _derive_news_publisher(entry: dict, title: str, default: str) -> str:
    if getattr(entry, "source", None):
        source_title = clean_html(getattr(entry.source, "title", ""))
        if source_title:
            return source_title

    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return default


def _strip_publisher_suffix(title: str, publisher: str, source_type: str) -> str:
    cleaned = _normalize_whitespace(title)
    if source_type == "NEWS" and publisher and cleaned.endswith(publisher):
        cleaned = cleaned[: -len(publisher)].rstrip(" -|:")
    return cleaned


def _parse_date(date_string: str) -> datetime:
    raw = (date_string or "").strip()
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _normalize_date(date_string: str) -> str:
    parsed = _parse_date(date_string)
    if parsed == datetime.min.replace(tzinfo=timezone.utc):
        return ""
    return parsed.isoformat()


def _classification_payload(article_class: str, confidence: float, reasoning: str) -> dict:
    return {
        "article_class": article_class,
        "classification_confidence": round(confidence, 2),
        "classification_reasoning": reasoning,
        "is_actionable": article_class in {"OFFICIAL_POLICY", "NEWS_REPORT"},
    }


def infer_article_class(
    text: str,
    source_type: str,
    publisher: str,
) -> dict:
    normalized = _normalize_whitespace(text).lower()
    if not normalized:
        return _classification_payload("OTHER", 0.0, "No text was available to classify.")

    preview_markers = (
        "to announce",
        "will announce",
        "scheduled to announce",
        "scheduled to meet",
        "ahead of policy",
        "await",
        "expected to",
        "today's policy",
        "policy today",
        "preview",
    )
    commentary_markers = (
        "why ",
        "what should",
        "what investors",
        "strategy",
        "outlook",
        "signals",
        "may help",
        "opinion",
        "analysis",
        "explainer",
        "should you",
    )
    market_reaction_markers = (
        "shares",
        "stocks",
        "sensex",
        "nifty",
        "markets",
        "market reaction",
        "rally",
        "surge",
        "falls",
        "tumbles",
        "gains",
        "investors cheer",
    )
    action_markers = (
        "approves",
        "approved",
        "announces",
        "announced",
        "raises",
        "raised",
        "cuts",
        "cut ",
        "hikes",
        "hiked",
        "revises",
        "revised",
        "introduces",
        "introduced",
        "issues",
        "issued",
        "notifies",
        "notified",
        "launches",
        "launched",
        "increased",
        "decreased",
    )
    personnel_action_markers = (
        "appoints",
        "appointed",
        "appointment",
        "reappoints",
        "re-appointed",
        "reappointment",
        "re-appointment",
        "reappointed",
        "tenure extended",
        "extension of tenure",
        "resigns",
        "resigned",
        "resignation",
        "retires",
        "retired",
        "retirement",
    )
    personnel_role_markers = (
        "deputy governor",
        "governor",
        "chairperson",
        "chairman",
        "whole-time member",
        "whole time member",
        "executive director",
        "managing director",
        "chief executive officer",
        "director",
    )

    if (
        any(marker in normalized for marker in personnel_action_markers)
        and any(marker in normalized for marker in personnel_role_markers)
    ):
        return _classification_payload("OTHER", 0.95, "The text is an official personnel update, not a market-impact policy measure.")
    if any(marker in normalized for marker in preview_markers):
        return _classification_payload("PREVIEW", 0.93, "The text describes an upcoming policy announcement rather than a completed decision.")
    if any(marker in normalized for marker in commentary_markers):
        return _classification_payload("COMMENTARY", 0.88, "The text reads like commentary or investor analysis rather than a primary policy event.")
    if any(marker in normalized for marker in market_reaction_markers):
        return _classification_payload("MARKET_REACTION", 0.84, "The text focuses on price action or investor response after policy news.")
    if source_type == "OFFICIAL" and any(marker in normalized for marker in action_markers):
        return _classification_payload("OFFICIAL_POLICY", 0.97, f"The text comes from {publisher} and describes a concrete policy action.")
    if source_type == "NEWS" and any(marker in normalized for marker in action_markers):
        return _classification_payload("NEWS_REPORT", 0.9, "The text appears to be a factual news report about a completed policy action.")
    if source_type == "OFFICIAL":
        return _classification_payload("OFFICIAL_POLICY", 0.72, f"The text comes from {publisher}, so it is treated as an official policy update by default.")
    return _classification_payload("OTHER", 0.45, "The text is too vague to classify as a concrete policy event.")


def _build_item_id(link: str, title: str) -> str:
    return hashlib.md5(f"{link}|{title}".encode("utf-8")).hexdigest()


def _normalize_item(adapter: FeedAdapter, entry: dict) -> dict | None:
    link = _normalize_whitespace(entry.get("link", ""))
    title = clean_html(entry.get("title", ""))
    summary = clean_html(entry.get("summary", "") or entry.get("description", ""))
    date_str = entry.get("published", "") or entry.get("updated", "") or entry.get("pubDate", "")

    if not link or not title:
        return None

    publisher = adapter.publisher if adapter.source_type == "OFFICIAL" else _derive_news_publisher(entry, title, adapter.publisher)
    display_title = _strip_publisher_suffix(title, publisher, adapter.source_type)
    raw_text_preview = summary or display_title
    classification = infer_article_class(
        text=f"{display_title}. {summary}".strip(),
        source_type=adapter.source_type,
        publisher=publisher,
    )

    return {
        "id": _build_item_id(link, display_title),
        "title": display_title,
        "summary": summary,
        "date": _normalize_date(date_str),
        "link": link,
        "source": adapter.source,
        "source_type": adapter.source_type,
        "publisher": publisher,
        "article_class": classification["article_class"],
        "classification_confidence": classification["classification_confidence"],
        "classification_reasoning": classification["classification_reasoning"],
        "raw_text_preview": raw_text_preview,
        "full_text": "",
        "is_actionable": classification["is_actionable"],
    }


async def _fetch_adapter(session: aiohttp.ClientSession, adapter: FeedAdapter) -> list[dict]:
    cache_entry = _ADAPTER_CACHE.get(adapter.key)
    now = datetime.now(timezone.utc)
    if cache_entry:
        age = now - cache_entry["fetched_at"]
        if age <= timedelta(seconds=adapter.refresh_seconds):
            return cache_entry["items"]

    items: list[dict] = []
    error_message = ""
    try:
        async with session.get(adapter.url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            content = await response.text()
            feed = feedparser.parse(content)
            for entry in feed.entries:
                normalized = _normalize_item(adapter, entry)
                if normalized:
                    items.append(normalized)
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)
        logger.warning("Feed adapter %s failed: %s", adapter.key, exc)
        items = cache_entry["items"] if cache_entry else []

    _ADAPTER_CACHE[adapter.key] = {
        "items": items,
        "fetched_at": now,
        "error": error_message,
        "source_type": adapter.source_type,
    }
    return items


async def fetch_all_feeds() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[_fetch_adapter(session, adapter) for adapter in ADAPTERS],
            return_exceptions=True,
        )

    all_items: list[dict] = []
    for result in results:
        if isinstance(result, list):
            all_items.extend(result)
    return all_items


def get_fallback_feed() -> list[dict]:
    fallback_path = os.path.join(os.path.dirname(__file__), "fallback_data", "sample_feed.json")
    try:
        with open(fallback_path, "r", encoding="utf-8") as handle:
            items = json.load(handle)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load fallback feed: %s", exc)
        return []

    normalized = []
    for item in items:
        source_type = item.get("source_type", "OFFICIAL")
        publisher = item.get("publisher", item.get("source", "Official Source"))
        classification = infer_article_class(
            text=f"{item.get('title', '')}. {item.get('summary', '')}".strip(),
            source_type=source_type,
            publisher=publisher,
        )
        normalized.append(
            {
                "id": item.get("id") or _build_item_id(item.get("link", ""), item.get("title", "")),
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "date": item.get("date", ""),
                "link": item.get("link", ""),
                "source": item.get("source", "Official"),
                "source_type": source_type,
                "publisher": publisher,
                "article_class": item.get("article_class", classification["article_class"]),
                "classification_confidence": item.get("classification_confidence", classification["classification_confidence"]),
                "classification_reasoning": item.get("classification_reasoning", classification["classification_reasoning"]),
                "raw_text_preview": item.get("raw_text_preview", item.get("summary") or item.get("title", "")),
                "full_text": item.get("full_text", ""),
                "is_actionable": item.get("is_actionable", classification["is_actionable"]),
            }
        )
    return normalized


def _dedupe_items(items: list[dict]) -> list[dict]:
    best_by_key: dict[str, dict] = {}
    for item in items:
        title_key = re.sub(r"[^a-z0-9]+", " ", item.get("title", "").lower()).strip()
        parsed = urlparse(item.get("link", ""))
        url_key = f"{parsed.netloc}{parsed.path}".lower().strip("/")
        dedupe_key = title_key or url_key or item.get("id", "")

        existing = best_by_key.get(dedupe_key)
        if existing is None:
            best_by_key[dedupe_key] = item
            continue

        current_rank = _sort_key(item)
        existing_rank = _sort_key(existing)
        if current_rank > existing_rank:
            best_by_key[dedupe_key] = item
    return list(best_by_key.values())


def _sort_key(item: dict) -> tuple[int, float]:
    source_priority = 2 if item.get("source_type") == "OFFICIAL" else 1
    parsed = _parse_date(item.get("date", ""))
    timestamp = 0.0 if parsed.year <= 1 else parsed.timestamp()
    return source_priority, timestamp


def _log_feed_stats(items: list[dict]) -> None:
    per_source_type = {"OFFICIAL": 0, "NEWS": 0, "COMMENTARY": 0}
    per_class: dict[str, int] = {}
    actionable = 0
    for item in items:
        per_source_type[item.get("source_type", "NEWS")] = per_source_type.get(item.get("source_type", "NEWS"), 0) + 1
        article_class = item.get("article_class", "OTHER")
        per_class[article_class] = per_class.get(article_class, 0) + 1
        actionable += int(bool(item.get("is_actionable")))

    logger.info(
        "Feed stats official=%s news=%s commentary=%s actionable=%s class_distribution=%s",
        per_source_type.get("OFFICIAL", 0),
        per_source_type.get("NEWS", 0),
        per_source_type.get("COMMENTARY", 0),
        actionable,
        per_class,
    )


def fetch_policies() -> list[dict]:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    items = loop.run_until_complete(fetch_all_feeds())
    if not items:
        items = get_fallback_feed()

    unique_items = _dedupe_items(items)
    unique_items.sort(key=_sort_key, reverse=True)
    result = unique_items[:FEED_LIMIT]
    _log_feed_stats(result)
    return result


if __name__ == "__main__":
    policies = fetch_policies()
    print(f"Fetched {len(policies)} policies.")
    for policy in policies[:5]:
        print(policy)
