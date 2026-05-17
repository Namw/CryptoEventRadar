from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from crypto_market_intel.observability import emit_structured_log


@dataclass(frozen=True)
class AlertNotificationSummary:
    status: str
    channel: str
    sent_channels: list[str]
    errors: list[str]


def notify_alert_report(
    *,
    report_title: str,
    report_path: str,
    alerts: int,
    min_importance: float,
) -> AlertNotificationSummary:
    channel = _resolve_alert_channel()
    emit_structured_log(
        "alert.notify.start",
        channel=channel,
        report_title=report_title,
        report_path=report_path,
        alerts=alerts,
        min_importance=min_importance,
    )
    sent_channels: list[str] = []
    errors: list[str] = []

    summary_text = (
        f"{report_title} | alerts={alerts} | min_importance={min_importance:.2f} | "
        f"report_path={report_path}"
    )

    if channel in {"console", "both"}:
        print(f"[alert-notify][console] {summary_text}", flush=True)
        sent_channels.append("console")

    if channel in {"webhook", "both"}:
        webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
        if not webhook_url:
            errors.append("webhook_url_missing")
        else:
            try:
                _post_webhook(
                    webhook_url=webhook_url,
                    payload={
                        "title": report_title,
                        "alerts": alerts,
                        "min_importance": min_importance,
                        "report_path": str(Path(report_path)),
                    },
                )
                sent_channels.append("webhook")
            except Exception as exc:  # pragma: no cover - exercised by tests via monkeypatch
                errors.append(f"webhook_send_failed:{exc}")

    if errors and not sent_channels:
        result = AlertNotificationSummary(
            status="failed",
            channel=channel,
            sent_channels=sent_channels,
            errors=errors,
        )
        emit_structured_log("alert.notify.done", status=result.status, channel=result.channel, errors=result.errors)
        return result

    if errors:
        result = AlertNotificationSummary(
            status="partial",
            channel=channel,
            sent_channels=sent_channels,
            errors=errors,
        )
        emit_structured_log("alert.notify.done", status=result.status, channel=result.channel, errors=result.errors)
        return result

    result = AlertNotificationSummary(
        status="ok",
        channel=channel,
        sent_channels=sent_channels,
        errors=errors,
    )
    emit_structured_log("alert.notify.done", status=result.status, channel=result.channel, errors=result.errors)
    return result


def _resolve_alert_channel() -> str:
    raw_value = os.getenv("ALERT_NOTIFY_CHANNEL", "console").strip().lower()
    if raw_value in {"console", "webhook", "both"}:
        return raw_value
    return "console"


def _post_webhook(*, webhook_url: str, payload: dict[str, object]) -> None:
    timeout_seconds = _resolve_webhook_timeout_seconds()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", None)
            if status_code is not None and status_code >= 400:
                raise RuntimeError(f"http_status_{status_code}")
    except error.HTTPError as exc:
        raise RuntimeError(f"http_status_{exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"network_error:{exc.reason}") from exc


def _resolve_webhook_timeout_seconds() -> float:
    raw_value = os.getenv("ALERT_WEBHOOK_TIMEOUT_SECONDS", "8").strip()
    try:
        timeout = float(raw_value)
    except ValueError:
        timeout = 8.0
    return max(1.0, timeout)
