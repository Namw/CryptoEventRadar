from crypto_market_intel.tools.base import ToolRequest, ToolResult
from crypto_market_intel.tools.registry import ToolRegistry


class DummyMarketTool:
    name = "market_data"
    source = "dummy_market_api"

    def run(self, request: ToolRequest) -> ToolResult:
        symbol = str(request.args.get("symbol") or "").upper()
        if not symbol:
            return ToolResult.failure(
                tool_name=self.name,
                source=self.source,
                code="invalid_symbol",
                message="symbol is required",
            )
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "symbol": symbol,
                "price": 100000.0,
                "change_24h_pct": 1.25,
                "volume_24h": 123456789.0,
                "as_of": "2026-05-17T12:00:00Z",
            },
        )


class BrokenTool:
    name = "broken_tool"
    source = "broken_source"

    def run(self, request: ToolRequest) -> ToolResult:  # pragma: no cover - exception path
        raise RuntimeError("boom")


def test_registry_run_success():
    registry = ToolRegistry()
    registry.register(DummyMarketTool())

    result = registry.run(ToolRequest(tool_name="market_data", args={"symbol": "btc"}))

    assert result.ok is True
    assert result.tool_name == "market_data"
    assert result.source == "dummy_market_api"
    assert result.data["symbol"] == "BTC"
    assert result.error is None
    assert result.latency_ms is not None


def test_registry_rejects_duplicate_registration():
    registry = ToolRegistry()
    registry.register(DummyMarketTool())

    try:
        registry.register(DummyMarketTool())
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "already registered" in str(exc)


def test_registry_returns_error_when_tool_missing():
    registry = ToolRegistry()

    result = registry.run(ToolRequest(tool_name="not_exists", args={}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "tool_not_registered"


def test_registry_wraps_tool_exception():
    registry = ToolRegistry()
    registry.register(BrokenTool())

    result = registry.run(ToolRequest(tool_name="broken_tool", args={}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "tool_execution_error"
    assert "boom" in result.error.message
    assert result.latency_ms is not None
