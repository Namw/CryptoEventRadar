from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from crypto_market_intel.db.models import SourceRecord


def upsert_source_record(
	session: Session,
	*,
	source_name: str,
	source_record_id: str,
	title: str | None,
	url: str | None,
	published_at: datetime | None,
	raw_payload: str,
	content_hash: str,
	fetched_at: datetime,
) -> tuple[SourceRecord, bool]:
	existing = (
		session.query(SourceRecord)
		.filter(SourceRecord.source_name == source_name)
		.filter(SourceRecord.source_record_id == source_record_id)
		.one_or_none()
	)
	if existing is not None:
		return existing, False

	record = SourceRecord(
		source_name=source_name,
		source_record_id=source_record_id,
		title=title,
		url=url,
		published_at=published_at,
		raw_payload=raw_payload,
		content_hash=content_hash,
		fetched_at=fetched_at,
	)
	session.add(record)
	session.flush()
	return record, True
