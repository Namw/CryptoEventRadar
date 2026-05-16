from datetime import datetime, timezone

from crypto_market_intel.db.engine import create_db_engine, create_session_factory
from crypto_market_intel.db.models import Base, Event, SourceRecord
from crypto_market_intel.pipeline.deduplicate import _build_dedupe_key, _deduplicate_with_session_factory


def _seed_source_record(session, record_id: str) -> SourceRecord:
    record = SourceRecord(
        source_name="coindesk_news",
        source_record_id=record_id,
        title="seed",
        url=f"https://example.com/{record_id}",
        published_at=datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc),
        raw_payload='{"description":"seed"}',
        content_hash=f"hash-{record_id}",
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(record)
    session.flush()
    return record


def test_build_dedupe_key_same_payload_same_key():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record_1 = _seed_source_record(session, "1")
        source_record_2 = _seed_source_record(session, "2")

        event_1 = Event(
            event_id="event-1",
            source_record_db_id=source_record_1.id,
            source="coindesk_news",
            source_event_id="1",
            event_type="listing",
            title="BTC Listing Incoming",
            summary="s",
            raw_text="r",
            event_time=datetime.now(timezone.utc),
            detected_at=datetime.now(timezone.utc),
            source_url="https://example.com/1",
            assets_json='["BTC"]',
            importance_score=0.5,
            importance_reason="reason",
            status="analyzed",
        )
        event_2 = Event(
            event_id="event-2",
            source_record_db_id=source_record_2.id,
            source="coindesk_news",
            source_event_id="2",
            event_type="listing",
            title="BTC listing incoming",
            summary="s",
            raw_text="r",
            event_time=datetime.now(timezone.utc),
            detected_at=datetime.now(timezone.utc),
            source_url="https://example.com/2",
            assets_json='["BTC"]',
            importance_score=0.5,
            importance_reason="reason",
            status="analyzed",
        )

        assert _build_dedupe_key(event_1) == _build_dedupe_key(event_2)


def test_run_deduplicate_marks_duplicate_events():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record_1 = _seed_source_record(session, "dup-1")
        source_record_2 = _seed_source_record(session, "dup-2")

        session.add(
            Event(
                event_id="event-dup-1",
                source_record_db_id=source_record_1.id,
                source="coindesk_news",
                source_event_id="dup-1",
                event_type="listing",
                title="ETH listing update",
                summary="summary",
                raw_text="raw",
                event_time=datetime.now(timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/dup-1",
                assets_json='["ETH"]',
                importance_score=0.7,
                importance_reason="reason",
                status="analyzed",
            )
        )
        session.add(
            Event(
                event_id="event-dup-2",
                source_record_db_id=source_record_2.id,
                source="coindesk_news",
                source_event_id="dup-2",
                event_type="listing",
                title="ETH Listing Update",
                summary="summary",
                raw_text="raw",
                event_time=datetime.now(timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/dup-2",
                assets_json='["ETH"]',
                importance_score=0.7,
                importance_reason="reason",
                status="analyzed",
            )
        )
        session.commit()

    result = _deduplicate_with_session_factory(session_factory, limit=50, verbose=False)

    assert result["fetched"] == 2
    assert result["deduplicated"] == 1

    with session_factory() as session:
        events = session.query(Event).order_by(Event.id.asc()).all()
        assert events[0].status == "analyzed"
        assert events[1].status == "deduplicated"
        assert events[0].cluster_key
        assert events[0].cluster_key == events[1].cluster_key


def test_run_deduplicate_merges_fuzzy_similar_titles_in_time_window():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record_1 = _seed_source_record(session, "fuzzy-1")
        source_record_2 = _seed_source_record(session, "fuzzy-2")

        session.add(
            Event(
                event_id="event-fuzzy-1",
                source_record_db_id=source_record_1.id,
                source="coindesk_news",
                source_event_id="fuzzy-1",
                event_type="security",
                title="Major Solana wallet exploit triggers losses",
                summary="summary",
                raw_text="raw",
                event_time=datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/fuzzy-1",
                assets_json='["SOL"]',
                importance_score=0.8,
                importance_reason="reason",
                status="analyzed",
            )
        )
        session.add(
            Event(
                event_id="event-fuzzy-2",
                source_record_db_id=source_record_2.id,
                source="coindesk_news",
                source_event_id="fuzzy-2",
                event_type="security",
                title="Solana wallet exploit causes major losses",
                summary="summary",
                raw_text="raw",
                event_time=datetime(2026, 5, 17, 18, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/fuzzy-2",
                assets_json='["SOL"]',
                importance_score=0.8,
                importance_reason="reason",
                status="analyzed",
            )
        )
        session.commit()

    result = _deduplicate_with_session_factory(session_factory, limit=50, verbose=False)

    assert result["fetched"] == 2
    assert result["deduplicated"] == 1

    with session_factory() as session:
        events = session.query(Event).order_by(Event.id.asc()).all()
        assert events[0].cluster_key == events[1].cluster_key
        assert events[1].status == "deduplicated"
