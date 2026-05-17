from datetime import datetime, timezone
from pathlib import Path

import crypto_market_intel.pipeline.publish as publish_module
from crypto_market_intel.db.engine import create_db_engine, create_session_factory
from crypto_market_intel.db.models import Base, Event, SourceRecord
from crypto_market_intel.pipeline.publish import _publish_alerts_with_session_factory, _publish_with_session_factory


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

        second_source_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="news-2b",
            title="BTC stable",
            url="https://example.com/news2b",
            published_at=datetime(2026, 5, 16, 11, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
            content_hash="hash-2b",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(second_source_record)
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
        session.add(
            Event(
                event_id="event-2b",
                source_record_db_id=second_source_record.id,
                source="coindesk_news",
                source_event_id="news-2b",
                event_type="project_news",
                title="BTC stable",
                summary="BTC remains rangebound",
                raw_text="sample",
                event_time=datetime(2026, 5, 16, 11, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/news2b",
                assets_json='["BTC"]',
                importance_score=0.6,
                importance_reason="Limited near-term catalyst",
                status="analyzed",
            )
        )
        session.commit()

    calls: list[list[int]] = []

    def fake_build_card_translator(*, translate_to_zh: bool):
        assert translate_to_zh is True

        def fake_translate(items, progress_callback=None):
            calls.append([item.index for item in items])
            if progress_callback is not None:
                progress_callback(1, 1, items)
            return {
                item.index: (
                    f"中文:{item.title}",
                    f"中文:{item.summary}",
                    f"中文:{item.importance_reason}",
                )
                for item in items
            }

        return fake_translate, "ok"

    monkeypatch.setattr(publish_module, "_build_card_translator", fake_build_card_translator)

    result = _publish_with_session_factory(
        session_factory,
        limit=10,
        reports_dir=str(tmp_path),
        translate_to_zh=True,
    )

    assert calls == [[1, 2]]
    assert result["translated_cards"] == 2
    assert result["translation_fallback_cards"] == 0
    report_path = Path(str(result["report_path"]))
    content = report_path.read_text(encoding="utf-8")
    assert "中文:ETH rises" in content
    assert "中文:ETH gains momentum" in content
    assert "中文:BTC stable" in content


def test_publish_translate_zh_prints_progress(monkeypatch, tmp_path, capsys):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="news-progress-1",
            title="SOL ecosystem update",
            url="https://example.com/news-progress-1",
            published_at=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
            content_hash="hash-progress-1",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(source_record)
        session.flush()

        session.add(
            Event(
                event_id="event-progress-1",
                source_record_db_id=source_record.id,
                source="coindesk_news",
                source_event_id="news-progress-1",
                event_type="project_news",
                title="SOL ecosystem update",
                summary="SOL ecosystem remains active",
                raw_text="sample",
                event_time=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/news-progress-1",
                assets_json='["SOL"]',
                importance_score=0.75,
                importance_reason="Potential market attention",
                status="analyzed",
            )
        )
        session.commit()

    def fake_build_card_translator(*, translate_to_zh: bool):
        assert translate_to_zh is True

        def fake_translate(items, progress_callback=None):
            if progress_callback is not None:
                progress_callback(1, 1, items)
            return {
                item.index: (
                    f"中文:{item.title}",
                    f"中文:{item.summary}",
                    f"中文:{item.importance_reason}",
                )
                for item in items
            }

        return fake_translate, "ok"

    monkeypatch.setattr(publish_module, "_build_card_translator", fake_build_card_translator)

    _publish_with_session_factory(
        session_factory,
        limit=10,
        reports_dir=str(tmp_path),
        translate_to_zh=True,
    )

    captured = capsys.readouterr()
    assert "[publish-report] 正在翻译批次 1/1（1 条）: SOL ecosystem update" in captured.out


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


def test_publish_alerts_generates_markdown_for_high_importance_events(tmp_path):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="alert-1",
            title="BTC ETF inflow spikes",
            url="https://example.com/alert-1",
            published_at=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
            content_hash="hash-alert-1",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(source_record)
        session.flush()

        low_score_record = SourceRecord(
            source_name="coindesk_news",
            source_record_id="alert-2",
            title="Minor altcoin update",
            url="https://example.com/alert-2",
            published_at=datetime(2026, 5, 16, 13, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
            content_hash="hash-alert-2",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(low_score_record)
        session.flush()

        session.add(
            Event(
                event_id="alert-event-1",
                source_record_db_id=source_record.id,
                source="coindesk_news",
                source_event_id="alert-1",
                event_type="project_news",
                title="BTC ETF inflow spikes",
                summary="Large ETF inflows may affect short-term sentiment",
                raw_text="sample",
                event_time=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/alert-1",
                assets_json='["BTC"]',
                importance_score=0.92,
                importance_reason="Strong macro demand signal",
                status="analyzed",
            )
        )
        session.add(
            Event(
                event_id="alert-event-2",
                source_record_db_id=low_score_record.id,
                source="coindesk_news",
                source_event_id="alert-2",
                event_type="project_news",
                title="Minor altcoin update",
                summary="Routine ecosystem update",
                raw_text="sample",
                event_time=datetime(2026, 5, 16, 13, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://example.com/alert-2",
                assets_json='["ALT"]',
                importance_score=0.55,
                importance_reason="Low urgency",
                status="analyzed",
            )
        )
        session.commit()

    result = _publish_alerts_with_session_factory(
        session_factory,
        limit=10,
        reports_dir=str(tmp_path),
        min_importance=0.8,
    )

    assert result["alerts"] == 1
    assert result["min_importance"] == 0.8
    report_path = Path(str(result["report_path"]))
    assert report_path.exists()
    assert report_path.name.startswith("alerts-")
    content = report_path.read_text(encoding="utf-8")
    assert "高优先级事件告警" in content
    assert "BTC ETF inflow spikes" in content
    assert "Minor altcoin update" not in content


def test_publish_alerts_writes_empty_state_when_no_events_match_threshold(tmp_path):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    result = _publish_alerts_with_session_factory(
        session_factory,
        limit=10,
        reports_dir=str(tmp_path),
        min_importance=0.9,
    )

    assert result["alerts"] == 0
    report_path = Path(str(result["report_path"]))
    content = report_path.read_text(encoding="utf-8")
    assert "当前无命中告警阈值的事件" in content
    assert "告警阈值：0.90" in content


def test_publish_alerts_normalizes_legacy_binance_source_url(tmp_path):
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        source_record = SourceRecord(
            source_name="binance_announcements",
            source_record_id="legacy-alert-1",
            title="Binance listing update",
            url="https://www.binance.com506a7482e6b94bc58f3e275cb15c2861",
            published_at=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
            raw_payload='{"description": "sample"}',
            content_hash="hash-legacy-alert-1",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(source_record)
        session.flush()

        session.add(
            Event(
                event_id="legacy-alert-event-1",
                source_record_db_id=source_record.id,
                source="binance_announcements",
                source_event_id="legacy-alert-1",
                event_type="listing",
                title="Binance listing update",
                summary="legacy url regression test",
                raw_text="sample",
                event_time=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
                detected_at=datetime.now(timezone.utc),
                source_url="https://www.binance.com506a7482e6b94bc58f3e275cb15c2861",
                assets_json='["MEGA"]',
                importance_score=0.95,
                importance_reason="High-impact listing",
                status="analyzed",
            )
        )
        session.commit()

    result = _publish_alerts_with_session_factory(
        session_factory,
        limit=10,
        reports_dir=str(tmp_path),
        min_importance=0.8,
    )

    report_path = Path(str(result["report_path"]))
    content = report_path.read_text(encoding="utf-8")
    assert "https://www.binance.com/en/support/announcement/detail/506a7482e6b94bc58f3e275cb15c2861" in content
    assert "https://www.binance.com506a7482e6b94bc58f3e275cb15c2861" not in content
