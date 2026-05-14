from datetime import datetime

from pydantic import BaseModel, Field


class UnifiedEvent(BaseModel):
    event_id: str
    source: str
    source_event_id: str
    event_type: str
    title: str
    source_url: str | None = None
    assets: list[str] = Field(default_factory=list)
    summary: str | None = None
    raw_text: str | None = None
    event_time: datetime | None = None
    detected_at: datetime
    status: str = "new"
