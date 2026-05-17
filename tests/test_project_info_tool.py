from crypto_market_intel.tools.base import ToolRequest
from crypto_market_intel.tools.project_info import ProjectInfoTool


def test_project_info_tool_success():
    def fake_fetcher(symbol: str, _timeout: float) -> dict:
        assert symbol == "BTC"
        return {
            "name": "Bitcoin",
            "links": {"homepage": ["https://bitcoin.org", ""]},
            "asset_platform_id": "bitcoin",
            "categories": ["Payments", "Store of Value"],
        }

    tool = ProjectInfoTool(fetcher=fake_fetcher)
    result = tool.run(ToolRequest(tool_name="project_info", args={"symbol": "btc"}))

    assert result.ok is True
    assert result.error is None
    assert result.data["symbol"] == "BTC"
    assert result.data["project_name"] == "Bitcoin"
    assert result.data["website"] == "https://bitcoin.org"
    assert result.data["chain"] == "bitcoin"
    assert result.data["tags"] == ["Payments", "Store of Value"]


def test_project_info_tool_missing_fields_should_not_fail():
    tool = ProjectInfoTool(fetcher=lambda _symbol, _timeout: {"name": "Unknown"})
    result = tool.run(ToolRequest(tool_name="project_info", args={"symbol": "ABC"}))

    assert result.ok is True
    assert result.error is None
    assert result.data["project_name"] == "Unknown"
    assert result.data["website"] is None
    assert result.data["chain"] is None
    assert result.data["tags"] == []


def test_project_info_tool_invalid_symbol():
    tool = ProjectInfoTool(fetcher=lambda _symbol, _timeout: {})
    result = tool.run(ToolRequest(tool_name="project_info", args={"symbol": ""}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "invalid_symbol"


def test_project_info_tool_timeout():
    def timeout_fetcher(_symbol: str, _timeout: float) -> dict:
        raise TimeoutError("request timed out")

    tool = ProjectInfoTool(fetcher=timeout_fetcher)
    result = tool.run(ToolRequest(tool_name="project_info", args={"symbol": "BTC"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "timeout"
    assert result.error.retryable is True


def test_project_info_tool_empty_result():
    tool = ProjectInfoTool(fetcher=lambda _symbol, _timeout: {})
    result = tool.run(ToolRequest(tool_name="project_info", args={"symbol": "BTC"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "empty_result"