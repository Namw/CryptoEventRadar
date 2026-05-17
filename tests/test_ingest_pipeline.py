from urllib.error import URLError
from urllib import request

import crypto_market_intel.pipeline.ingest as ingest
from crypto_market_intel.sources import binance_announcements as binance


class _DummyResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload


def test_run_all_sources_ingest_continues_when_one_source_fails(monkeypatch):
    monkeypatch.setattr(
        ingest,
        "SOURCE_FETCHERS",
        {
            "binance_announcements": lambda limit: [],
            "coindesk_news": lambda limit: [],
        },
    )

    def fake_run_source_ingest(source_name: str, limit: int = 20):
        if source_name == "binance_announcements":
            raise RuntimeError("binance temporary network issue")
        return {"fetched": 3, "inserted": 2, "skipped": 1}

    monkeypatch.setattr(ingest, "run_source_ingest", fake_run_source_ingest)

    result = ingest.run_all_sources_ingest(limit=20)

    assert result["binance_announcements"]["failed"] == 1
    assert result["binance_announcements"]["fetched"] == 0
    assert result["coindesk_news"] == {"fetched": 3, "inserted": 2, "skipped": 1}


def test_read_url_bytes_retries_for_transient_url_error(monkeypatch):
    attempts = {"count": 0}

    def fake_open_url(req: request.Request, timeout: int):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise URLError(OSError("UNEXPECTED_EOF_WHILE_READING"))
        return _DummyResponse(b"ok")

    monkeypatch.setattr(binance, "_open_url", fake_open_url)

    data = binance._read_url_bytes(
        request.Request("https://example.com"),
        timeout=1,
        attempts=2,
        retry_delay_seconds=0,
    )

    assert data == b"ok"
    assert attempts["count"] == 2
