from __future__ import annotations

from crypto_market_intel.services.alert_service import notify_alert_report


def test_notify_alert_report_console_channel(monkeypatch, capsys):
    monkeypatch.setenv("ALERT_NOTIFY_CHANNEL", "console")

    result = notify_alert_report(
        report_title="Crypto Market Alerts - 2026-05-17",
        report_path="reports/alerts-demo.md",
        alerts=2,
        min_importance=0.8,
    )

    captured = capsys.readouterr()
    assert "[alert-notify][console]" in captured.out
    assert result.status == "ok"
    assert result.sent_channels == ["console"]
    assert result.errors == []


def test_notify_alert_report_webhook_channel_success(monkeypatch):
    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    def fake_urlopen(req, timeout=0):
        assert req.get_method() == "POST"
        assert req.full_url == "https://example.com/hook"
        assert timeout == 5.0
        payload_bytes = req.data
        assert payload_bytes is not None
        assert b'"alerts": 1' in payload_bytes
        return _Resp()

    monkeypatch.setenv("ALERT_NOTIFY_CHANNEL", "webhook")
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("ALERT_WEBHOOK_TIMEOUT_SECONDS", "5")
    monkeypatch.setattr("crypto_market_intel.services.alert_service.request.urlopen", fake_urlopen)

    result = notify_alert_report(
        report_title="Crypto Market Alerts - 2026-05-17",
        report_path="reports/alerts-demo.md",
        alerts=1,
        min_importance=0.9,
    )

    assert result.status == "ok"
    assert result.sent_channels == ["webhook"]
    assert result.errors == []


def test_notify_alert_report_webhook_channel_missing_url(monkeypatch):
    monkeypatch.setenv("ALERT_NOTIFY_CHANNEL", "webhook")
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)

    result = notify_alert_report(
        report_title="Crypto Market Alerts - 2026-05-17",
        report_path="reports/alerts-demo.md",
        alerts=1,
        min_importance=0.9,
    )

    assert result.status == "failed"
    assert result.sent_channels == []
    assert "webhook_url_missing" in result.errors
