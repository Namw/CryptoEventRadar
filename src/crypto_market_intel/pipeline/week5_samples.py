from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base, Event
from crypto_market_intel.observability import emit_structured_log


def run_collect_historical_samples(
    *,
    sample_size: int = 40,
    output_dir: str = "data/processed",
    seed: int = 42,
    analyzed_only: bool = True,
) -> dict[str, str | int | bool]:
    """Collect Week5 historical event samples for manual labeling.

    The output is a JSONL file that can be used as the raw labeling set.
    """
    target_size = max(1, sample_size)
    emit_structured_log(
        "pipeline.week5_samples.start",
        sample_size=target_size,
        output_dir=output_dir,
        seed=seed,
        analyzed_only=analyzed_only,
    )

    engine = create_db_engine(get_database_url())
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stmt = select(Event).order_by(Event.id.asc())
        if analyzed_only:
            stmt = stmt.where(Event.status == "analyzed")
        rows = list(session.scalars(stmt).all())

    total_candidates = len(rows)
    if total_candidates == 0:
        report = _write_empty_placeholder(output_dir=output_dir)
        result = {
            "requested": target_size,
            "collected": 0,
            "total_candidates": 0,
            "seed": seed,
            "analyzed_only": analyzed_only,
            "output_path": str(report),
            "warning": "no_candidates",
        }
        emit_structured_log("pipeline.week5_samples.done", result=result)
        return result

    rng = random.Random(seed)
    chosen_size = min(target_size, total_candidates)
    sampled = rng.sample(rows, chosen_size)
    sampled.sort(key=lambda item: item.id)

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    output_path = Path(output_dir) / f"week5-historical-samples-{timestamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for index, event in enumerate(sampled, start=1):
            record = {
                "sample_id": f"S{index:03d}",
                "event_id": event.event_id,
                "source": event.source,
                "source_event_id": event.source_event_id,
                "event_type": event.event_type,
                "title": event.title,
                "summary": event.summary,
                "importance_score": float(event.importance_score),
                "importance_reason": event.importance_reason,
                "source_credibility": float(event.source_credibility),
                "assets": _parse_assets(event.assets_json),
                "source_url": event.source_url,
                "event_time": _to_iso(event.event_time),
                "detected_at": _to_iso(event.detected_at),
                "status": event.status,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    warning = "insufficient_candidates" if total_candidates < target_size else ""
    result = {
        "requested": target_size,
        "collected": chosen_size,
        "total_candidates": total_candidates,
        "seed": seed,
        "analyzed_only": analyzed_only,
        "output_path": str(output_path),
        "warning": warning,
    }
    emit_structured_log("pipeline.week5_samples.done", result=result)
    return result


def _parse_assets(raw_assets: str) -> list[str]:
    try:
        parsed = json.loads(raw_assets)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    assets: list[str] = []
    for item in parsed:
        text = str(item).strip().upper()
        if text:
            assets.append(text)
    return assets


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


def _write_empty_placeholder(*, output_dir: str) -> Path:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    output_path = Path(output_dir) / f"week5-historical-samples-{timestamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("", encoding="utf-8")
    return output_path
