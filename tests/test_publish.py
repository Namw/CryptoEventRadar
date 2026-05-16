from datetime import datetime, timezone
from pathlib import Path

import crypto_market_intel.pipeline.publish as publish_module
from crypto_market_intel.db.engine import create_db_engine, create_session_factory
from crypto_market_intel.db.models import Base, Event, SourceRecord
from crypto_market_intel.pipeline.publish import _publish_with_session_factory


def test_publish_generates_markdown_report(tmp_path):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="news-1",
            title="BTC and ETH market update",
            url="https://example.com/news",
            published_at=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
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
                event_type="listing",
                title="BTC and ETH market update",
                summary="测试摘要",
                raw_text="sample",
                event_time=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/news",
                assets_json='["BTC", "ETH"]',
                importance_score=0.9,
                importance_reason="测试重要度说明",
                status="analyzed",
            )
        )
        session.commit()

    result = _publish_with_session_factory(session_factory, limit=10, reports_dir=str(tmp_path))

    assert result["events"] == 1
    report_path = Path(str(result["report_path"]))
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "重点事件卡片" in content
    assert "BTC and ETH market update" in content
    assert "https://example.com/news" in content


def test_publish_translate_zh_success(monkeypatch, tmp_path):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="news-2",
            title="ETH rises",
            url="https://example.com/news2",
            published_at=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
            content_hash="hash-2",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(source_record)
        session.flush()

        session.add(
            Event(
                event_id="event-2",
                source_record_db_id=source_record.id,
                source="coindesk_news",
                source_event_id="news-2",
                event_type="project_news",
                title="ETH rises",
                summary="ETH gains momentum",
                raw_text="sample",
                event_time=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/news2",
                assets_json='["ETH"]',
                importance_score=0.7,
                importance_reason="Potential momentum impact",
                status="analyzed",
            )
        )
        session.commit()

    def fake_build_card_translator(*, translate_to_zh: bool):
        assert translate_to_zh is True

        def fake_translate(title: str, summary: str, importance_reason: str):
            return f"中文:{title}", f"中文:{summary}", f"中文:{importance_reason}"

        return fake_translate, "ok"

    monkeypatch.setattr(publish_module, "_build_card_translator", fake_build_card_translator)

    result = _publish_with_session_factory(
        session_factory,
        limit=10,
        reports_dir=str(tmp_path),
        translate_to_zh=True,
    )

    assert result["translated_cards"] == 1
    assert result["translation_fallback_cards"] == 0
    report_path = Path(str(result["report_path"]))
    content = report_path.read_text(encoding="utf-8")
    assert "中文:ETH rises" in content
    assert "中文:ETH gains momentum" in content


def test_publish_translate_zh_fallback_when_translator_unavailable(monkeypatch, tmp_path):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="news-3",
            title="BTC stable",
            url="https://example.com/news3",
            published_at=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
            content_hash="hash-3",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(source_record)
        session.flush()

        session.add(
            Event(
                event_id="event-3",
                source_record_db_id=source_record.id,
                source="coindesk_news",
                source_event_id="news-3",
                event_type="project_news",
                title="BTC stable",
                summary="BTC remains rangebound",
                raw_text="sample",
                event_time=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/news3",
                assets_json='["BTC"]',
                importance_score=0.6,
                importance_reason="Limited near-term catalyst",
                status="analyzed",
            )
        )
        session.commit()

    def fake_build_card_translator(*, translate_to_zh: bool):
        assert translate_to_zh is True
        return None, "llm_not_configured"

    monkeypatch.setattr(publish_module, "_build_card_translator", fake_build_card_translator)

    result = _publish_with_session_factory(
        session_factory,
        limit=10,
        reports_dir=str(tmp_path),
        translate_to_zh=True,
    )

    assert result["translated_cards"] == 0
    assert result["translation_fallback_cards"] == 1
    assert result["translation_reason"] == "llm_not_configured"
    report_path = Path(str(result["report_path"]))
    content = report_path.read_text(encoding="utf-8")
    assert "BTC stable" in content
