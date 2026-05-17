from __future__ import annotations

import json

from crypto_market_intel.observability import emit_structured_log, set_trace_id


def test_emit_structured_log_contains_trace_id(capsys):
    set_trace_id("trace-test-001")
    emit_structured_log("unit.test", foo="bar")

    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "unit.test"
    assert payload["trace_id"] == "trace-test-001"
    assert payload["foo"] == "bar"
