from pydantic import BaseModel


class UnifiedEvent(BaseModel):
    event_id: str
    source: str
    source_event_id: str
    event_type: str
    title: str
    summary: str | None = None
    raw_text: str | None = None
    event_time: str | None = None
    detected_at: str | None = None
