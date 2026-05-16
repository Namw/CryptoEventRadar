from datetime import datetime, timezone

from crypto_market_intel.db.models import SourceRecord
from crypto_market_intel.pipeline.normalize import _get_source_credibility, normalize_source_record


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


def test_source_credibility_known_sources():
    # 已知来源应返回预定义的可信度分值
    assert _get_source_credibility("binance_announcements") == 0.95
    assert _get_source_credibility("coindesk_news") == 0.75


def test_source_credibility_unknown_source():
    # 未知来源应返回默认分值 0.6
    assert _get_source_credibility("unknown_source") == 0.6


def test_normalize_assigns_source_credibility():
    # normalize 流程应将可信度写入 UnifiedEvent
    source_record = SourceRecord(
        id=3,
        source_name="binance_announcements",
        source_record_id="abc-3",
        title="New token listing announcement",
        url="https://binance.com/ann-3",
        published_at=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        raw_payload='{"description": "sample"}',
        content_hash="h3",
        fetched_at=datetime.now(timezone.utc),
    )

    event = normalize_source_record(source_record)

    assert event.source_credibility == 0.95
