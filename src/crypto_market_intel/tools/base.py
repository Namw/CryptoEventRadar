from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolRequest:
    """统一的工具请求载体。"""

    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None


@dataclass(frozen=True)
class ToolError:
    """结构化错误，便于 agent 决策是否重试。"""

    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """统一的工具输出结构。"""

    ok: bool
    tool_name: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    error: ToolError | None = None
    latency_ms: int | None = None

    @classmethod
    def success(
        cls,
        *,
        tool_name: str,
        source: str,
        data: dict[str, Any],
        latency_ms: int | None = None,
    ) -> "ToolResult":
        return cls(
            ok=True,
            tool_name=tool_name,
            source=source,
            data=data,
            error=None,
            latency_ms=latency_ms,
        )

    @classmethod
    def failure(
        cls,
        *,
        tool_name: str,
        source: str,
        code: str,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
        latency_ms: int | None = None,
    ) -> "ToolResult":
        return cls(
            ok=False,
            tool_name=tool_name,
            source=source,
            data={},
            error=ToolError(
                code=code,
                message=message,
                retryable=retryable,
                details=details or {},
            ),
            latency_ms=latency_ms,
        )


class Tool(Protocol):
    """工具实现协议。"""

    name: str
    source: str

    def run(self, request: ToolRequest) -> ToolResult:
        ...
