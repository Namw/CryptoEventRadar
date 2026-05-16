from datetime import datetime, timezone

from crypto_market_intel.db.models import SourceRecord
from crypto_market_intel.pipeline.normalize import normalize_source_record


def test_normalize_source_record_sets_base_tags():
    source_record = SourceRecord(
        id=1,
        source_name="coindesk_news",
        source_record_id="abc-1",
        title="Bitcoin listing debate continues",
        url="https://example.com/news",
        published_at=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        raw_payload='{"description": "sample"}',
        content_hash="h",
        fetched_at=datetime.now(timezone.utc),
    )

    event = normalize_source_record(source_record)

    assert event.source == "coindesk_news"
    assert event.title == "Bitcoin listing debate continues"
    assert event.source_url == "https://example.com/news"
    assert event.event_time == datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    assert event.event_type in {"listing", "project_news"}


def test_normalize_source_record_extracts_assets():
    source_record = SourceRecord(
        id=1,
        source_name="coindesk_news",
        source_record_id="abc-2",
        title="BTC and ETH market update",
        url="https://example.com/news-2",
        published_at=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        raw_payload='{"description": "sample"}',
        content_hash="h",
        fetched_at=datetime.now(timezone.utc),
    )

    event = normalize_source_record(source_record)

    assert event.assets == ["BTC", "ETH"]
