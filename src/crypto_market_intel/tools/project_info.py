from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Callable
from urllib import error, parse, request

from crypto_market_intel.tools.base import ToolRequest, ToolResult


ProjectFetcher = Callable[[str, float], dict[str, Any]]


class ProjectInfoTool:
    name = "project_info"
    source = "coingecko_public_api"

    def __init__(
        self,
        *,
        timeout_seconds: float = 8.0,
        fetcher: ProjectFetcher | None = None,
    ) -> None:
        self.timeout_seconds = max(1.0, timeout_seconds)
        self._fetcher = fetcher or _fetch_project_info_from_coingecko

    def run(self, request_data: ToolRequest) -> ToolResult:
        symbol = str(request_data.args.get("symbol") or "").strip().upper()
        if not _is_valid_symbol(symbol):
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="invalid_symbol",
                message="symbol is required and must be 2-15 uppercase letters or digits",
            )

        started = perf_counter()
        try:
            payload = self._fetcher(symbol, self.timeout_seconds)
        except TimeoutError:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="timeout",
                message="project info request timed out",
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
                message=f"no project info for symbol={symbol}",
                latency_ms=elapsed_ms,
            )

        elapsed_ms = int((perf_counter() - started) * 1000)
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "symbol": symbol,
                "project_name": _to_str(payload.get("name")),
                "website": _extract_website(payload),
                "chain": _extract_chain(payload),
                "tags": _extract_tags(payload),
                "source": self.source,
            },
            latency_ms=elapsed_ms,
        )


def _fetch_project_info_from_coingecko(symbol: str, timeout_seconds: float) -> dict[str, Any]:
    search_query = parse.urlencode({"query": symbol})
    search_url = f"https://api.coingecko.com/api/v3/search?{search_query}"

    try:
        with request.urlopen(search_url, timeout=timeout_seconds) as response:
            search_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise RuntimeError(f"coingecko_http_{exc.code}") from exc
    except TimeoutError as exc:
        raise TimeoutError("timeout") from exc
    except error.URLError as exc:
        reason = str(getattr(exc, "reason", "")).lower()
        if "timed out" in reason or "timeout" in reason:
            raise TimeoutError("timeout") from exc
        raise RuntimeError("network_error") from exc

    coin_id = _pick_coin_id(search_payload, symbol)
    if not coin_id:
        return {}

    detail_query = parse.urlencode(
        {
            "localization": "false",
            "tickers": "false",
            "market_data": "false",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
        }
    )
    detail_url = f"https://api.coingecko.com/api/v3/coins/{parse.quote(coin_id)}?{detail_query}"

    try:
        with request.urlopen(detail_url, timeout=timeout_seconds) as response:
            detail_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise RuntimeError(f"coingecko_http_{exc.code}") from exc
    except TimeoutError as exc:
        raise TimeoutError("timeout") from exc
    except error.URLError as exc:
        reason = str(getattr(exc, "reason", "")).lower()
        if "timed out" in reason or "timeout" in reason:
            raise TimeoutError("timeout") from exc
        raise RuntimeError("network_error") from exc

    if isinstance(detail_payload, dict):
        return detail_payload
    return {}


def _pick_coin_id(search_payload: dict[str, Any], symbol: str) -> str | None:
    coins = search_payload.get("coins") if isinstance(search_payload, dict) else None
    if not isinstance(coins, list):
        return None

    symbol_upper = symbol.upper()
    exact_match: str | None = None
    fallback_match: str | None = None

    for item in coins:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        item_symbol = str(item.get("symbol") or "").strip().upper()
        if not item_id:
            continue
        if item_symbol == symbol_upper:
            exact_match = item_id
            break
        if fallback_match is None and item_symbol.startswith(symbol_upper):
            fallback_match = item_id

    return exact_match or fallback_match


def _extract_website(payload: dict[str, Any]) -> str | None:
    links = payload.get("links") if isinstance(payload, dict) else None
    if isinstance(links, dict):
        homepage = links.get("homepage")
        if isinstance(homepage, list):
            for item in homepage:
                if isinstance(item, str) and item.strip():
                    return item.strip()
    return None


def _extract_chain(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return None

    asset_platform_id = payload.get("asset_platform_id")
    if isinstance(asset_platform_id, str) and asset_platform_id.strip():
        return asset_platform_id.strip()

    platforms = payload.get("platforms")
    if isinstance(platforms, dict):
        for key, value in platforms.items():
            key_text = str(key or "").strip()
            value_text = str(value or "").strip()
            if key_text and value_text:
                return key_text

    return None


def _extract_tags(payload: dict[str, Any]) -> list[str]:
    categories = payload.get("categories") if isinstance(payload, dict) else None
    if not isinstance(categories, list):
        return []

    tags: list[str] = []
    for item in categories:
        if isinstance(item, str):
            text = item.strip()
            if text:
                tags.append(text)
    return tags


def _to_str(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


def _is_valid_symbol(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{2,15}", symbol))