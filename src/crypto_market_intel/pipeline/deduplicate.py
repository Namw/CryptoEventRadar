from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

from sqlalchemy import inspect, select, text

from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base, Event


def run_deduplicate(limit: int = 200, verbose: bool = True) -> dict[str, int]:
	engine = create_db_engine(get_database_url())
	Base.metadata.create_all(engine)
	_ensure_event_columns(engine)
	session_factory = create_session_factory(engine)
	return _deduplicate_with_session_factory(session_factory, limit=limit, verbose=verbose)


def _deduplicate_with_session_factory(session_factory, limit: int = 200, verbose: bool = False) -> dict[str, int]:
	with session_factory() as session:
		stmt = (
			select(Event)
			.where(Event.status.in_(["new", "analyzed", "deduplicated"]))
			.order_by(Event.id.asc())
			.limit(max(1, limit))
		)
		events = list(session.scalars(stmt).all())

		strict_clusters: dict[str, list[Event]] = defaultdict(list)
		for event in events:
			dedupe_key = _build_dedupe_key(event)
			event.dedupe_key = dedupe_key
			strict_clusters[dedupe_key].append(event)

		clusters = _merge_fuzzy_clusters(strict_clusters)

		updated = 0
		clustered = 0
		deduplicated = 0
		for group in clusters:
			group_sorted = sorted(group, key=lambda item: item.id)
			canonical = group_sorted[0]
			cluster_key = _build_cluster_key(canonical)
			for event in group_sorted:
				event.cluster_key = cluster_key
				if event.id != canonical.id and event.status != "deduplicated":
					event.status = "deduplicated"
					deduplicated += 1
				updated += 1

			if len(group_sorted) > 1:
				clustered += len(group_sorted)

		session.commit()

	if verbose:
		print(
			"deduplicate complete: "
			f"fetched={len(events)} updated={updated} clustered={clustered} deduplicated={deduplicated}"
		)

	return {
		"fetched": len(events),
		"updated": updated,
		"clustered": clustered,
		"deduplicated": deduplicated,
	}


def _merge_fuzzy_clusters(strict_clusters: dict[str, list[Event]]) -> list[list[Event]]:
	clusters: list[list[Event]] = []
	for _strict_key, strict_group in strict_clusters.items():
		for event in strict_group:
			matched_cluster: list[Event] | None = None
			for cluster in clusters:
				if _is_near_duplicate(event, cluster[0]):
					matched_cluster = cluster
					break
			if matched_cluster is None:
				clusters.append([event])
			else:
				matched_cluster.append(event)
	return clusters


def _is_near_duplicate(left: Event, right: Event) -> bool:
	if _build_dedupe_key(left) == _build_dedupe_key(right):
		return True

	left_event_type = (left.event_type or "").strip().lower()
	right_event_type = (right.event_type or "").strip().lower()
	if left_event_type != right_event_type:
		return False

	if not _assets_compatible(left.assets_json, right.assets_json):
		return False

	if not _time_compatible(left.event_time, right.event_time):
		return False

	left_title = _normalize_title(left.title)
	right_title = _normalize_title(right.title)
	ratio = SequenceMatcher(a=left_title, b=right_title).ratio()
	if ratio >= 0.9:
		return True

	return _token_jaccard(left_title, right_title) >= 0.6


def _assets_compatible(left_raw: str, right_raw: str) -> bool:
	left_assets = set(_normalize_assets(left_raw))
	right_assets = set(_normalize_assets(right_raw))
	if not left_assets or not right_assets:
		return True
	return bool(left_assets & right_assets)


def _time_compatible(left_time: datetime | None, right_time: datetime | None) -> bool:
	if left_time is None or right_time is None:
		return True
	left_ts = left_time.timestamp()
	right_ts = right_time.timestamp()
	return abs(left_ts - right_ts) <= 36 * 3600


def _token_jaccard(left_title: str, right_title: str) -> float:
	left_tokens = {token for token in left_title.split(" ") if token}
	right_tokens = {token for token in right_title.split(" ") if token}
	if not left_tokens and not right_tokens:
		return 1.0
	union = left_tokens | right_tokens
	if not union:
		return 0.0
	return len(left_tokens & right_tokens) / len(union)


def _build_cluster_key(event: Event) -> str:
	base = f"{event.dedupe_key or _build_dedupe_key(event)}|{(event.event_type or 'other').strip().lower()}"
	return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _ensure_event_columns(engine) -> None:
	inspector = inspect(engine)
	if "events" not in inspector.get_table_names():
		return

	column_names = {column["name"] for column in inspector.get_columns("events")}
	statements: list[str] = []
	if "dedupe_key" not in column_names:
		statements.append("ALTER TABLE events ADD COLUMN dedupe_key TEXT")
	if "cluster_key" not in column_names:
		statements.append("ALTER TABLE events ADD COLUMN cluster_key TEXT")

	if not statements:
		return

	with engine.begin() as conn:
		for statement in statements:
			conn.execute(text(statement))


def _build_dedupe_key(event: Event) -> str:
	title = _normalize_title(event.title)
	assets = _normalize_assets(event.assets_json)
	assets_part = ",".join(assets[:4]) if assets else "NA"
	event_type = (event.event_type or "other").strip().lower()
	payload = f"{event_type}|{title}|{assets_part}"
	return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _normalize_title(title: str) -> str:
	lowered = (title or "").strip().lower()
	cleaned = re.sub(r"\s+", " ", lowered)
	return re.sub(r"[^a-z0-9\s]", "", cleaned)


def _normalize_assets(raw_assets: str) -> list[str]:
	try:
		parsed = json.loads(raw_assets)
		if not isinstance(parsed, list):
			return []
		assets = [str(item).strip().upper() for item in parsed if str(item).strip()]
		return sorted(set(assets))
	except json.JSONDecodeError:
		return []