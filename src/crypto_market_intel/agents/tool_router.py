from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from crypto_market_intel.tools import (
    ExchangeInfoTool,
    HistoryLookupTool,
    MarketDataTool,
    ProjectInfoTool,
    ToolRegistry,
    ToolRequest,
)


@dataclass(frozen=True)
class RoutePlan:
    symbol: str | None
    exchange: str
    days: int
    event_type: str | None
    tools: list[str]


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(MarketDataTool())
    registry.register(ExchangeInfoTool())
    registry.register(ProjectInfoTool())
    registry.register(HistoryLookupTool())
    return registry


def answer_question(
    question: str,
    *,
    registry: ToolRegistry | None = None,
    trace_id: str | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    selected_backend = _resolve_backend(backend)
    if selected_backend == "langchain_mcp":
        try:
            from crypto_market_intel.agents.langchain_mcp_router import answer_question_with_langchain_mcp

            return answer_question_with_langchain_mcp(question=question, trace_id=trace_id)
        except Exception as exc:
            fallback_result = _answer_question_with_rules(
                question=question,
                registry=registry,
                trace_id=trace_id,
            )
            fallback_result["backend"] = "rules_fallback"
            fallback_result["backend_error"] = str(exc)
            return fallback_result

    result = _answer_question_with_rules(question=question, registry=registry, trace_id=trace_id)
    result["backend"] = "rules"
    return result


def _answer_question_with_rules(
    question: str,
    *,
    registry: ToolRegistry | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    tool_registry = registry or build_default_tool_registry()
    plan = plan_tools_for_question(question)
    if not plan.tools:
        return {
            "question": question,
            "route": _plan_to_dict(plan),
            "tool_calls": [],
            "conclusion": "未识别出明确工具需求，请补充资产符号或分析目标。",
        }

    tool_calls: list[dict[str, Any]] = []
    for tool_name in plan.tools:
        args = _build_tool_args(tool_name, plan)
        result = tool_registry.run(ToolRequest(tool_name=tool_name, args=args, trace_id=trace_id))
        tool_calls.append(
            {
                "tool_name": tool_name,
                "ok": result.ok,
                "source": result.source,
                "latency_ms": result.latency_ms,
                "key_evidence": _extract_key_evidence(tool_name, result.data),
                "error": {
                    "code": result.error.code,
                    "message": result.error.message,
                    "retryable": result.error.retryable,
                }
                if result.error
                else None,
            }
        )

    return {
        "question": question,
        "route": _plan_to_dict(plan),
        "tool_calls": tool_calls,
        "conclusion": _build_conclusion(tool_calls),
    }


def _resolve_backend(backend: str | None) -> str:
    explicit = (backend or "").strip().lower()
    if explicit in {"rules", "langchain_mcp"}:
        return explicit
    env_backend = os.getenv("TOOL_ROUTER_BACKEND", "").strip().lower()
    if env_backend in {"rules", "langchain_mcp"}:
        return env_backend
    return "rules"


def plan_tools_for_question(question: str) -> RoutePlan:
    text = (question or "").strip()
    lowered = text.lower()
    symbol = _extract_symbol(text)
    exchange = _extract_exchange(lowered)
    days = _extract_days(text)
    event_type = _extract_event_type(text)

    needs_market = _contains_any(text, ["涨跌", "价格", "行情", "price", "market"]) 
    needs_exchange = _contains_any(text, ["可交易", "交易状态", "交易对", "上币", "上线", "exchange", "listing status"])
    needs_project = _contains_any(text, ["项目", "官网", "资料", "属于什么链", "标签", "project", "website", "chain"])
    needs_history = _contains_any(text, ["历史", "过去", "最近", "一周", "事件", "history"])

    tools: list[str] = []
    if needs_market:
        tools.append("market_data")
    if needs_exchange:
        tools.append("exchange_info")
    if needs_project:
        tools.append("project_info")
    if needs_history:
        tools.append("history_lookup")

    if symbol and not tools:
        tools = ["market_data"]

    return RoutePlan(
        symbol=symbol,
        exchange=exchange,
        days=days,
        event_type=event_type,
        tools=_dedupe(tools)[:3],
    )


def _build_tool_args(tool_name: str, plan: RoutePlan) -> dict[str, Any]:
    symbol = plan.symbol or "BTC"
    if tool_name == "market_data":
        return {"symbol": symbol}
    if tool_name == "exchange_info":
        return {"exchange": plan.exchange, "symbol": symbol}
    if tool_name == "project_info":
        return {"symbol": symbol}
    if tool_name == "history_lookup":
        args: dict[str, Any] = {"symbol": symbol, "days": plan.days}
        if plan.event_type:
            args["event_type"] = plan.event_type
        return args
    return {}


def _extract_key_evidence(tool_name: str, data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return {}
    if tool_name == "market_data":
        return {
            "symbol": data.get("symbol"),
            "price": data.get("price"),
            "change_24h_pct": data.get("change_24h_pct"),
            "source": data.get("source"),
        }
    if tool_name == "exchange_info":
        return {
            "exchange": data.get("exchange"),
            "symbol": data.get("symbol"),
            "tradable": data.get("tradable"),
            "status": data.get("status"),
            "source": data.get("source"),
        }
    if tool_name == "project_info":
        return {
            "symbol": data.get("symbol"),
            "project_name": data.get("project_name"),
            "chain": data.get("chain"),
            "tags": data.get("tags"),
            "source": data.get("source"),
        }
    if tool_name == "history_lookup":
        return {
            "query": data.get("query"),
            "total": data.get("total"),
            "events": data.get("events"),
            "source": data.get("source"),
        }
    return data


def _build_conclusion(tool_calls: list[dict[str, Any]]) -> str:
    if not tool_calls:
        return "未触发工具调用。"

    success_calls = [item for item in tool_calls if item.get("ok")]
    failed_calls = [item for item in tool_calls if not item.get("ok")]
    if not success_calls:
        return "工具调用均失败，建议检查 symbol 或网络状态后重试。"
    if not failed_calls:
        return f"共调用 {len(tool_calls)} 个工具，全部成功并返回关键证据。"
    return f"共调用 {len(tool_calls)} 个工具，成功 {len(success_calls)} 个，失败 {len(failed_calls)} 个。"


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _extract_symbol(text: str) -> str | None:
    matches = re.findall(r"\b[A-Z]{2,10}\b", text.upper())
    if not matches:
        return None
    stop_words = {"AND", "OR", "THE", "WHAT", "WITH", "THIS", "THAT", "HOW", "USD", "USDT"}
    for symbol in matches:
        if symbol not in stop_words:
            return symbol
    return None


def _extract_exchange(lowered_text: str) -> str:
    if "binance" in lowered_text or "币安" in lowered_text:
        return "binance"
    return "binance"


def _extract_days(text: str) -> int:
    for pattern in [r"过去\s*(\d+)\s*天", r"最近\s*(\d+)\s*天", r"(\d+)\s*天"]:
        matched = re.search(pattern, text)
        if matched:
            try:
                value = int(matched.group(1))
            except ValueError:
                continue
            return max(1, value)
    if "一周" in text:
        return 7
    return 7


def _extract_event_type(text: str) -> str | None:
    lowered = text.lower()
    if "上币" in text or "上线" in text or "listing" in lowered:
        return "listing"
    if "下架" in text or "delisting" in lowered:
        return "delisting"
    if "安全" in text or "攻击" in text or "security" in lowered:
        return "security"
    return None


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _plan_to_dict(plan: RoutePlan) -> dict[str, Any]:
    return {
        "symbol": plan.symbol,
        "exchange": plan.exchange,
        "days": plan.days,
        "event_type": plan.event_type,
        "planned_tools": plan.tools,
    }