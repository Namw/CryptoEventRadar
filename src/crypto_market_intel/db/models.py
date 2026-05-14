from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
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
