from datetime import datetime, timezone

from crypto_market_intel.db.engine import create_db_engine, create_session_factory
from crypto_market_intel.db.models import Base, SourceRecord
from crypto_market_intel.db.repo import upsert_source_record


def test_upsert_source_record_deduplicates_by_source_and_record_id():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        _, created_first = upsert_source_record(
            session,
            source_name="binance_announcements",
            source_record_id="123",
            title="test",
            url="https://example.com",
            published_at=None,
            raw_payload="{}",
            content_hash="abc",
            fetched_at=datetime.now(timezone.utc),
        )
        _, created_second = upsert_source_record(
            session,
            source_name="binance_announcements",
            source_record_id="123",
            title="test",
            url="https://example.com",
            published_at=None,
            raw_payload="{}",
            content_hash="abc",
            fetched_at=datetime.now(timezone.utc),
        )
        session.commit()

    with session_factory() as session:
        count = session.query(SourceRecord).count()

    assert created_first is True
    assert created_second is False
    assert count == 1
