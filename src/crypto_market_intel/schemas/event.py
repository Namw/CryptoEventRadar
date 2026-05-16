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
    source_credibility: float = 0.8
    status: str = "new"


class EventAnalysis(BaseModel):
    event_id: str
    source: str
    source_event_id: str
    event_type: str
    title: str
    summary: str
    assets: list[str] = Field(default_factory=list)
    importance_score: float
    importance_reason: str
    status: str = "analyzed"
