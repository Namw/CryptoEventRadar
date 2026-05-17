from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from sqlalchemy import select

from crypto_market_intel.db.engine import create_db_engine, create_session_factory, get_database_url
from crypto_market_intel.db.models import Base, Event
from crypto_market_intel.observability import emit_structured_log
from crypto_market_intel.schemas.report import AlertReport, DailyReport
from crypto_market_intel.services.alert_service import notify_alert_report


@dataclass(frozen=True)
class ReportCardTranslationItem:
    index: int
    title: str
    summary: str
    importance_reason: str


BatchCardTranslator = Callable[
    [list[ReportCardTranslationItem], Callable[[int, int, list[ReportCardTranslationItem]], None] | None],
    dict[int, tuple[str, str, str]],
]


def run_publish(limit: int = 30, reports_dir: str = "reports", translate_to_zh: bool = False) -> dict[str, str | int | bool]:
    emit_structured_log("pipeline.publish_report.start", limit=limit, reports_dir=reports_dir, translate_to_zh=translate_to_zh)
    engine = create_db_engine(get_database_url())
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    result = _publish_with_session_factory(
        session_factory,
        limit=limit,
        reports_dir=reports_dir,
        translate_to_zh=translate_to_zh,
    )
    emit_structured_log("pipeline.publish_report.done", result=result)
    return result


