from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select

from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base, Event
from crypto_market_intel.schemas.report import DailyReport


def run_publish(limit: int = 30, reports_dir: str = "reports", translate_to_zh: bool = False) -> dict[str, str | int | bool]:
	engine = create_db_engine(get_database_url())
	Base.metadata.create_all(engine)
	session_factory = create_session_factory(engine)
	return _publish_with_session_factory(
		session_factory,
		limit=limit,
		reports_dir=reports_dir,
		translate_to_zh=translate_to_zh,
	)


def _publish_with_session_factory(
	session_factory,
	limit: int = 30,
	reports_dir: str = "reports",
	translate_to_zh: bool = False,
) -> dict[str, str | int | bool]:
	with session_factory() as session:
		stmt = (
			select(Event)
			.where(Event.status == "analyzed")
			.order_by(Event.importance_score.desc(), Event.event_time.desc(), Event.id.desc())
			.limit(max(1, limit))
		)
		events = list(session.scalars(stmt).all())

	translator, translator_reason = _build_card_translator(translate_to_zh=translate_to_zh)
	report, translated_cards, translation_fallback_cards = _build_daily_report(
		events,
		card_translator=translator,
	)
	report_path = _write_report(report, reports_dir=reports_dir)
	return {
		"events": len(events),
		"report_path": str(report_path),
		"report_title": report.title,
		"translate_to_zh": translate_to_zh,
		"translated_cards": translated_cards,
		"translation_fallback_cards": translation_fallback_cards,
		"translation_reason": translator_reason or "ok",
	}


def _build_daily_report(
	events: list[Event],
	card_translator: Callable[[str, str, str], tuple[str, str, str] | None] | None,
) -> tuple[DailyReport, int, int]:
	now_local = datetime.now().astimezone()
	report_date = now_local.strftime("%Y-%m-%d")
	title = f"Crypto Market Daily Report - {report_date}"

	header_lines = [
		f"# {title}",
		"",
		f"生成时间：{now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}",
		f"事件总数：{len(events)}",
		"",
	]

	if not events:
		header_lines.extend(
			[
				"## 今日暂无已分析事件",
				"",
				"建议先执行 ingest -> normalize -> analyze 后再发布日报。",
			]
		)
		return DailyReport(report_date=report_date, title=title, content_markdown="\n".join(header_lines)), 0, 0

	body_lines = ["## 重点事件卡片", ""]
	translated_cards = 0
	translation_fallback_cards = 0
	for index, event in enumerate(events, start=1):
		card_lines, translated = _format_event_card(index=index, event=event, card_translator=card_translator)
		body_lines.extend(card_lines)
		if translated:
			translated_cards += 1
		else:
			translation_fallback_cards += 1

	content_markdown = "\n".join(header_lines + body_lines)
	return (
		DailyReport(report_date=report_date, title=title, content_markdown=content_markdown),
		translated_cards,
		translation_fallback_cards,
	)


def _format_event_card(
	*,
	index: int,
	event: Event,
	card_translator: Callable[[str, str, str], tuple[str, str, str] | None] | None,
) -> tuple[list[str], bool]:
	assets = _parse_assets(event.assets_json)
	assets_text = "、".join(assets) if assets else "未识别"
	event_time_text = _format_event_time(event.event_time)
	importance_score = f"{event.importance_score:.2f}"
	title = (event.title or "未命名事件").strip()
	summary = (event.summary or "暂无摘要").strip()
	importance_reason = (event.importance_reason or "暂无重要度说明").strip()
	source_url = (event.source_url or "").strip()
	translated = False

	if card_translator is not None:
		translated_triplet = card_translator(title, summary, importance_reason)
		if translated_triplet is not None:
			title, summary, importance_reason = translated_triplet
			translated = True

	source_credibility = f"{event.source_credibility:.2f}" if hasattr(event, "source_credibility") and event.source_credibility is not None else "N/A"
	lines = [
		f"### {index}. {title}",
		f"- 类型：{event.event_type}",
		f"- 来源：{event.source}（可信度 {source_credibility}）",
		f"- 时间：{event_time_text}",
		f"- 资产：{assets_text}",
		f"- 重要度：{importance_score}",
		f"- 摘要：{summary}",
		f"- 说明：{importance_reason}",
	]
	if source_url:
		lines.append(f"- 链接：{source_url}")
	lines.append("")
	return lines, translated


