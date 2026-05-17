# Crypto Market Intel Agent

一个面向加密市场的事件研究 Agent：自动采集公告和新闻，完成事件抽取、分类、去重、资产映射与优先级排序，输出日报和告警。

## 第一版目标

- 本地可运行
- 可回溯事件数据
- 可生成 Markdown 日报
- 可生成 Markdown 告警

## 当前阶段

当前仓库已完成 Week 1 到 Week 3，并进入 Week 4 交付阶段。

当前已完成：

- 数据采集、规范化、去重、分析、日报输出
- 4 个工具能力与 agent 工具路由
- CLI 单次执行与批量主链路
- 本地 Markdown 告警输出
- 命令级 trace id 与结构化日志

当前未完成：

- Week 5 评估数据与自动评估脚本

## Day 2 运行方式

先抓取 Binance 公告并写入 SQLite `source_records`：

```bash
uv run python main.py ingest-binance --limit 20
```

如果本地网络对 Binance 有拦截，请在 `.env` 中配置代理（可用你的 VPN 本地代理地址）：

```env
BINANCE_PROXY_URL=http://127.0.0.1:7890
```

默认数据库路径来自 `.env.example`：

- `DATABASE_URL=sqlite:///./data/app.db`

## Day 3 运行方式

抓取第二个 source（Coindesk RSS）并写入同一张 `source_records`：

```bash
uv run python main.py ingest-coindesk --limit 20
```

一次抓取两个 source：

```bash
uv run python main.py ingest-all --limit 20
```

## Day 4 运行方式

将 source_records 规范化为统一事件并写入 events：

```bash
uv run python main.py normalize-events --limit 50
```

## Week 2 Step 1：重复事件检测与聚合

对事件进行去重聚合，将重复事件标记为 `deduplicated`（主事件保留当前状态）：

```bash
uv run python main.py deduplicate-events --limit 200
```

## Day 5 运行方式

对规范化事件执行分析（LLM + fallback），并打印可观测进度：

```bash
uv run python main.py analyze-events --limit 50
```

## Day 6 运行方式

生成 Markdown 日报并写入 `reports/`：

```bash
uv run python main.py publish-report --limit 30
```

如需在发布阶段尝试将卡片内容翻译为简体中文（LLM 失败会自动回退原文）：

```bash
uv run python main.py publish-report --limit 30 --translate-zh
```

自定义日报输出目录：

```bash
uv run python main.py publish-report --limit 30 --reports-dir reports
```

## Week 4：告警输出

生成高重要度事件告警并写入 `reports/`：

```bash
uv run python main.py publish-alerts --limit 10 --min-importance 0.8
```

自定义告警输出目录或阈值：

```bash
uv run python main.py publish-alerts --limit 20 --min-importance 0.9 --reports-dir reports
```

说明：当前阶段的告警输出为本地 Markdown 产物，通知渠道还未接入。

## Week 4：告警通知渠道（最小版）

当前已支持最小通知渠道：

- `console`：打印通知摘要到终端
- `webhook`：发送 JSON 到 `ALERT_WEBHOOK_URL`
- `both`：同时发送到 console 和 webhook

在 `.env` 配置：

```env
ALERT_NOTIFY_CHANNEL=console
ALERT_WEBHOOK_URL=
ALERT_WEBHOOK_TIMEOUT_SECONDS=8
```

触发告警并发送通知：

```bash
uv run python main.py publish-alerts --limit 10 --min-importance 0.8 --notify
```

## Week 4：trace id 与结构化日志

当前 CLI 与核心链路（ingest/normalize/deduplicate/analyze/publish/alert）会输出 JSON 结构化日志，并自动附带 trace_id，便于端到端排查与复盘。

示例（简化）：

```json
{"event": "cli.command.start", "trace_id": "cli-publish-alerts-...", "command": "publish-alerts"}
{"event": "pipeline.publish_alerts.start", "trace_id": "cli-publish-alerts-...", "limit": 10}
{"event": "alert.notify.done", "trace_id": "cli-publish-alerts-...", "status": "ok", "channel": "console"}
```

## Week 3 工具路由（LangChain + MCP）

当前支持两种后端：

- `rules`：规则路由（本地稳定兜底）
- `langchain_mcp`：LangChain Agent + MCP 工具调用

推荐先在 `.env` 中配置：

```env
TOOL_ROUTER_BACKEND=langchain_mcp
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=20
```

执行工具问答（默认读取 `TOOL_ROUTER_BACKEND`）：

```bash
uv run python main.py tool-query "BTC 今天涨跌多少"
```

也可以临时指定后端：

```bash
uv run python main.py tool-query "BTC 今天涨跌多少" --backend rules
uv run python main.py tool-query "BTC 今天涨跌多少" --backend langchain_mcp
```

说明：当 `langchain_mcp` 依赖或 LLM 配置不可用时，会自动回退到 `rules` 后端，保证命令可用。

## Day 7：完整流程验证（已验证）

使用临时数据库从零跑通一遍流程（不污染默认 `data/app.db`）：

```bash
DATABASE_URL=sqlite:///./data/day7_smoke.db uv run python main.py ingest-all --limit 3
DATABASE_URL=sqlite:///./data/day7_smoke.db uv run python main.py normalize-events --limit 10
DATABASE_URL=sqlite:///./data/day7_smoke.db uv run python main.py analyze-events --limit 10
DATABASE_URL=sqlite:///./data/day7_smoke.db uv run python main.py publish-report --limit 10
```

校验数据库状态：

```bash
sqlite3 data/day7_smoke.db ".tables"
sqlite3 data/day7_smoke.db "SELECT status, COUNT(*) FROM events GROUP BY status;"
```

本次验证结果：`source_records=6`，`events=6`，`events.status=analyzed(6)`，并生成日报文件。

## 已知问题

- 直接执行 `python3 main.py ...` 可能报 `ModuleNotFoundError: No module named 'sqlalchemy'`。
- 原因是依赖安装在 `uv` 虚拟环境中；请统一使用 `uv run python main.py ...`。
- 当 source 没有新数据时，`normalize-events` 出现 `fetched=0 inserted=0` 属于正常行为，不是故障。
