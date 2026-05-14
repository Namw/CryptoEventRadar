from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class RawSourceRecord:
	source_name: str
	source_record_id: str
	title: str | None
	url: str | None
	published_at: datetime | None
	raw_payload: dict[str, Any]
