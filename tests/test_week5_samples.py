from datetime import datetime, timezone
from pathlib import Path

from crypto_market_intel.db.engine import create_db_engine, create_session_factory
from crypto_market_intel.db.models import Base, Event, SourceRecord
from crypto_market_intel.pipeline.week5_samples import run_collect_historical_samples


def test_collect_week5_samples_creates_jsonl(monkeypatch, tmp_path):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        for idx in range(1, 5):
            source_record = SourceRecord(
                source_name="coindesk_news",
                source_record_id=f"sample-{idx}",
                title=f"Sample title {idx}",
                url=f"https://example.com/{idx}",
                published_at=datetime(2026, 5, idx, 10, 0, tzinfo=timezone.utc),
                raw_payload='{"description": "sample"}',
                content_hash=f"hash-{idx}",
                fetched_at=datetime.now(timezone.utc),
            )
            session.add(source_record)
            session.flush()

            session.add(
                Event(
                    event_id=f"event-{idx}",
                    source_record_db_id=source_record.id,
                    source="coindesk_news",
                    source_event_id=f"sample-{idx}",
                    event_type="project_news",
                    title=f"Sample event {idx}",
                    summary="summary",
                    raw_text="raw",
                    event_time=datetime(2026, 5, idx, 10, 0, tzinfo=timezone.utc),
                    detected_at=datetime.now(timezone.utc),
                    source_url=f"https://example.com/{idx}",
                    assets_json='["BTC"]',
                    importance_score=0.6,
                    importance_reason="reason",
                    status="analyzed",
                )
            )
        session.commit()

    monkeypatch.setattr(
        "crypto_market_intel.pipeline.week5_samples.create_db_engine",
        lambda _url: engine,
    )

    result = run_collect_historical_samples(sample_size=3, output_dir=str(tmp_path), seed=7, analyzed_only=True)

    assert result["requested"] == 3
    assert result["collected"] == 3
    assert result["warning"] == ""

    output_path = Path(str(result["output_path"]))
    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert all("\"sample_id\":" in line for line in lines)


def test_collect_week5_samples_returns_warning_when_candidates_not_enough(monkeypatch, tmp_path):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="sample-a",
            title="Sample A",
            url="https://example.com/a",
            published_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
            content_hash="hash-a",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(source_record)
        session.flush()

        session.add(
            Event(
                event_id="event-a",
                source_record_db_id=source_record.id,
                source="coindesk_news",
                source_event_id="sample-a",
                event_type="project_news",
                title="Sample event A",
                summary="summary",
                raw_text="raw",
                event_time=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/a",
                assets_json='["BTC"]',
                importance_score=0.6,
                importance_reason="reason",
                status="analyzed",
            )
        )
        session.commit()

    monkeypatch.setattr(
        "crypto_market_intel.pipeline.week5_samples.create_db_engine",
        lambda _url: engine,
    )

    result = run_collect_historical_samples(sample_size=5, output_dir=str(tmp_path), seed=7, analyzed_only=True)

    assert result["requested"] == 5
    assert result["collected"] == 1
    assert result["total_candidates"] == 1
    assert result["warning"] == "insufficient_candidates"
