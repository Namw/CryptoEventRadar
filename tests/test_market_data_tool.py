from crypto_market_intel.tools.base import ToolRequest
from crypto_market_intel.tools.market_data import MarketDataTool


def test_market_data_tool_success():
    def fake_fetcher(pair: str, _timeout: float) -> dict:
        assert pair == "BTCUSDT"
        return {
            "lastPrice": "68000.12",
            "priceChangePercent": "2.50",
            "volume": "123456.78",
            "closeTime": 1715900000000,
        }

    tool = MarketDataTool(fetcher=fake_fetcher)
    result = tool.run(ToolRequest(tool_name="market_data", args={"symbol": "btc"}))

    assert result.ok is True
    assert result.error is None
    assert result.data["symbol"] == "BTC"
    assert result.data["pair"] == "BTCUSDT"
    assert result.data["price"] == 68000.12
    assert result.data["change_24h_pct"] == 2.5


def test_market_data_tool_invalid_symbol():
    tool = MarketDataTool(fetcher=lambda _pair, _timeout: {})

    result = tool.run(ToolRequest(tool_name="market_data", args={"symbol": ""}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "invalid_symbol"


def test_market_data_tool_timeout():
    def timeout_fetcher(_pair: str, _timeout: float) -> dict:
        raise TimeoutError("request timed out")

    tool = MarketDataTool(fetcher=timeout_fetcher)
    result = tool.run(ToolRequest(tool_name="market_data", args={"symbol": "BTC"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "timeout"
    assert result.error.retryable is True


def test_market_data_tool_empty_result():
    tool = MarketDataTool(fetcher=lambda _pair, _timeout: {})
    result = tool.run(ToolRequest(tool_name="market_data", args={"symbol": "BTC"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "empty_result"
