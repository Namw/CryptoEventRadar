from __future__ import annotations

from time import perf_counter

from crypto_market_intel.tools.base import Tool, ToolRequest, ToolResult


class ToolRegistry:
    """注册并调度工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def get(self, tool_name: str) -> Tool | None:
        return self._tools.get(tool_name)

    def run(self, request: ToolRequest) -> ToolResult:
        tool = self.get(request.tool_name)
        if tool is None:
            return ToolResult.failure(
                tool_name=request.tool_name,
                source="tool_registry",
                code="tool_not_registered",
                message=f"Tool not found: {request.tool_name}",
            )

        started = perf_counter()
        try:
            result = tool.run(request)
            elapsed_ms = int((perf_counter() - started) * 1000)
            if result.latency_ms is None:
                return ToolResult(
                    ok=result.ok,
                    tool_name=result.tool_name,
                    source=result.source,
                    data=result.data,
                    error=result.error,
                    latency_ms=elapsed_ms,
                )
            return result
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return ToolResult.failure(
                tool_name=request.tool_name,
                source=getattr(tool, "source", "unknown"),
                code="tool_execution_error",
                message=str(exc),
                retryable=False,
                latency_ms=elapsed_ms,
            )
