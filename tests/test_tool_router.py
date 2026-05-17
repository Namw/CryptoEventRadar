from crypto_market_intel.agents.tool_router import answer_question, plan_tools_for_question
from crypto_market_intel.tools.base import ToolRequest, ToolResult
from crypto_market_intel.tools.registry import ToolRegistry


class DummyMarketTool:
    name = "market_data"
    source = "dummy_market"

    def run(self, request: ToolRequest) -> ToolResult:
        symbol = str(request.args.get("symbol") or "BTC").upper()
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "symbol": symbol,
                "price": 70000.0,
                "change_24h_pct": 2.1,
                "source": self.source,
            },
        )


class DummyExchangeTool:
    name = "exchange_info"
    source = "dummy_exchange"

    def run(self, request: ToolRequest) -> ToolResult:
        symbol = str(request.args.get("symbol") or "BTC").upper()
        exchange = str(request.args.get("exchange") or "binance")
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "exchange": exchange,
                "symbol": symbol,
                "tradable": True,
                "status": "TRADING",
                "source": self.source,
            },
        )


class DummyProjectTool:
    name = "project_info"
    source = "dummy_project"

    def run(self, request: ToolRequest) -> ToolResult:
        symbol = str(request.args.get("symbol") or "BTC").upper()
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "symbol": symbol,
                "project_name": "Bitcoin",
                "chain": "bitcoin",
                "tags": ["Payments"],
                "source": self.source,
            },
        )


class DummyHistoryTool:
    name = "history_lookup"
    source = "dummy_history"

    def run(self, request: ToolRequest) -> ToolResult:
        symbol = str(request.args.get("symbol") or "BTC").upper()
        days = int(request.args.get("days") or 7)
        return ToolResult.success(
            tool_name=self.name,
            source=self.source,
            data={
                "query": {"symbol": symbol, "days": days},
                "total": 2,
                "events": [
                    {
                        "event_id": "event-1",
                        "event_time": "2026-05-16T10:00:00+00:00",
                        "event_type": "listing",
                        "importance_score": 0.9,
                    }
                ],
                "source": self.source,
            },
        )


def _build_dummy_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(DummyMarketTool())
    registry.register(DummyExchangeTool())
    registry.register(DummyProjectTool())
    registry.register(DummyHistoryTool())
    return registry


def test_plan_single_tool_market_question():
    plan = plan_tools_for_question("BTC 今天涨跌多少？")
    assert plan.symbol == "BTC"
    assert plan.tools == ["market_data"]


def test_plan_double_tools_listing_after_price_question():
    plan = plan_tools_for_question("BTC 在币安的交易状态和价格表现如何？")
    assert plan.symbol == "BTC"
    assert set(plan.tools) == {"market_data", "exchange_info"}


def test_plan_multi_tools_project_history_exchange_question():
    plan = plan_tools_for_question("给我 BTC 这个项目过去一周的事件和当前交易状态")
    assert plan.symbol == "BTC"
    assert set(plan.tools) == {"project_info", "history_lookup", "exchange_info"}
    assert plan.days == 7


def test_answer_question_includes_tool_sources_and_key_evidence():
    registry = _build_dummy_registry()
    result = answer_question("BTC 在币安交易状态和价格如何", registry=registry)

    assert result["conclusion"].startswith("共调用")
    assert len(result["tool_calls"]) == 2
    for call in result["tool_calls"]:
        assert call["source"].startswith("dummy_")
        assert isinstance(call["key_evidence"], dict)
        assert call["error"] is None


def test_answer_question_supports_five_question_types():
    registry = _build_dummy_registry()
    questions = [
        "BTC 今天涨跌多少",
        "BTC 在币安交易状态和价格如何",
        "BTC 项目官网和标签是什么",
        "BTC 过去7天有什么历史事件",
        "给我 BTC 这个项目过去一周的事件和当前交易状态",
    ]

    results = [answer_question(question, registry=registry) for question in questions]

    assert len(results) == 5
    call_counts = [len(item["tool_calls"]) for item in results]
    assert all(1 <= count <= 3 for count in call_counts)
    assert any(count == 1 for count in call_counts)
    assert any(count == 2 for count in call_counts)
    assert any(count == 3 for count in call_counts)