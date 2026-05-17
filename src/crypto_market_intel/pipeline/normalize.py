from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base, Event, SourceRecord
from crypto_market_intel.observability import emit_structured_log
from crypto_market_intel.schemas.event import UnifiedEvent


def run_normalize(limit: int = 50) -> dict[str, int]:
	emit_structured_log("pipeline.normalize.start", limit=limit)
	engine = create_db_engine(get_database_url())
	Base.metadata.create_all(engine)
	session_factory = create_session_factory(engine)

	with session_factory() as session:
		stmt = (
			select(SourceRecord)
			.outerjoin(Event, Event.source_record_db_id == SourceRecord.id)
			.where(Event.id.is_(None))
			.order_by(SourceRecord.id.asc())
			.limit(max(1, limit))
		)
		source_records = list(session.scalars(stmt).all())

		inserted = 0
		for source_record in source_records:
			unified_event = normalize_source_record(source_record)
			session.add(
				Event(
					event_id=unified_event.event_id,
					source_record_db_id=source_record.id,
					source=unified_event.source,
					source_event_id=unified_event.source_event_id,
					event_type=unified_event.event_type,
					title=unified_event.title,
					summary=unified_event.summary,
					raw_text=unified_event.raw_text,
					event_time=unified_event.event_time,
					detected_at=unified_event.detected_at,
					source_url=unified_event.source_url,
					assets_json=json.dumps(unified_event.assets, ensure_ascii=False),
					source_credibility=unified_event.source_credibility,
					status=unified_event.status,
				)
			)
			inserted += 1

		session.commit()

	result = {
		"fetched": len(source_records),
		"inserted": inserted,
		"skipped": 0,
	}
	emit_structured_log("pipeline.normalize.done", result=result)
	return result


# 来源可信度静态评级表：基于来源性质的先验经验分，后续可用历史准确率数据校准
_SOURCE_CREDIBILITY: dict[str, float] = {
	"binance_announcements": 0.95,  # 官方交易所一手公告，可信度最高
	"coindesk_news": 0.75,          # 行业主流媒体，二手来源，可信度中等
}
_DEFAULT_SOURCE_CREDIBILITY = 0.6  # 未知来源的默认可信度


def _get_source_credibility(source_name: str) -> float:
	return _SOURCE_CREDIBILITY.get(source_name, _DEFAULT_SOURCE_CREDIBILITY)


def normalize_source_record(record: SourceRecord) -> UnifiedEvent:
	payload = _parse_payload(record.raw_payload)
	title = (record.title or _payload_str(payload, "title") or "Untitled event").strip()
	source_url = record.url or _payload_str(payload, "link") or _payload_str(payload, "url")
	event_time = record.published_at
	event_type = _classify_event_type(record.source_name, title)
	assets = _extract_assets(title)
	source_credibility = _get_source_credibility(record.source_name)

	stable_key = f"{record.source_name}:{record.source_record_id}"
	return UnifiedEvent(
		event_id=str(uuid5(NAMESPACE_URL, stable_key)),
		source=record.source_name,
		source_event_id=record.source_record_id,
		event_type=event_type,
		title=title,
		source_url=source_url,
		assets=assets,
		summary=None,
		raw_text=_payload_str(payload, "description"),
		event_time=event_time,
		detected_at=datetime.now(timezone.utc),
		source_credibility=source_credibility,
		status="new",
	)


def _parse_payload(raw_payload: str) -> dict:
	try:
		payload = json.loads(raw_payload)
		if isinstance(payload, dict):
			return payload
		return {}
	except json.JSONDecodeError:
		return {}


def _payload_str(payload: dict, key: str) -> str | None:
	value = payload.get(key)
	if isinstance(value, str):
		return value
	return None


def _classify_event_type(source: str, title: str) -> str:
	title_lower = title.lower()
	if "delist" in title_lower:
		return "delisting"
	if "list" in title_lower or "listing" in title_lower:
		return "listing"
	if "security" in title_lower or "hack" in title_lower or "exploit" in title_lower:
		return "security"
	if source == "coindesk_news":
		return "project_news"
	return "other"


def _extract_assets(title: str) -> list[str]:
	# Extract potential ticker symbols from titles, such as BTC/ETH/SOL.
	candidates = re.findall(r"\b[A-Z]{2,10}\b", title)
	stopwords = {
		"BINANCE",
		"USD",
		"USDT",
		"NEWS",
		"ETF",
		"API",
	}
	assets: list[str] = []
	for candidate in candidates:
		if candidate in stopwords:
			continue
		if candidate not in assets:
			assets.append(candidate)
	return assets[:8]
