from __future__ import annotations

import asyncio
import importlib
import os
import sys
from typing import Any, Callable, cast

from pydantic import SecretStr


def answer_question_with_langchain_mcp(
    question: str,
    *,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """使用 LangChain Agent + MCP 工具完成问答。"""

    return asyncio.run(_answer_question_with_langchain_mcp_async(question=question, trace_id=trace_id))


async def _answer_question_with_langchain_mcp_async(
    question: str,
    *,
    trace_id: str | None = None,
) -> dict[str, Any]:
    try:
        agents_module = importlib.import_module("langchain.agents")
        adapters_module = importlib.import_module("langchain_mcp_adapters.client")
        openai_module = importlib.import_module("langchain_openai")
        langgraph_prebuilt_module = importlib.import_module("langgraph.prebuilt")
    except ImportError as exc:  # pragma: no cover - 依赖缺失时走调用方回退
        raise RuntimeError("langchain_mcp_dependencies_missing") from exc

    # 兼容两类 LangChain API：
    # 1) 旧版：AgentExecutor + create_tool_calling_agent
    # 2) 新版：langgraph.prebuilt.create_react_agent
    agent_executor_cls_obj = getattr(agents_module, "AgentExecutor", None)
    create_tool_calling_agent_obj = getattr(agents_module, "create_tool_calling_agent", None)
    create_react_agent_obj = getattr(langgraph_prebuilt_module, "create_react_agent", None)
    multi_server_client_cls_obj = getattr(adapters_module, "MultiServerMCPClient", None)
    chat_openai_cls_obj = getattr(openai_module, "ChatOpenAI", None)

    has_legacy_agent_api = bool(agent_executor_cls_obj and create_tool_calling_agent_obj)
    has_langgraph_agent_api = bool(create_react_agent_obj)
    if not all([multi_server_client_cls_obj, chat_openai_cls_obj]) or not (
        has_legacy_agent_api or has_langgraph_agent_api
    ):
        raise RuntimeError("langchain_mcp_api_unavailable")

    agent_executor_cls = cast(type[Any], agent_executor_cls_obj)
    create_tool_calling_agent = cast(Callable[..., Any], create_tool_calling_agent_obj)
    create_react_agent = cast(Callable[..., Any], create_react_agent_obj)
    multi_server_client_cls = cast(type[Any], multi_server_client_cls_obj)
    chat_openai_cls = cast(type[Any], chat_openai_cls_obj)

    model = os.getenv("OPENAI_MODEL", "").strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
    timeout_seconds = _load_timeout_seconds()
    if not model or not api_key:
        raise RuntimeError("llm_not_configured")

    client = multi_server_client_cls(
        {
            "crypto_tools": {
                "command": sys.executable,
                "args": ["-m", "crypto_market_intel.mcp.tool_server"],
                "transport": "stdio",
            }
        }
    )
    tools = await client.get_tools()
    if not tools:
        raise RuntimeError("mcp_tools_unavailable")

    llm = chat_openai_cls(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        timeout=timeout_seconds,
        temperature=0,
    )

    if has_langgraph_agent_api:
        # LangChain 1.x 主路径：使用 langgraph 预构建 ReAct agent。
        app = create_react_agent(
            llm,
            tools,
            prompt=(
                "你是加密市场研究助手。请根据用户问题自主选择工具并输出结论。"
                "回答必须简洁，并优先引用工具返回证据。"
            ),
        )
        result = await app.ainvoke({"messages": [{"role": "user", "content": question}]})
        tool_calls = _extract_tool_calls_from_langgraph_result(result)
        conclusion = _extract_conclusion_from_langgraph_result(result)
    else:
        # 兼容旧 API，便于在老版本环境中运行。
        prompts_module = importlib.import_module("langchain_core.prompts")
        chat_prompt_template_cls_obj = getattr(prompts_module, "ChatPromptTemplate", None)
        if chat_prompt_template_cls_obj is None:
            raise RuntimeError("langchain_prompt_api_unavailable")
        chat_prompt_template_cls = cast(type[Any], chat_prompt_template_cls_obj)
        prompt = chat_prompt_template_cls.from_messages(
            [
                (
                    "system",
                    "你是加密市场研究助手。请根据用户问题自主选择工具并输出结论。"
                    "回答必须简洁，并优先引用工具返回证据。",
                ),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )
        agent = create_tool_calling_agent(llm, tools, prompt)
        executor = agent_executor_cls(
            agent=agent,
            tools=tools,
            verbose=False,
            return_intermediate_steps=True,
        )
        legacy_result = await executor.ainvoke({"input": question})
        steps = legacy_result.get("intermediate_steps") or []
        tool_calls = [_step_to_tool_call(item) for item in steps]
        conclusion = str(legacy_result.get("output") or "").strip()

    planned_tools = [call["tool_name"] for call in tool_calls]

    return {
        "question": question,
        "backend": "langchain_mcp",
        "trace_id": trace_id,
        "route": {
            "planned_tools": planned_tools,
        },
        "tool_calls": tool_calls,
        "conclusion": conclusion or "已完成工具调用并生成结论。",
    }


def _step_to_tool_call(step: Any) -> dict[str, Any]:
    action: Any
    observation: Any
    if isinstance(step, tuple) and len(step) == 2:
        action, observation = step
    else:
        action = None
        observation = step

    tool_name = getattr(action, "tool", "unknown_tool")
    payload = observation if isinstance(observation, dict) else {"raw_observation": str(observation)}

    if isinstance(payload.get("data"), dict):
        key_evidence = payload["data"]
    else:
        key_evidence = payload

    ok = bool(payload.get("ok", True))
    return {
        "tool_name": tool_name,
        "ok": ok,
        "source": str(payload.get("source") or "mcp_tool"),
        "latency_ms": payload.get("latency_ms"),
        "key_evidence": key_evidence,
        "error": payload.get("error"),
    }


def _extract_tool_calls_from_langgraph_result(result: Any) -> list[dict[str, Any]]:
    messages = _extract_messages(result)
    tool_calls: list[dict[str, Any]] = []
    for message in messages:
        message_type = str(getattr(message, "type", "") or "")
        if message_type != "tool":
            continue
        name = str(getattr(message, "name", "unknown_tool") or "unknown_tool")
        content = getattr(message, "content", None)
        payload = _to_payload(content)
        ok = bool(payload.get("ok", True)) if isinstance(payload, dict) else True
        key_evidence = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        error = payload.get("error") if isinstance(payload, dict) else None
        tool_calls.append(
            {
                "tool_name": name,
                "ok": ok,
                "source": str(payload.get("source") if isinstance(payload, dict) else "mcp_tool"),
                "latency_ms": payload.get("latency_ms") if isinstance(payload, dict) else None,
                "key_evidence": key_evidence if isinstance(key_evidence, dict) else {"raw": key_evidence},
                "error": error,
            }
        )
    return tool_calls


def _extract_conclusion_from_langgraph_result(result: Any) -> str:
    messages = _extract_messages(result)
    for message in reversed(messages):
        message_type = str(getattr(message, "type", "") or "")
        if message_type != "ai":
            continue
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        parts.append(text_value.strip())
            if parts:
                return "\n".join(parts)
    return ""


def _extract_messages(result: Any) -> list[Any]:
    if not isinstance(result, dict):
        return []
    messages = result.get("messages")
    if isinstance(messages, list):
        return messages
    return []


def _to_payload(content: Any) -> Any:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        text = content.strip()
        if not text:
            return {}
        try:
            import json

            parsed = json.loads(text)
            return parsed
        except Exception:
            return {"raw": text}
    if isinstance(content, list):
        if len(content) == 1:
            return _to_payload(content[0])
        return {"raw": str(content)}
    return {"raw": str(content)}


def _load_timeout_seconds() -> float:
    raw_timeout = os.getenv("OPENAI_TIMEOUT_SECONDS", "20").strip()
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError:
        timeout_seconds = 20.0
    return max(5.0, timeout_seconds)
