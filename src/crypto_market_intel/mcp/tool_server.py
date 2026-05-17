from __future__ import annotations

import importlib
from typing import Any

from crypto_market_intel.agents.tool_router import build_default_tool_registry
from crypto_market_intel.tools import ToolRequest


def _create_mcp_server() -> Any:
    try:
        fastmcp_module = importlib.import_module("mcp.server.fastmcp")
    except ImportError as exc:  # pragma: no cover - 依赖缺失时由调用方处理
        raise RuntimeError("mcp_dependency_missing") from exc
    fastmcp_cls = getattr(fastmcp_module, "FastMCP", None)
    if fastmcp_cls is None:
        raise RuntimeError("mcp_fastmcp_api_unavailable")

    mcp = fastmcp_cls("crypto-market-intel-tools")
    registry = build_default_tool_registry()

    @mcp.tool(name="market_data", description="查询资产最新行情，返回价格与24h涨跌")
    def market_data(symbol: str) -> dict[str, Any]:
        return _run_tool(registry=registry, tool_name="market_data", args={"symbol": symbol})

    @mcp.tool(name="exchange_info", description="查询交易所资产可交易状态")
    def exchange_info(exchange: str, symbol: str) -> dict[str, Any]:
        return _run_tool(
            registry=registry,
            tool_name="exchange_info",
            args={"exchange": exchange, "symbol": symbol},
        )

    @mcp.tool(name="project_info", description="查询项目资料，包括官网、链和标签")
    def project_info(symbol: str) -> dict[str, Any]:
        return _run_tool(registry=registry, tool_name="project_info", args={"symbol": symbol})

    @mcp.tool(name="history_lookup", description="查询历史事件，支持symbol+days组合")
    def history_lookup(symbol: str, days: int = 7, event_type: str | None = None, limit: int = 20) -> dict[str, Any]:
        args: dict[str, Any] = {
            "symbol": symbol,
            "days": days,
            "limit": limit,
        }
        if event_type:
            args["event_type"] = event_type
        return _run_tool(registry=registry, tool_name="history_lookup", args=args)

    return mcp


def _run_tool(*, registry: Any, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    result = registry.run(ToolRequest(tool_name=tool_name, args=args))
    return {
        "ok": result.ok,
        "tool_name": result.tool_name,
        "source": result.source,
        "data": result.data,
        "error": {
            "code": result.error.code,
            "message": result.error.message,
            "retryable": result.error.retryable,
            "details": result.error.details,
        }
        if result.error
        else None,
        "latency_ms": result.latency_ms,
    }


def main() -> None:
    mcp = _create_mcp_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
