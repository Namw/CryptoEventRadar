from datetime import datetime, timezone
import json

from crypto_market_intel.db.engine import create_db_engine, create_session_factory
from crypto_market_intel.db.models import Base, Event, SourceRecord
from crypto_market_intel.services.event_service import _analyze_events_with_session_factory


def test_analyze_events_updates_db_rows():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="news-1",
            title="BTC and ETH market update",
            url="https://example.com/news",
            published_at=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "BTC and ETH are mentioned in this article."}',
            content_hash="hash-1",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(source_record)
        session.flush()
        session.add(
            Event(
                event_id="event-1",
                source_record_db_id=source_record.id,
                source="coindesk_news",
                source_event_id="news-1",
                event_type="project_news",
                title="BTC and ETH market update",
                summary=None,
                raw_text="BTC and ETH are mentioned in this article.",
                event_time=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/news",
                assets_json='["BTC", "ETH"]',
                status="new",
            )
        )
        session.commit()

    result = _analyze_events_with_session_factory(session_factory, limit=10)

    assert result["fetched"] == 1
    assert result["inserted"] == 1
    assert result["llm_used"] == 0
    assert result["fallback_rules"] == 1
    assert result["elapsed_seconds"] >= 0

    with session_factory() as session:
        event = session.query(Event).one()

    assert event.status == "analyzed"
    assert event.summary.startswith("BTC and ETH market update")
    assert event.event_type in {"project_news", "listing", "delisting", "security", "other"}
    assert json.loads(event.assets_json) == ["BTC", "ETH"]
    assert 0.0 <= event.importance_score <= 1.0
    assert event.importance_reason