from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4


_TRACE_ID: ContextVar[str | None] = ContextVar("trace_id", default=None)


def create_trace_id() -> str:
    return uuid4().hex


def set_trace_id(trace_id: str) -> None:
    _TRACE_ID.set(trace_id.strip())


def get_trace_id() -> str:
    current = _TRACE_ID.get()
    if current:
        return current
    trace_id = create_trace_id()
    _TRACE_ID.set(trace_id)
    return trace_id


def emit_structured_log(event: str, **fields: object) -> None:
    payload: dict[str, object] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "trace_id": get_trace_id(),
    }
    payload.update(fields)
    print(json.dumps(payload, ensure_ascii=False), flush=True)
