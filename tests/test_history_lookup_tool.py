from datetime import datetime, timedelta, timezone

from crypto_market_intel.db.engine import create_db_engine, create_session_factory
from crypto_market_intel.db.models import Base, Event, SourceRecord
from crypto_market_intel.tools.base import ToolRequest
from crypto_market_intel.tools.history_lookup import HistoryLookupTool


def _build_history_fetcher_with_memory_db():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    now = datetime.now(timezone.utc)
    with session_factory() as session:
        source_1 = SourceRecord(
            source_name="coindesk_news",
            source_record_id="news-1",
            title="BTC listing event",
            url="https://example.com/1",
            published_at=now - timedelta(days=1),
            raw_payload='{"k":"v"}',
            content_hash="hash-1",
            fetched_at=now,
        )
        source_2 = SourceRecord(
            source_name="binance_announcements",
            source_record_id="announce-2",
            title="BTC security event",
            url="https://example.com/2",
            published_at=now - timedelta(days=2),
            raw_payload='{"k":"v"}',
            content_hash="hash-2",
            fetched_at=now,
        )
        source_3 = SourceRecord(
            source_name="coindesk_news",
            source_record_id="news-3",
            title="ETH event",
            url="https://example.com/3",
            published_at=now - timedelta(days=1),
            raw_payload='{"k":"v"}',
            content_hash="hash-3",
            fetched_at=now,
        )
        session.add_all([source_1, source_2, source_3])
        session.flush()

        session.add_all(
            [
                Event(
                    event_id="event-btc-1",
                    source_record_db_id=source_1.id,
                    source="coindesk_news",
                    source_event_id="news-1",
                    event_type="listing",
                    title="BTC listing",
                    summary="summary",
                    raw_text="raw",
                    event_time=now - timedelta(days=1),
                    detected_at=now - timedelta(days=1),
                    source_url="https://example.com/1",
                    assets_json='["BTC"]',
                    importance_score=0.91,
                    importance_reason="reason",
                    status="analyzed",
                ),
                Event(
                    event_id="event-btc-2",
                    source_record_db_id=source_2.id,
                    source="binance_announcements",
                    source_event_id="announce-2",
                    event_type="security",
                    title="BTC security",
                    summary="summary",
                    raw_text="raw",
                    event_time=now - timedelta(days=2),
                    detected_at=now - timedelta(days=2),
                    source_url="https://example.com/2",
                    assets_json='["BTC", "ETH"]',
                    importance_score=0.75,
                    importance_reason="reason",
                    status="analyzed",
                ),
                Event(
                    event_id="event-eth-1",
                    source_record_db_id=source_3.id,
                    source="coindesk_news",
                    source_event_id="news-3",
                    event_type="project_news",
                    title="ETH project news",
                    summary="summary",
                    raw_text="raw",
                    event_time=now - timedelta(days=1),
                    detected_at=now - timedelta(days=1),
                    source_url="https://example.com/3",
                    assets_json='["ETH"]',
                    importance_score=0.66,
                    importance_reason="reason",
                    status="analyzed",
                ),
            ]
        )
        session.commit()

    def fetcher(symbol: str, days: int, event_type: str | None, limit: int):
        ended_at = datetime.now(timezone.utc)
        started_at = ended_at - timedelta(days=days)
        with session_factory() as session:
            rows = (
                session.query(Event)
                .filter(Event.assets_json.like(f'%"{symbol}"%'))
                .filter(Event.event_time >= started_at)
                .filter(Event.event_time <= ended_at)
                .all()
            )

        if event_type:
            rows = [row for row in rows if row.event_type == event_type]

        rows = sorted(rows, key=lambda row: float(row.importance_score), reverse=True)[:limit]
        return [
            {
                "event_id": row.event_id,
                "event_time": row.event_time.isoformat() if row.event_time else None,
                "event_type": row.event_type,
                "importance_score": float(row.importance_score),
                "title": row.title,
            }
            for row in rows
        ]

    return fetcher


def test_history_lookup_tool_success_with_symbol_and_days():
    tool = HistoryLookupTool(fetcher=_build_history_fetcher_with_memory_db())
    result = tool.run(
        ToolRequest(tool_name="history_lookup", args={"symbol": "btc", "days": 7})
    )

    assert result.ok is True
    assert result.error is None
    assert result.data["query"]["symbol"] == "BTC"
    assert result.data["query"]["days"] == 7
    assert result.data["total"] == 2
    assert result.data["events"][0]["event_id"] == "event-btc-1"
    assert {item["event_type"] for item in result.data["events"]} == {"listing", "security"}


def test_history_lookup_tool_event_type_filter():
    tool = HistoryLookupTool(fetcher=_build_history_fetcher_with_memory_db())
    result = tool.run(
        ToolRequest(
            tool_name="history_lookup",
            args={"symbol": "BTC", "days": 7, "event_type": "security"},
        )
    )

    assert result.ok is True
    assert result.error is None
    assert result.data["total"] == 1
    assert result.data["events"][0]["event_type"] == "security"


def test_history_lookup_tool_invalid_symbol():
    tool = HistoryLookupTool(fetcher=lambda _symbol, _days, _event_type, _limit: [])
    result = tool.run(ToolRequest(tool_name="history_lookup", args={"symbol": ""}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "invalid_symbol"


def test_history_lookup_tool_invalid_days():
    tool = HistoryLookupTool(fetcher=lambda _symbol, _days, _event_type, _limit: [])
    result = tool.run(ToolRequest(tool_name="history_lookup", args={"symbol": "BTC", "days": 0}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "invalid_days"


def test_history_lookup_tool_empty_result_is_success():
    tool = HistoryLookupTool(fetcher=lambda _symbol, _days, _event_type, _limit: [])
    result = tool.run(
        ToolRequest(tool_name="history_lookup", args={"symbol": "BTC", "days": 7, "event_type": "listing"})
    )

    assert result.ok is True
    assert result.error is None
    assert result.data["total"] == 0
    assert result.data["events"] == []