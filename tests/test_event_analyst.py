from datetime import datetime, timezone

import crypto_market_intel.agents.event_analyst as analyst_module
from crypto_market_intel.agents.event_analyst import analyze_event
from crypto_market_intel.schemas.event import UnifiedEvent


def test_analyze_event_builds_structured_result():
    event = UnifiedEvent(
        event_id="event-1",
        source="coindesk_news",
        source_event_id="news-1",
        event_type="listing",
        title="BTC and ETH market update",
        source_url="https://example.com/news",
        assets=["btc", "ETH", "ETH"],
        summary=None,
        raw_text="BTC and ETH are mentioned in this article.",
        event_time=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        detected_at=datetime(2026, 5, 14, 12, 1, tzinfo=timezone.utc),
    )

    analysis = analyze_event(event)

    assert analysis.event_id == "event-1"
    assert analysis.summary.startswith("BTC and ETH market update")
    assert analysis.assets == ["BTC", "ETH"]
    assert analysis.importance_score >= 0.85
    assert analysis.status == "analyzed"
    assert "BTC" in analysis.importance_reason


def test_analyze_event_prefers_llm_result(monkeypatch):
    event = UnifiedEvent(
        event_id="event-2",
        source="coindesk_news",
        source_event_id="news-2",
        event_type="project_news",
        title="ETH ETF progress update",
        source_url="https://example.com/news2",
        assets=["ETH"],
        summary=None,
        raw_text="sample",
        event_time=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        detected_at=datetime(2026, 5, 14, 12, 1, tzinfo=timezone.utc),
    )

    def fake_llm(_event):
        return (
            analyst_module.EventAnalysis(
                event_id=_event.event_id,
                source=_event.source,
                source_event_id=_event.source_event_id,
                event_type="listing",
                title=_event.title,
                summary="LLM 摘要",
                assets=["ETH"],
                importance_score=0.91,
                importance_reason="LLM 认为该事件短线影响较大。",
                status="analyzed",
            ),
            None,
            "deepseek-v4-pro",
        )

    monkeypatch.setattr(analyst_module, "_analyze_with_llm", fake_llm)

    analysis = analyze_event(event)

    assert analysis.summary == "LLM 摘要"
    assert analysis.event_type == "listing"
    assert analysis.importance_score == 0.91


def test_analyze_event_fallback_when_llm_errors(monkeypatch):
    event = UnifiedEvent(
        event_id="event-3",
        source="coindesk_news",
        source_event_id="news-3",
        event_type="project_news",
        title="SOL ecosystem update",
        source_url="https://example.com/news3",
        assets=["sol"],
        summary=None,
        raw_text="sample",
        event_time=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        detected_at=datetime(2026, 5, 14, 12, 1, tzinfo=timezone.utc),
    )

    def broken_llm(_event):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(analyst_module, "_analyze_with_llm", broken_llm)

    analysis = analyze_event(event)

    assert analysis.summary.startswith("SOL ecosystem update")
    assert analysis.assets == ["SOL"]
    assert analysis.status == "analyzed"


def test_analyze_event_with_trace_records_fallback_reason(monkeypatch):
    event = UnifiedEvent(
        event_id="event-4",
        source="coindesk_news",
        source_event_id="news-4",
        event_type="project_news",
        title="AVAX ecosystem update",
        source_url="https://example.com/news4",
        assets=["avax"],
        summary=None,
        raw_text="sample",
        event_time=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        detected_at=datetime(2026, 5, 14, 12, 1, tzinfo=timezone.utc),
    )

    def no_llm(_event):
        return None, "llm_not_configured", None

    monkeypatch.setattr(analyst_module, "_analyze_with_llm", no_llm)

    _analysis, trace = analyst_module.analyze_event_with_trace(event)

    assert trace.mode == "fallback_rules"
    assert trace.llm_attempted is False
    assert trace.llm_used is False
    assert trace.fallback_reason == "llm_not_configured"