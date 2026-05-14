# 项目结构与模块设计

## 推荐目录结构

```text
crypto-market-intel-agent/
  pyproject.toml
  README.md
  .env.example
  backlog.md
  data/
    raw/
    processed/
  reports/
  scripts/
  tests/
  src/
    crypto_market_intel/
      __init__.py
      config.py
      logging.py
      schemas/
        event.py
        report.py
      db/
        models.py
        engine.py
        repo.py
      sources/
        base.py
        binance_announcements.py
        coindesk_news.py
      pipeline/
        ingest.py
        normalize.py
        deduplicate.py
        enrich.py
        score.py
        publish.py
      tools/
        market_data.py
        exchange_lookup.py
        asset_lookup.py
        history_lookup.py
      agents/
        event_analyst.py
        report_writer.py
      services/
        event_service.py
        report_service.py
        alert_service.py
      cli.py
```

## 模块职责

### `sources/`

负责数据采集。

- 每个 source 只做一件事：拉取原始数据并转成 source-specific records
- 第一版建议只接两个源：`binance_announcements` 和一个新闻源

### `schemas/`

负责结构化数据定义。

- `event.py`：统一事件 schema
- `report.py`：日报和告警 schema
- 建议用 Pydantic 约束字段，避免后面数据越来越乱

### `db/`

负责存储。

- `models.py`：SQLAlchemy 模型
- `engine.py`：数据库连接
- `repo.py`：最小仓储层

### `pipeline/`

负责主流程。

- `ingest.py`：抓取并保存原始数据
- `normalize.py`：转成统一事件
- `deduplicate.py`：去重和聚合
- `enrich.py`：补资产、来源、上下文
- `score.py`：打重要度分
- `publish.py`：生成日报和告警

### `tools/`

负责 agent 的外部能力。

- `market_data.py`：查价格、涨跌幅、成交量
- `exchange_lookup.py`：查交易所支持和公告背景
- `asset_lookup.py`：查币种基础资料
- `history_lookup.py`：查历史相似事件

### `agents/`

负责推理与输出。

- `event_analyst.py`：对事件进行分类、摘要、风险说明、决定是否调用工具
- `report_writer.py`：把事件列表整理成日报或告警文案

### `services/`

负责组合调用。

- `event_service.py`：从 source 到 unified event 的主流程
- `report_service.py`：日报生成
- `alert_service.py`：实时提醒和通知

## 第一版执行链路

```text
抓取原始公告/新闻
-> 保存 raw records
-> 规范化为 unified events
-> 去重聚合
-> 调用 event analyst agent
-> 需要时调用 market/history tools
-> 生成事件卡片
-> 输出 markdown 日报
```

## 第一版最小功能范围

- 两个 source
- SQLite
- 单 agent
- Markdown 日报
- 本地 CLI 运行
- 基础日志

## 暂时不要做的东西

- Web 前端
- 多 agent 自治编排
- 自动交易下单
- 复杂调度系统
- 向量数据库
