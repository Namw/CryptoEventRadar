from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
	return datetime.now(timezone.utc)


class Base(DeclarativeBase):
	pass


class SourceRecord(Base):
	__tablename__ = "source_records"
	__table_args__ = (
		UniqueConstraint("source_name", "source_record_id", name="uq_source_record_source_id"),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True)
	source_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
	source_record_id: Mapped[str] = mapped_column(String(256), nullable=False)
	title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
	url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
	published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
	content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
	fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		default=utc_now,
		onupdate=utc_now,
	)


class Event(Base):
	__tablename__ = "events"
	__table_args__ = (
		UniqueConstraint("event_id", name="uq_events_event_id"),
		UniqueConstraint("source", "source_event_id", name="uq_events_source_source_event_id"),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True)
	event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
	source_record_db_id: Mapped[int] = mapped_column(
		Integer,
		ForeignKey("source_records.id", ondelete="CASCADE"),
		nullable=False,
		unique=True,
	)
	source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
	source_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
	event_type: Mapped[str] = mapped_column(String(64), nullable=False)
	title: Mapped[str] = mapped_column(String(1024), nullable=False)
	summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
	event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
	detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
	source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
	assets_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
	importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
	importance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
	source_credibility: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
	dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)
	cluster_key: Mapped[str | None] = mapped_column(Text, nullable=True)
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		default=utc_now,
		onupdate=utc_now,
	)
