import crypto_market_intel.agents.tool_router as router


def test_answer_question_supports_rules_backend_explicitly():
    result = router.answer_question("BTC 今天涨跌多少", backend="rules")
    assert result["backend"] == "rules"
    assert result["tool_calls"]


def test_answer_question_langchain_backend_fallbacks_to_rules(monkeypatch):
    def broken_langchain_answer(*args, **kwargs):
        raise RuntimeError("mock_mcp_error")

    monkeypatch.setattr(
        "crypto_market_intel.agents.langchain_mcp_router.answer_question_with_langchain_mcp",
        broken_langchain_answer,
    )

    result = router.answer_question("BTC 在币安交易状态和价格如何", backend="langchain_mcp")

    assert result["backend"] == "rules_fallback"
    assert "mock_mcp_error" in result["backend_error"]
    assert len(result["tool_calls"]) >= 1
