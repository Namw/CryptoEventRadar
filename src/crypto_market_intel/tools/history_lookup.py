from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, Callable

from sqlalchemy import func, select

from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base, Event
from crypto_market_intel.tools.base import ToolRequest, ToolResult


HistoryFetcher = Callable[[str, int, str | None, int], list[dict[str, Any]]]


class HistoryLookupTool:
    name = "history_lookup"
    source = "local_event_db"

    def __init__(
        self,
        *,
        default_days: int = 7,
        default_limit: int = 20,
        fetcher: HistoryFetcher | None = None,
    ) -> None:
        self.default_days = max(1, default_days)
        self.default_limit = max(1, default_limit)
        self._fetcher = fetcher or _fetch_history_events

    def run(self, request: ToolRequest) -> ToolResult:
        symbol = str(request.args.get("symbol") or "").strip().upper()
        if not _is_valid_symbol(symbol):
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="invalid_symbol",
                message="symbol is required and must be 2-15 uppercase letters or digits",
            )

        raw_days = request.args.get("days", self.default_days)
        days = _to_positive_int(raw_days)
        if days is None:
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="invalid_days",
                message="days must be a positive integer",
            )

        raw_limit = request.args.get("limit", self.default_limit)
        limit = _to_positive_int(raw_limit)
        if limit is None:
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="invalid_limit",
                message="limit must be a positive integer",
            )

        event_type = str(request.args.get("event_type") or "").strip().lower() or None

        ended_at = datetime.now(timezone.utc)
        started_at = ended_at - timedelta(days=days)

        started = perf_counter()
        try:
            events = self._fetcher(symbol, days, event_type, limit)
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="upstream_error",
                message=str(exc),
                retryable=True,
                latency_ms=elapsed_ms,
            )

        elapsed_ms = int((perf_counter() - started) * 1000)
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "query": {
                    "symbol": symbol,
                    "days": days,
                    "event_type": event_type,
                    "limit": limit,
                    "since": started_at.isoformat(),
                    "until": ended_at.isoformat(),
                },
                "total": len(events),
                "events": events,
                "source": self.source,
            },
            latency_ms=elapsed_ms,
        )


def _fetch_history_events(symbol: str, days: int, event_type: str | None, limit: int) -> list[dict[str, Any]]:
    engine = create_db_engine(get_database_url())
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    ended_at = datetime.now(timezone.utc)
    started_at = ended_at - timedelta(days=days)
    symbol_pattern = f'%"{symbol}"%'

    with session_factory() as session:
        event_time_expr = func.coalesce(Event.event_time, Event.detected_at)
        stmt = (
            select(Event)
            .where(Event.assets_json.like(symbol_pattern))
            .where(event_time_expr >= started_at)
            .where(event_time_expr <= ended_at)
            .order_by(Event.importance_score.desc(), event_time_expr.desc(), Event.id.desc())
            .limit(max(1, limit))
        )
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)

        rows = list(session.scalars(stmt).all())

    return [_event_to_item(row) for row in rows]


def _event_to_item(event: Event) -> dict[str, Any]:
    assets = _parse_assets(event.assets_json)
    return {
        "event_id": event.event_id,
        "event_time": _to_iso(event.event_time or event.detected_at),
        "event_type": event.event_type,
        "importance_score": float(event.importance_score),
        "title": event.title,
        "assets": assets,
        "source": event.source,
    }


def _parse_assets(raw_assets: str) -> list[str]:
    try:
        parsed = json.loads(raw_assets)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    assets: list[str] = []
    for item in parsed:
        text = str(item).strip().upper()
        if text:
            assets.append(text)
    return assets


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


def _is_valid_symbol(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{2,15}", symbol))


def _to_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed