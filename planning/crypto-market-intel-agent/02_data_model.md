# 数据表与核心 Schema

## 统一事件 Schema

建议第一版统一成以下字段：

```python
UnifiedEvent = {
    "event_id": "uuid",
    "source": "binance_announcements",
    "source_event_id": "original-id-or-url",
    "event_type": "listing|delisting|contract_update|security|macro|project_news|other",
    "title": "...",
    "summary": "...",
    "raw_text": "...",
    "event_time": "2026-05-14T10:00:00Z",
    "detected_at": "2026-05-14T10:01:03Z",
    "assets": ["BTC", "ETH"],
    "exchange": "Binance",
    "importance_score": 0.0,
    "source_url": "https://...",
    "source_trust_score": 0.0,
    "dedupe_key": "...",
    "status": "new|deduplicated|analyzed|published",
}
```

## 推荐数据表

### `source_records`

保存最原始的数据，方便回溯。

字段建议：

- `id`
- `source_name`
- `source_record_id`
- `title`
- `url`
- `published_at`
- `raw_payload`
- `content_hash`
- `fetched_at`
- `created_at`
- `updated_at`

### `events`

保存统一后的事件主表。

字段建议：

- `id`
- `event_id`
- `source_record_id`
- `event_type`
- `title`
- `summary`
- `raw_text`
- `event_time`
- `detected_at`
- `exchange_name`
- `source_url`
- `source_trust_score`
- `importance_score`
- `dedupe_key`
- `status`
- `created_at`
- `updated_at`

### `event_assets`

因为一个事件可能对应多个资产，单独拆表。

字段建议：

- `id`
- `event_id`
- `asset_symbol`
- `asset_name`
- `confidence_score`
- `created_at`
- `updated_at`

### `event_clusters`

用于把重复或相近事件聚合。

字段建议：

- `id`
- `cluster_key`
- `canonical_event_id`
- `cluster_reason`
- `created_at`
- `updated_at`

### `agent_runs`

记录 agent 的执行情况，后面做评估和 trace 会用到。

字段建议：

- `id`
- `event_id`
- `trace_id`
- `model_name`
- `prompt_version`
- `input_snapshot`
- `output_snapshot`
- `tool_calls`
- `latency_ms`
- `status`
- `error_message`
- `created_at`
- `updated_at`

### `reports`

记录每次日报和告警产物。

字段建议：

- `id`
- `report_type`
- `title`
- `content_markdown`
- `report_date`
- `published_to`
- `created_at`
- `updated_at`

## 表之间的关系

```text
source_records 1 -> 1 events
events 1 -> n event_assets
events n -> 1 event_clusters
events 1 -> n agent_runs
reports n -> n events
```

## 第一版数据库建议

- 第一版直接用 SQLite
- ORM 建议用 SQLAlchemy 2.x
- 不要一开始就上 Postgres
- 第一版先把可追溯性做好，比数据库选型更重要

## 第一版必须保留的字段

- 原文
- 原始 URL
- 事件时间
- 抽取到的资产
- 分类结果
- 重要度分数
- agent 输出
- 工具调用记录
