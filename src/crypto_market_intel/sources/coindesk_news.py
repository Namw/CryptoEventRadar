from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib import request
from xml.etree import ElementTree

from crypto_market_intel.sources.base import RawSourceRecord

COINDESK_RSS_URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"


def fetch_coindesk_news(limit: int = 20) -> list[RawSourceRecord]:
    req = request.Request(
        COINDESK_RSS_URL,
        headers={
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "User-Agent": "crypto-market-intel-agent/0.1",
        },
        method="GET",
    )
    with request.urlopen(req, timeout=20) as resp:
        raw_xml = resp.read().decode("utf-8")

    return parse_coindesk_rss(raw_xml, limit=limit)


def parse_coindesk_rss(raw_xml: str, limit: int = 20) -> list[RawSourceRecord]:
    root = ElementTree.fromstring(raw_xml)
    items = root.findall("./channel/item")

    records: list[RawSourceRecord] = []
    for item in items[: max(1, min(limit, 50))]:
        title = item.findtext("title")
        link = item.findtext("link")
        guid = item.findtext("guid")
        pub_date = item.findtext("pubDate")
        description = item.findtext("description")

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
            "description": description,
        }
        records.append(
            RawSourceRecord(
                source_name="coindesk_news",
                source_record_id=source_record_id,
                title=title,
                url=link,
                published_at=published_at,
                raw_payload=payload,
            )
        )

    return records
