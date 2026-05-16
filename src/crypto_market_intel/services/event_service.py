from __future__ import annotations

import json
from time import perf_counter

from sqlalchemy import inspect, select, text

from crypto_market_intel.agents.event_analyst import analyze_event_with_trace
from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base, Event
from crypto_market_intel.schemas.event import UnifiedEvent


def run_analyze_events(limit: int = 50, verbose: bool = True) -> dict[str, int | float]:
	engine = create_db_engine(get_database_url())
	Base.metadata.create_all(engine)
	_ensure_event_columns(engine)
	session_factory = create_session_factory(engine)
	return _analyze_events_with_session_factory(session_factory, limit=limit, verbose=verbose)


def _ensure_event_columns(engine) -> None:
	inspector = inspect(engine)
	if "events" not in inspector.get_table_names():
		return

	column_names = {column["name"] for column in inspector.get_columns("events")}
	statements: list[str] = []
	if "importance_score" not in column_names:
		statements.append("ALTER TABLE events ADD COLUMN importance_score FLOAT NOT NULL DEFAULT 0.0")
	if "importance_reason" not in column_names:
		statements.append("ALTER TABLE events ADD COLUMN importance_reason TEXT")

	if not statements:
		return

	with engine.begin() as conn:
		for statement in statements:
			conn.execute(text(statement))


def _analyze_events_with_session_factory(session_factory, limit: int = 50, verbose: bool = False) -> dict[str, int | float]:
	started_at = perf_counter()
	with session_factory() as session:
		stmt = (
			select(Event)
			.where(Event.status != "analyzed")
			.order_by(Event.id.asc())
			.limit(max(1, limit))
		)
		events = list(session.scalars(stmt).all())

		if verbose:
			print(f"[analyze] fetched={len(events)} pending events")

		updated = 0
		llm_used = 0
		fallback_rules = 0
		total = len(events)
		for index, event in enumerate(events, start=1):
			unified_event = _event_to_unified_event(event)
			analysis, trace = analyze_event_with_trace(unified_event)
			event.event_type = analysis.event_type
			event.assets_json = json.dumps(analysis.assets, ensure_ascii=False)
			event.summary = analysis.summary
			event.importance_score = analysis.importance_score
			event.importance_reason = analysis.importance_reason
			event.status = analysis.status
			if trace.llm_used:
				llm_used += 1
			else:
				fallback_rules += 1

			if verbose:
				reason = trace.fallback_reason or "ok"
				model = trace.llm_model or "-"
				print(
					f"[analyze] {index}/{total} event_id={event.event_id} "
					f"mode={trace.mode} llm_model={model} reason={reason}"
				)
			updated += 1

		session.commit()

	elapsed_seconds = round(perf_counter() - started_at, 2)

	return {
		"fetched": len(events),
		"inserted": updated,
		"skipped": 0,
		"llm_used": llm_used,
		"fallback_rules": fallback_rules,
		"elapsed_seconds": elapsed_seconds,
	}


def _event_to_unified_event(event: Event) -> UnifiedEvent:
	assets = []
	if event.assets_json:
		try:
			assets = list(json.loads(event.assets_json))
		except json.JSONDecodeError:
			assets = []
	return UnifiedEvent(
		event_id=event.event_id,
		source=event.source,
		source_event_id=event.source_event_id,
		event_type=event.event_type,
		title=event.title,
		source_url=event.source_url,
		assets=assets,
		summary=event.summary,
		raw_text=event.raw_text,
		event_time=event.event_time,
		detected_at=event.detected_at,
		status=event.status,
	)
