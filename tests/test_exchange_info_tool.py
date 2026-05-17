from crypto_market_intel.tools.base import ToolRequest
from crypto_market_intel.tools.exchange_info import ExchangeInfoTool


def test_exchange_info_tool_success():
    def fake_fetcher(exchange: str, pair: str, _timeout: float) -> dict:
        assert exchange == "binance"
        assert pair == "BTCUSDT"
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "isSpotTradingAllowed": True,
                }
            ]
        }

    tool = ExchangeInfoTool(fetcher=fake_fetcher)
    result = tool.run(
        ToolRequest(tool_name="exchange_info", args={"exchange": "binance", "symbol": "btc"})
    )

    assert result.ok is True
    assert result.error is None
    assert result.data["exchange"] == "binance"
    assert result.data["symbol"] == "BTC"
    assert result.data["tradable"] is True
    assert result.data["pairs"] == ["BTCUSDT"]
    assert result.data["status"] == "TRADING"
    assert len(result.data["reference_links"]) >= 1


def test_exchange_info_tool_invalid_symbol():
    tool = ExchangeInfoTool(fetcher=lambda _exchange, _pair, _timeout: {})
    result = tool.run(
        ToolRequest(tool_name="exchange_info", args={"exchange": "binance", "symbol": ""})
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "invalid_symbol"


def test_exchange_info_tool_timeout():
    def timeout_fetcher(_exchange: str, _pair: str, _timeout: float) -> dict:
        raise TimeoutError("request timed out")

    tool = ExchangeInfoTool(fetcher=timeout_fetcher)
    result = tool.run(
        ToolRequest(tool_name="exchange_info", args={"exchange": "binance", "symbol": "BTC"})
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "timeout"
    assert result.error.retryable is True


def test_exchange_info_tool_empty_result():
    tool = ExchangeInfoTool(fetcher=lambda _exchange, _pair, _timeout: {})
    result = tool.run(
        ToolRequest(tool_name="exchange_info", args={"exchange": "binance", "symbol": "BTC"})
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "empty_result"


def test_exchange_info_tool_invalid_exchange():
    tool = ExchangeInfoTool(fetcher=lambda _exchange, _pair, _timeout: {})
    result = tool.run(
        ToolRequest(tool_name="exchange_info", args={"exchange": "kraken", "symbol": "BTC"})
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "invalid_exchange"