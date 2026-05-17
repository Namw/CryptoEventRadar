from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Callable
from urllib import error, parse, request

from crypto_market_intel.tools.base import ToolRequest, ToolResult


ExchangeFetcher = Callable[[str, str, float], dict[str, Any]]


class ExchangeInfoTool:
    name = "exchange_info"
    source = "exchange_public_api"
    _SUPPORTED_EXCHANGES = {"binance"}

    def __init__(
        self,
        *,
        quote_asset: str = "USDT",
        timeout_seconds: float = 8.0,
        fetcher: ExchangeFetcher | None = None,
    ) -> None:
        self.quote_asset = quote_asset.upper()
        self.timeout_seconds = max(1.0, timeout_seconds)
        self._fetcher = fetcher or _fetch_exchange_pair_info

    def run(self, request: ToolRequest) -> ToolResult:
        exchange = str(request.args.get("exchange") or "binance").strip().lower()
        symbol = str(request.args.get("symbol") or "").strip().upper()
        if exchange not in self._SUPPORTED_EXCHANGES:
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="invalid_exchange",
                message="exchange is required and currently only supports: binance",
                details={"exchange": exchange},
            )

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
            payload = self._fetcher(exchange, pair, self.timeout_seconds)
        except TimeoutError:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="timeout",
                message="exchange info request timed out",
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

        symbol_info = _extract_symbol_info(payload, pair)
        if symbol_info is None:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="empty_result",
                message=f"no exchange info for {exchange}:{pair}",
                latency_ms=elapsed_ms,
            )

        status = str(symbol_info.get("status") or "UNKNOWN").upper()
        is_spot_allowed = symbol_info.get("isSpotTradingAllowed") is not False
        tradable = status == "TRADING" and is_spot_allowed

        elapsed_ms = int((perf_counter() - started) * 1000)
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "exchange": exchange,
                "symbol": symbol,
                "tradable": tradable,
                "pairs": [str(symbol_info.get("symbol") or pair)],
                "status": status,
                "reference_links": _build_reference_links(exchange, pair),
                "source": f"{exchange}_public_api",
            },
            latency_ms=elapsed_ms,
        )


def _fetch_exchange_pair_info(exchange: str, pair: str, timeout_seconds: float) -> dict[str, Any]:
    if exchange == "binance":
        query = parse.urlencode({"symbol": pair})
        url = f"https://api.binance.com/api/v3/exchangeInfo?{query}"
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

    raise RuntimeError("unsupported_exchange")


def _extract_symbol_info(payload: dict[str, Any], pair: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    symbols = payload.get("symbols")
    if isinstance(symbols, list):
        for item in symbols:
            if isinstance(item, dict) and str(item.get("symbol") or "").upper() == pair.upper():
                return item

    if str(payload.get("symbol") or "").upper() == pair.upper():
        return payload

    return None


def _build_reference_links(exchange: str, pair: str) -> list[str]:
    if exchange == "binance":
        query = parse.urlencode({"symbol": pair})
        return [
            f"https://api.binance.com/api/v3/exchangeInfo?{query}",
            "https://www.binance.com/en/support/announcement",
        ]
    return []


def _is_valid_symbol(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{2,15}", symbol))