def _build_card_translator(
	*, translate_to_zh: bool
) -> tuple[Callable[[str, str, str], tuple[str, str, str] | None] | None, str | None]:
	if not translate_to_zh:
		return None, "translation_disabled"

	api_key = os.getenv("OPENAI_API_KEY", "").strip()
	model = os.getenv("OPENAI_MODEL", "").strip()
	if not api_key or not model:
		return None, "llm_not_configured"

	base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
	raw_timeout = os.getenv("OPENAI_TIMEOUT_SECONDS", "20").strip()
	try:
		timeout_seconds = float(raw_timeout)
	except ValueError:
		timeout_seconds = 20.0

	llm = ChatOpenAI(
		model=model,
		api_key=api_key,
		base_url=base_url,
		temperature=0,
		timeout=max(5.0, timeout_seconds),
	)

	def translate_card(title: str, summary: str, importance_reason: str) -> tuple[str, str, str] | None:
		payload = {
			"title": title,
			"summary": summary,
			"importance_reason": importance_reason,
		}
		prompt = (
			"请将输入 JSON 中的 title、summary、importance_reason 翻译为简体中文。"
			"保留币种符号、数字、专有名词和链接，不要增加解释。仅返回 JSON。"
		)
		try:
			response = llm.invoke(
				[
					SystemMessage(content="你是金融科技文案翻译助手。"),
					HumanMessage(content=prompt + "\n" + json.dumps(payload, ensure_ascii=False)),
				]
			)
			content = _extract_langchain_content(response.content)
			if not content:
				return None
			parsed = _parse_translation_json(content)
			if parsed is None:
				return None
			translated_title = str(parsed.get("title") or "").strip() or title
			translated_summary = str(parsed.get("summary") or "").strip() or summary
			translated_reason = str(parsed.get("importance_reason") or "").strip() or importance_reason
			return translated_title, translated_summary, translated_reason
		except Exception:
			return None

	return translate_card, "ok"


def _extract_langchain_content(content: object) -> str | None:
	if isinstance(content, str):
		return content.strip()
	if isinstance(content, list):
		parts: list[str] = []
		for item in content:
			if isinstance(item, dict):
				text_value = item.get("text")
				if isinstance(text_value, str) and text_value.strip():
					parts.append(text_value.strip())
			elif isinstance(item, str) and item.strip():
				parts.append(item.strip())
		if parts:
			return "\n".join(parts)
	return None


def _parse_translation_json(content: str) -> dict[str, object] | None:
	try:
		parsed = json.loads(content)
		if isinstance(parsed, dict):
			return parsed
		return None
	except json.JSONDecodeError:
		cleaned = content.replace("```json", "").replace("```", "").strip()
		try:
			parsed = json.loads(cleaned)
			if isinstance(parsed, dict):
				return parsed
			return None
		except json.JSONDecodeError:
			return None


def _parse_assets(raw_assets: str) -> list[str]:
	try:
		assets = json.loads(raw_assets)
		if isinstance(assets, list):
			return [str(asset).strip().upper() for asset in assets if str(asset).strip()]
		return []
	except json.JSONDecodeError:
		return []


def _format_event_time(event_time: datetime | None) -> str:
	if event_time is None:
		return "未知"
	if event_time.tzinfo is None:
		return event_time.strftime("%Y-%m-%d %H:%M:%S")
	local_time = event_time.astimezone()
	return local_time.strftime("%Y-%m-%d %H:%M:%S %Z")


def _write_report(report: DailyReport, reports_dir: str) -> Path:
	output_dir = Path(reports_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
	filename = f"daily-report-{report.report_date}-{timestamp}.md"
	report_path = output_dir / filename
	report_path.write_text(report.content_markdown, encoding="utf-8")
	return report_path
