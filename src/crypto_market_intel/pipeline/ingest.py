from __future__ import annotations

import json
from datetime import datetime, timezone

from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base
from crypto_market_intel.db.repo import upsert_source_record
from crypto_market_intel.sources.binance_announcements import compute_content_hash, fetch_binance_announcements


def run_binance_ingest(limit: int = 20) -> dict[str, int]:
	records = fetch_binance_announcements(limit=limit)

	engine = create_db_engine(get_database_url())
	Base.metadata.create_all(engine)
	session_factory = create_session_factory(engine)

	inserted = 0
	skipped = 0

	with session_factory() as session:
		for record in records:
			raw_payload_json = json.dumps(record.raw_payload, ensure_ascii=False, sort_keys=True)
			_, created = upsert_source_record(
				session,
				source_name=record.source_name,
				source_record_id=record.source_record_id,
				title=record.title,
				url=record.url,
				published_at=record.published_at,
				raw_payload=raw_payload_json,
				content_hash=compute_content_hash(record.raw_payload),
				fetched_at=datetime.now(timezone.utc),
			)
			if created:
				inserted += 1
			else:
				skipped += 1
		session.commit()

	return {
		"fetched": len(records),
		"inserted": inserted,
		"skipped": skipped,
	}
