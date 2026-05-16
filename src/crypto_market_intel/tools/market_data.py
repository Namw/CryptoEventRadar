from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable
from urllib import error, parse, request

from crypto_market_intel.tools.base import ToolRequest, ToolResult


MarketFetcher = Callable[[str, float], dict[str, Any]]


class MarketDataTool:
    name = "market_data"
    source = "binance_public_api"

    def __init__(
        self,
        *,
        quote_asset: str = "USDT",
        timeout_seconds: float = 6.0,
        fetcher: MarketFetcher | None = None,
    ) -> None:
        self.quote_asset = quote_asset.upper()
        self.timeout_seconds = max(1.0, timeout_seconds)
        self._fetcher = fetcher or _fetch_market_24h_from_binance

    def run(self, request_data: ToolRequest) -> ToolResult:
        symbol = str(request_data.args.get("symbol") or "").strip().upper()
        if not _is_valid_symbol(symbol):
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="invalid_symbol",
                message="symbol is required and must be 2-15 uppercase letters or digits",
            )

        pair = f"{symbol}{self.quote_asset}"
        started = perf_counter()
        try:
            payload = self._fetcher(pair, self.timeout_seconds)
        except TimeoutError:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="timeout",
                message="market data request timed out",
                retryable=True,
                latency_ms=elapsed_ms,
            )
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

        if not payload:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="empty_result",
                message=f"no market data for {pair}",
                latency_ms=elapsed_ms,
            )

        elapsed_ms = int((perf_counter() - started) * 1000)
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "symbol": symbol,
                "pair": pair,
                "price": _to_float(payload.get("lastPrice")),
                "change_24h_pct": _to_float(payload.get("priceChangePercent")),
                "volume_24h": _to_float(payload.get("volume")),
                "as_of": _to_iso(payload.get("closeTime")),
            },
            latency_ms=elapsed_ms,
        )


def _fetch_market_24h_from_binance(pair: str, timeout_seconds: float) -> dict[str, Any]:
    query = parse.urlencode({"symbol": pair})
    url = f"https://api.binance.com/api/v3/ticker/24hr?{query}"

    try:
        with request.urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code == 400:
            return {}
        raise RuntimeError(f"binance_http_{exc.code}") from exc
    except TimeoutError as exc:
        raise TimeoutError("timeout") from exc
    except error.URLError as exc:
        reason = str(getattr(exc, "reason", "")).lower()
        if "timed out" in reason or "timeout" in reason:
            raise TimeoutError("timeout") from exc
        raise RuntimeError("network_error") from exc

    if isinstance(payload, dict):
        return payload
    return {}


def _is_valid_symbol(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{2,15}", symbol))


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_iso(close_time_ms: Any) -> str | None:
    try:
        timestamp = float(close_time_ms) / 1000.0
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
