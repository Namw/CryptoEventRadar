from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any
from urllib.error import HTTPError, URLError
from urllib import request
from urllib.parse import urlencode
from xml.etree import ElementTree

from crypto_market_intel.sources.base import RawSourceRecord

BINANCE_ARTICLE_API = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
BINANCE_CATALOG_ARTICLE_API = "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query"
BINANCE_ANNOUNCEMENT_RSS = "https://www.binance.com/en/support/announcement/rss"


def compute_content_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        if value > 10_000_000_000:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _to_absolute_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://www.binance.com{url}"


def _extract_articles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict):
        articles = data.get("articles")
        if isinstance(articles, list):
            return [item for item in articles if isinstance(item, dict)]
    return []


def fetch_binance_announcements(limit: int = 20) -> list[RawSourceRecord]:
    page_size = max(1, min(limit, 50))
    query = urlencode({"catalogId": 48, "pageNo": 1, "pageSize": page_size})
    req = request.Request(
        f"{BINANCE_CATALOG_ARTICLE_API}?{query}",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.binance.com",
            "Referer": "https://www.binance.com/en/support/announcement",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        },
        method="GET",
    )

    try:
        with _open_url(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        records = _records_from_api_payload(payload)
        if records:
            return records[:limit]
    except (HTTPError, URLError, TimeoutError):
        pass

    try:
        return fetch_binance_announcements_from_rss(limit=limit)
    except (HTTPError, URLError, TimeoutError, ElementTree.ParseError) as exc:
        raise RuntimeError(
            "Binance source fetch failed. If your network blocks Binance, set BINANCE_PROXY_URL in .env "
            "(example: http://127.0.0.1:7890) and retry."
        ) from exc


def _records_from_api_payload(payload: dict[str, Any]) -> list[RawSourceRecord]:
    records: list[RawSourceRecord] = []
    for article in _extract_articles(payload):
        source_record_id = str(article.get("id") or article.get("code") or article.get("title") or "")
        if not source_record_id:
            continue

        records.append(
            RawSourceRecord(
                source_name="binance_announcements",
                source_record_id=source_record_id,
                title=article.get("title"),
                url=_to_absolute_url(article.get("url") or article.get("code")),
                published_at=_to_datetime(article.get("releaseDate") or article.get("publishDate")),
                raw_payload=article,
            )
        )
    return records


def fetch_binance_announcements_from_rss(limit: int = 20) -> list[RawSourceRecord]:
    req = request.Request(
        BINANCE_ANNOUNCEMENT_RSS,
        headers={
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        },
        method="GET",
    )
    with _open_url(req, timeout=20) as resp:
        raw_xml = resp.read().decode("utf-8")

    if not raw_xml.strip():
        raise ElementTree.ParseError("empty rss response")

    root = ElementTree.fromstring(raw_xml)
    items = root.findall("./channel/item")

    records: list[RawSourceRecord] = []
    for item in items[: max(1, min(limit, 50))]:
        title = item.findtext("title")
        link = item.findtext("link")
        guid = item.findtext("guid")
        pub_date = item.findtext("pubDate")

        published_at: datetime | None = None
        if pub_date:
            try:
                parsed = parsedate_to_datetime(pub_date)
                published_at = parsed.astimezone(timezone.utc)
            except (TypeError, ValueError):
                published_at = None

        source_record_id = guid or link or title or ""
        if not source_record_id:
            continue

        payload = {
            "title": title,
            "link": link,
            "guid": guid,
            "pubDate": pub_date,
        }
        records.append(
            RawSourceRecord(
                source_name="binance_announcements",
                source_record_id=source_record_id,
                title=title,
                url=link,
                published_at=published_at,
                raw_payload=payload,
            )
        )
    return records


def _open_url(req: request.Request, timeout: int):
    proxy_url = os.getenv("BINANCE_PROXY_URL", "").strip()
    if not proxy_url:
        return request.urlopen(req, timeout=timeout)

    opener = request.build_opener(
        request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    )
    return opener.open(req, timeout=timeout)