def run_publish_alerts(
    limit: int = 10,
    reports_dir: str = "reports",
    min_importance: float = 0.8,
    notify: bool = False,
) -> dict[str, str | int | float | bool | list[str] | None]:
    emit_structured_log(
        "pipeline.publish_alerts.start",
        limit=limit,
        reports_dir=reports_dir,
        min_importance=min_importance,
        notify=notify,
    )
    engine = create_db_engine(get_database_url())
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    result = _publish_alerts_with_session_factory(
        session_factory,
        limit=limit,
        reports_dir=reports_dir,
        min_importance=min_importance,
        notify=notify,
    )
    emit_structured_log("pipeline.publish_alerts.done", result=result)
    return result


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
        translation_progress_callback = _build_translation_progress_callback(
            enabled=translate_to_zh and translator is not None,
            total=len(events),
        )
        report, translated_cards, translation_fallback_cards = _build_daily_report(
            events,
            card_translator=translator,
            translation_progress_callback=translation_progress_callback,
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


def _publish_alerts_with_session_factory(
    session_factory,
    limit: int = 10,
    reports_dir: str = "reports",
    min_importance: float = 0.8,
    notify: bool = False,
) -> dict[str, str | int | float | bool | list[str] | None]:
    with session_factory() as session:
        stmt = (
            select(Event)
            .where(Event.status == "analyzed", Event.importance_score >= min_importance)
            .order_by(Event.importance_score.desc(), Event.event_time.desc(), Event.id.desc())
            .limit(max(1, limit))
        )
        events = list(session.scalars(stmt).all())
        alert_report = _build_alert_report(events, min_importance=min_importance)
        report_path = _write_alert_report(alert_report, reports_dir=reports_dir)
        notify_result = None
        if notify:
            notify_result = notify_alert_report(
                report_title=alert_report.title,
                report_path=str(report_path),
                alerts=len(events),
                min_importance=min_importance,
            )
        return {
            "alerts": len(events),
            "report_path": str(report_path),
            "report_title": alert_report.title,
            "min_importance": min_importance,
            "notify_requested": notify,
            "notify_status": None if notify_result is None else notify_result.status,
            "notify_channel": None if notify_result is None else notify_result.channel,
            "notify_sent_channels": [] if notify_result is None else notify_result.sent_channels,
            "notify_errors": [] if notify_result is None else notify_result.errors,
        }


def _build_daily_report(
    events: list[Event],
    card_translator: BatchCardTranslator | None,
    translation_progress_callback: Callable[[int, int, list[ReportCardTranslationItem]], None] | None = None,
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
    translation_items = _build_translation_items(events)
    translations_by_index = _translate_cards(
        items=translation_items,
        card_translator=card_translator,
        translation_progress_callback=translation_progress_callback,
    )
    translated_cards = 0
    translation_fallback_cards = 0
    for index, event in enumerate(events, start=1):
        translated_triplet = translations_by_index.get(index)
        card_lines, translated = _format_event_card(
            index=index,
            event=event,
            translated_triplet=translated_triplet,
        )
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


def _build_alert_report(events: list[Event], *, min_importance: float) -> AlertReport:
    now_local = datetime.now().astimezone()
    report_date = now_local.strftime("%Y-%m-%d")
    title = f"Crypto Market Alerts - {report_date}"

    header_lines = [
        f"# {title}",
        "",
        f"生成时间：{now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"告警阈值：{min_importance:.2f}",
        f"告警事件数：{len(events)}",
        "",
    ]

    if not events:
        header_lines.extend(
            [
                "## 当前无命中告警阈值的事件",
                "",
                "建议继续运行 ingest -> normalize -> analyze，或适当调低告警阈值。",
            ]
        )
        return AlertReport(report_date=report_date, title=title, content_markdown="\n".join(header_lines))

    body_lines = ["## 高优先级事件告警", ""]
    for index, event in enumerate(events, start=1):
        card_lines, _translated = _format_event_card(index=index, event=event)
        body_lines.extend(card_lines)

    content_markdown = "\n".join(header_lines + body_lines)
    return AlertReport(report_date=report_date, title=title, content_markdown=content_markdown)


def _format_event_card(
    *,
    index: int,
    event: Event,
    translated_triplet: tuple[str, str, str] | None = None,
) -> tuple[list[str], bool]:
    assets = _parse_assets(event.assets_json)
    assets_text = "、".join(assets) if assets else "未识别"
    event_time_text = _format_event_time(event.event_time)
    importance_score = f"{event.importance_score:.2f}"
    title = (event.title or "未命名事件").strip()
    summary = (event.summary or "暂无摘要").strip()
    importance_reason = (event.importance_reason or "暂无重要度说明").strip()
    source_url = _normalize_source_url((event.source_url or "").strip())
    translated = translated_triplet is not None

    if translated_triplet is not None:
        title, summary, importance_reason = translated_triplet

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


def _normalize_source_url(url: str) -> str:
    if not url:
        return ""

    matched = re.fullmatch(r"https://www\.binance\.com([0-9a-fA-F]{24,})", url)
    if matched:
        code = matched.group(1)
        return f"https://www.binance.com/en/support/announcement/detail/{code}"

    return url


def _build_card_translator(
    *, translate_to_zh: bool
) -> tuple[BatchCardTranslator | None, str | None]:
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

    batch_size = _load_translation_batch_size()
    batch_timeout = max(60.0, timeout_seconds * batch_size)

    llm = ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=0,
        timeout=batch_timeout,
    )

    def translate_cards(
        items: list[ReportCardTranslationItem],
        progress_callback: Callable[[int, int, list[ReportCardTranslationItem]], None] | None = None,
    ) -> dict[int, tuple[str, str, str]]:
        if not items:
            return {}

        results: dict[int, tuple[str, str, str]] = {}
        batches = [items[start : start + batch_size] for start in range(0, len(items), batch_size)]
        total_batches = len(batches)
        prompt = (
            "请将输入 JSON 中 items 数组里的 title、summary、importance_reason 翻译为简体中文。"
            "必须保留每个条目的 index，不要增加或删除条目，不要改变顺序。"
            "保留币种符号、数字、专有名词和链接，不要增加解释。仅返回 JSON。"
        )

        for batch_index, batch in enumerate(batches, start=1):
            if progress_callback is not None:
                progress_callback(batch_index, total_batches, batch)

            payload = {
                "items": [
                    {
                        "index": item.index,
                        "title": item.title,
                        "summary": item.summary,
                        "importance_reason": item.importance_reason,
                    }
                    for item in batch
                ]
            }

            try:
                response = llm.invoke(
                    [
                        SystemMessage(content="你是金融科技文案翻译助手。"),
                        HumanMessage(content=prompt + "\n" + json.dumps(payload, ensure_ascii=False)),
                    ]
                )
                content = _extract_langchain_content(response.content)
                if not content:
                    _debug_log(f"[translate] 批次 {batch_index}: LLM 返回空内容")
                    continue
                parsed = _parse_batch_translation_json(content)
                if parsed is None:
                    _debug_log(
                        f"[translate] 批次 {batch_index}: JSON 解析失败，原始内容前 300 字符：\n{content[:300]}"
                    )
                    continue
                batch_results = _extract_batch_translation_items(parsed)
                _debug_log(f"[translate] 批次 {batch_index}: 解析到 {len(batch_results)} 条翻译")
            except Exception as exc:
                _debug_log(f"[translate] 批次 {batch_index}: 异常 {exc}")
                continue

            for item in batch:
                translated_triplet = batch_results.get(item.index)
                if translated_triplet is not None:
                    results[item.index] = translated_triplet

        return results

    return translate_cards, "ok"


def _build_translation_progress_callback(
    *,
    enabled: bool,
    total: int,
    batch_size: int | None = None,
) -> Callable[[int, int, list[ReportCardTranslationItem]], None] | None:
    if not enabled or total <= 0:
        return None

    resolved_batch_size = batch_size or _load_translation_batch_size()
    total_batches = (total + resolved_batch_size - 1) // resolved_batch_size

    def report_progress(batch_index: int, _reported_total_batches: int, batch: list[ReportCardTranslationItem]) -> None:
        first_title = batch[0].title if batch else "未命名事件"
        short_title = first_title if len(first_title) <= 60 else f"{first_title[:57]}..."
        print(
            f"[publish-report] 正在翻译批次 {batch_index}/{total_batches}（{len(batch)} 条）: {short_title}",
            flush=True,
        )

    return report_progress


def _build_translation_items(events: list[Event]) -> list[ReportCardTranslationItem]:
    items: list[ReportCardTranslationItem] = []
    for index, event in enumerate(events, start=1):
        items.append(
            ReportCardTranslationItem(
                index=index,
                title=(event.title or "未命名事件").strip(),
                summary=(event.summary or "暂无摘要").strip(),
                importance_reason=(event.importance_reason or "暂无重要度说明").strip(),
            )
        )
    return items


def _translate_cards(
    *,
    items: list[ReportCardTranslationItem],
    card_translator: BatchCardTranslator | None,
    translation_progress_callback: Callable[[int, int, list[ReportCardTranslationItem]], None] | None,
) -> dict[int, tuple[str, str, str]]:
    if card_translator is None or not items:
        return {}
    return card_translator(items, translation_progress_callback)


def _load_translation_batch_size() -> int:
    raw_value = os.getenv("REPORT_TRANSLATION_BATCH_SIZE", "5").strip()
    try:
        batch_size = int(raw_value)
    except ValueError:
        batch_size = 5
    return max(1, batch_size)


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
    """解析翻译 JSON，仅用于单卡片翻译（返回 dict）。"""
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


def _parse_batch_translation_json(content: str) -> dict[str, object] | None:
    """解析批量翻译 JSON，兼容多种 LLM 返回格式：
    - {"items": [...]}  标准格式
    - [...]              顶层数组
    - {"translations": [...]}  其他键名
    - Markdown 代码块包裹
    """
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        start = 1
        end = len(lines)
        if lines[-1].strip() == "```":
            end -= 1
        cleaned = "\n".join(lines[start:end]).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, list):
        return {"items": parsed}

    if not isinstance(parsed, dict):
        return None

    if isinstance(parsed.get("items"), list):
        return parsed

    for value in parsed.values():
        if isinstance(value, list):
            return {"items": value}

    return None


