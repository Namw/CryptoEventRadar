# Week 3 Step5 端到端演示记录

- 日期：2026-05-17
- 目标：验证 agent 能根据自然语言问题自主规划并调用多个工具，输出可追溯证据。

## 命令

```bash
uv run python -m crypto_market_intel.cli tool-query "给我 BTC 这个项目过去一周的事件和当前交易状态"
```

## 输入

- question：给我 BTC 这个项目过去一周的事件和当前交易状态

## 输出（关键片段）

- route:
  - symbol: BTC
  - exchange: binance
  - days: 7
  - planned_tools: exchange_info, project_info, history_lookup

- tool_calls:
  - exchange_info:
    - status: TRADING
    - tradable: true
    - source: exchange_public_api
  - project_info:
    - project_name: Bitcoin
    - source: coingecko_public_api
  - history_lookup:
    - total: 1
    - events[0].event_type: project_news
    - source: local_event_db

- conclusion:
  - 共调用 3 个工具，全部成功并返回关键证据。

## 结论

本次演示验证了 Step5 的闭环能力：

1. agent 能从问题中自动抽取关键参数（symbol/exchange/days）。
2. agent 能自动选择并编排多工具调用（3 个工具）。
3. 输出包含每个工具的 source 与关键字段，满足可追溯要求。
4. 从“提问 -> 选工具 -> 调工具 -> 生成结论”的链路已跑通。
