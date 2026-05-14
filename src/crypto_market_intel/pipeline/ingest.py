from __future__ import annotations

import json
from datetime import datetime, timezone

from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base
from crypto_market_intel.db.repo import upsert_source_record
from crypto_market_intel.sources.base import SourceFetcher, compute_content_hash
from crypto_market_intel.sources.binance_announcements import fetch_binance_announcements
from crypto_market_intel.sources.coindesk_news import fetch_coindesk_news


SOURCE_FETCHERS: dict[str, SourceFetcher] = {
	"binance_announcements": fetch_binance_announcements,
	"coindesk_news": fetch_coindesk_news,
}


def run_source_ingest(source_name: str, limit: int = 20) -> dict[str, int]:
	fetcher = SOURCE_FETCHERS.get(source_name)
	if fetcher is None:
		supported = ", ".join(sorted(SOURCE_FETCHERS.keys()))
		raise ValueError(f"Unsupported source '{source_name}'. Supported: {supported}")

	records = fetcher(limit=limit)
	return _persist_source_records(records)


def run_binance_ingest(limit: int = 20) -> dict[str, int]:
	return run_source_ingest("binance_announcements", limit=limit)


def run_coindesk_ingest(limit: int = 20) -> dict[str, int]:
	return run_source_ingest("coindesk_news", limit=limit)


def run_all_sources_ingest(limit: int = 20) -> dict[str, dict[str, int]]:
	results: dict[str, dict[str, int]] = {}
	for source_name in sorted(SOURCE_FETCHERS.keys()):
		results[source_name] = run_source_ingest(source_name, limit=limit)
	return results


def _persist_source_records(records) -> dict[str, int]:
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
