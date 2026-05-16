from __future__ import annotations

import json
import os
from dataclasses import dataclass
from collections.abc import Iterable
from typing import Any
from urllib import error, request

from crypto_market_intel.schemas.event import EventAnalysis, UnifiedEvent


DEFAULT_ANALYST_PROMPT = """你是一个加密市场事件研究助手。
请基于输入事件输出结构化结果，必须包含：
1) summary: 1-2 句中文摘要
2) event_type: 事件类型字符串
3) assets: 资产符号数组
4) importance_score: 0 到 1 之间的小数
5) importance_reason: 中文重要度说明
要求输出稳定、简洁、可供日报直接使用，并且只输出 JSON。"""


@dataclass(frozen=True)
class LLMConfig:
	api_key: str
	model: str
	base_url: str
	timeout_seconds: float


@dataclass(frozen=True)
class AnalysisTrace:
	mode: str
	llm_attempted: bool
	llm_used: bool
	llm_model: str | None
	fallback_reason: str | None


def analyze_event(event: UnifiedEvent) -> EventAnalysis:
	analysis, _trace = analyze_event_with_trace(event)
	return analysis


def analyze_event_with_trace(event: UnifiedEvent) -> tuple[EventAnalysis, AnalysisTrace]:
	try:
		llm_result, llm_reason, llm_model = _analyze_with_llm(event)
		if llm_result is not None:
			return llm_result, AnalysisTrace(
				mode="llm",
				llm_attempted=True,
				llm_used=True,
				llm_model=llm_model,
				fallback_reason=None,
			)
	except Exception:
		llm_reason = "llm_exception"
		llm_model = None

	if llm_reason == "llm_not_configured":
		llm_attempted = False
	else:
		llm_attempted = True

	return _analyze_event_with_rules(event), AnalysisTrace(
		mode="fallback_rules",
		llm_attempted=llm_attempted,
		llm_used=False,
		llm_model=llm_model,
		fallback_reason=llm_reason,
	)


def _analyze_event_with_rules(event: UnifiedEvent) -> EventAnalysis:
	assets = _dedupe_assets(event.assets)
	summary = _build_summary(event)
	importance_score = _score_importance(event.event_type, assets)
	importance_reason = _build_importance_reason(event.event_type, assets, event.title)
	return EventAnalysis(
		event_id=event.event_id,
		source=event.source,
		source_event_id=event.source_event_id,
		event_type=event.event_type,
		title=event.title,
		summary=summary,
		assets=assets,
		importance_score=importance_score,
		importance_reason=importance_reason,
		status="analyzed",
	)


def analyze_events(events: Iterable[UnifiedEvent]) -> list[EventAnalysis]:
	return [analyze_event(event) for event in events]


def _analyze_with_llm(event: UnifiedEvent) -> tuple[EventAnalysis | None, str | None, str | None]:
	config = _load_llm_config()
	if config is None:
		return None, "llm_not_configured", None

	prompt_input = {
		"event_id": event.event_id,
		"source": event.source,
		"source_event_id": event.source_event_id,
		"event_type": event.event_type,
		"title": event.title,
		"source_url": event.source_url,
		"assets": event.assets,
		"summary": event.summary,
		"raw_text": event.raw_text,
		"event_time": event.event_time.isoformat() if event.event_time else None,
	}

	body = {
		"model": config.model,
		"temperature": 0,
		"messages": [
			{"role": "system", "content": DEFAULT_ANALYST_PROMPT},
			{
				"role": "user",
				"content": json.dumps(prompt_input, ensure_ascii=False),
			},
		],
	}

	endpoint = f"{config.base_url.rstrip('/')}/chat/completions"
	req = request.Request(
		endpoint,
		data=json.dumps(body).encode("utf-8"),
		headers={
			"Authorization": f"Bearer {config.api_key}",
			"Content-Type": "application/json",
		},
		method="POST",
	)

	try:
		with request.urlopen(req, timeout=config.timeout_seconds) as resp:
			response_payload = json.loads(resp.read().decode("utf-8"))
	except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
		return None, "llm_request_failed", config.model

	content = _extract_message_content(response_payload)
	if not content:
		return None, "llm_empty_response", config.model

	parsed = _parse_llm_json(content)
	if parsed is None:
		return None, "llm_invalid_json", config.model

	return _build_analysis_from_llm_payload(event, parsed), None, config.model