def _extract_batch_translation_items(parsed: dict[str, object]) -> dict[int, tuple[str, str, str]]:
    items = parsed.get("items")
    if not isinstance(items, list):
        return {}

    results: dict[int, tuple[str, str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_index = item.get("index")
        try:
            index = int(raw_index) if raw_index is not None else -1
        except (TypeError, ValueError):
            continue
        if index <= 0:
            continue

        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        reason = str(item.get("importance_reason") or item.get("reason") or "").strip()
        if not title or not summary or not reason:
            continue
        results[index] = (title, summary, reason)

    return results


def _debug_log(msg: str) -> None:
    """当 TRANSLATE_DEBUG=1 时输出调试信息。"""
    if os.getenv("TRANSLATE_DEBUG", "").strip() == "1":
        print(msg, flush=True)


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
    return _write_markdown_report(
        report_date=report.report_date,
        content_markdown=report.content_markdown,
        reports_dir=reports_dir,
        prefix="daily-report",
    )


def _write_alert_report(report: AlertReport, reports_dir: str) -> Path:
    return _write_markdown_report(
        report_date=report.report_date,
        content_markdown=report.content_markdown,
        reports_dir=reports_dir,
        prefix="alerts",
    )


def _write_markdown_report(
    *,
    report_date: str,
    content_markdown: str,
    reports_dir: str,
    prefix: str,
) -> Path:
    output_dir = Path(reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{prefix}-{report_date}-{timestamp}.md"
    report_path = output_dir / filename
    report_path.write_text(content_markdown, encoding="utf-8")
    return report_path
