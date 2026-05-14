from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Protocol


@dataclass(slots=True)
class RawSourceRecord:
	source_name: str
	source_record_id: str
	title: str | None
	url: str | None
	published_at: datetime | None
	raw_payload: dict[str, Any]


class SourceFetcher(Protocol):
	def __call__(self, limit: int = 20) -> list[RawSourceRecord]:
		...


def compute_content_hash(payload: dict[str, Any]) -> str:
	canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
	return sha256(canonical.encode("utf-8")).hexdigest()