def _load_llm_config() -> LLMConfig | None:
	api_key = os.getenv("OPENAI_API_KEY", "").strip()
	model = os.getenv("OPENAI_MODEL", "").strip()
	if not api_key or not model:
		return None

	base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
	raw_timeout = os.getenv("OPENAI_TIMEOUT_SECONDS", "20").strip()
	try:
		timeout_seconds = float(raw_timeout)
	except ValueError:
		timeout_seconds = 20.0

	return LLMConfig(
		api_key=api_key,
		model=model,
		base_url=base_url,
		timeout_seconds=max(5.0, timeout_seconds),
	)


def _extract_message_content(response_payload: dict[str, Any]) -> str | None:
	choices = response_payload.get("choices")
	if not isinstance(choices, list) or not choices:
		return None
	message = choices[0].get("message") if isinstance(choices[0], dict) else None
	if not isinstance(message, dict):
		return None
	content = message.get("content")
	if isinstance(content, str):
		return content.strip()
	return None


def _parse_llm_json(content: str) -> dict[str, Any] | None:
	try:
		parsed = json.loads(content)
		if isinstance(parsed, dict):
			return parsed
		return None
	except json.JSONDecodeError:
		# 兼容模型返回 ```json ... ``` 包裹场景。
		cleaned = content.replace("```json", "").replace("```", "").strip()
		try:
			parsed = json.loads(cleaned)
			if isinstance(parsed, dict):
				return parsed
			return None
		except json.JSONDecodeError:
			return None


def _build_analysis_from_llm_payload(event: UnifiedEvent, payload: dict[str, Any]) -> EventAnalysis:
	summary = str(payload.get("summary") or "").strip()
	if not summary:
		summary = _build_summary(event)

	raw_event_type = str(payload.get("event_type") or event.event_type or "other")
	event_type = raw_event_type.strip().lower().replace(" ", "_")
	if not event_type:
		event_type = event.event_type

	raw_assets = payload.get("assets")
	assets: list[str] = []
	if isinstance(raw_assets, list):
		assets = _dedupe_assets([str(item) for item in raw_assets if isinstance(item, str)])
	if not assets:
		assets = _dedupe_assets(event.assets)

	raw_score = payload.get("importance_score")
	try:
		importance_score = float(raw_score)
	except (TypeError, ValueError):
		importance_score = _score_importance(event_type, assets)
	importance_score = round(min(max(importance_score, 0.0), 1.0), 2)

	importance_reason = str(payload.get("importance_reason") or "").strip()
	if not importance_reason:
		importance_reason = _build_importance_reason(event_type, assets, event.title)

	return EventAnalysis(
		event_id=event.event_id,
		source=event.source,
		source_event_id=event.source_event_id,
		event_type=event_type,
		title=event.title,
		summary=summary,
		assets=assets,
		importance_score=importance_score,
		importance_reason=importance_reason,
		status="analyzed",
	)


def _build_summary(event: UnifiedEvent) -> str:
	if event.summary:
		return event.summary.strip()

	parts = [event.title.strip()]
	if event.raw_text:
		raw_text = event.raw_text.strip()
		if raw_text and raw_text != event.title.strip():
			parts.append(raw_text[:120])
	return " - ".join(part for part in parts if part)


def _dedupe_assets(assets: list[str]) -> list[str]:
	result: list[str] = []
	for asset in assets:
		normalized = asset.strip().upper()
		if normalized and normalized not in result:
			result.append(normalized)
	return result


def _score_importance(event_type: str, assets: list[str]) -> float:
	base_scores = {
		"delisting": 0.95,
		"security": 0.9,
		"listing": 0.85,
		"project_news": 0.6,
		"other": 0.4,
	}
	score = base_scores.get(event_type, 0.5)
	if assets:
		score += 0.05
	return round(min(score, 1.0), 2)


def _build_importance_reason(event_type: str, assets: list[str], title: str) -> str:
	asset_text = "、".join(assets) if assets else "未识别出明确资产"
	if event_type == "delisting":
		return f"{title} 属于下架类事件，通常直接影响 {asset_text} 的流动性和交易可见性。"
	if event_type == "listing":
		return f"{title} 属于上线类事件，通常会提升 {asset_text} 的交易关注度和短期波动。"
	if event_type == "security":
		return f"{title} 属于安全/风险类事件，通常会显著影响市场情绪，重点关注 {asset_text}。"
	if event_type == "project_news":
		return f"{title} 属于新闻类事件，更多反映基本面变化，需结合 {asset_text} 进一步判断影响。"
	return f"{title} 暂归类为一般事件，当前只识别到 {asset_text}，建议后续结合上下文复核。"
