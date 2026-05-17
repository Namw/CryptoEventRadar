# 第 3 周计划：工具调用（Week 3 Tool Calling）

## 目标

在本周内完成 4 个可调用工具，并让 agent 能根据问题自主选择工具，形成“提问 -> 选工具 -> 调工具 -> 生成结论”的闭环。

## 本周完成定义（DoD）

满足以下条件即视为第 3 周完成：

1. 已实现并可调用 4 个工具：行情、交易所信息、项目资料、历史事件查询。
2. 每个工具都有统一输入输出结构和错误处理约定。
3. agent 能在至少 5 条不同类型问题上自主选择并调用 1 到 3 个工具。
4. 输出中包含工具来源与关键字段（便于追溯和复盘）。
5. 至少有 1 份端到端演示记录（命令、输入、输出、结论）。

## 进度看板（每晚更新）

### Step 总进度

- [x] Step 1：增加行情工具
- [x] Step 2：增加交易所信息工具
- [x] Step 3：增加项目资料工具
- [x] Step 4：增加历史事件查询工具
- [ ] Step 5：让 agent 自主决定调用哪个工具

### Day 总进度

- [x] Day 1：接口规范日
- [x] Day 2：行情工具实现
- [x] Day 3：交易所信息工具实现
- [x] Day 4：项目资料工具实现
- [x] Day 5：历史事件查询工具实现
- [ ] Day 6：agent 工具路由联调
- [ ] Day 7：验收与复盘

### 本周状态

- 当前进行中：`Step 5（agent 自主工具选择）`
- 当前阻塞项：`无`
- 下一验收点：`Step 5 集成联调通过`

## 任务拆解（Step 视角）

### Step 1：增加行情工具

- [x] 状态：已完成
- [x] 验收通过

目标：给定资产符号，返回基础行情快照。

验收标准：

- 输入 `symbol=BTC` 能返回价格、24h 涨跌、成交量、时间戳。
- 接口超时、空结果、非法 symbol 时有结构化错误信息。

建议输出字段：

- `symbol`
- `price`
- `change_24h_pct`
- `volume_24h`
- `as_of`
- `source`

### Step 2：增加交易所信息工具

- [x] 状态：已完成
- [x] 验收通过

目标：给定交易所和资产，返回是否可交易、交易对状态、相关公告链接。

验收标准：

- 能按交易所和 symbol 查询到交易状态。
- 至少返回 1 条可追溯来源链接。

建议输出字段：

- `exchange`
- `symbol`
- `tradable`
- `pairs`
- `status`
- `reference_links`
- `source`

### Step 3：增加项目资料工具

- [x] 状态：已完成
- [x] 验收通过

目标：给定资产符号，返回项目基础资料，作为事件解释背景。

验收标准：

- 返回项目名称、官网、所属链、标签。
- 缺失字段时不报错，用 `null` 或空数组表示。

建议输出字段：

- `symbol`
- `project_name`
- `website`
- `chain`
- `tags`
- `source`

### Step 4：增加历史事件查询工具

- [x] 状态：已完成
- [x] 验收通过

目标：按资产、事件类型、时间窗口检索历史事件。

验收标准：

- 支持 `symbol + days` 的最小查询组合。
- 返回事件列表时包含 `event_id`、`event_time`、`event_type`、`importance_score`。

建议输出字段：

- `query`
- `total`
- `events`
- `source`

### Step 5：让 agent 自主决定调用哪个工具

- [ ] 状态：未开始
- [ ] 验收通过

目标：由 agent 根据用户问题自动规划工具调用链。

验收标准：

- 至少支持 3 类问题：
  - 单工具问题（如“BTC 今天涨跌多少”）
  - 双工具问题（如“某币上线后价格表现如何”）
  - 多工具问题（如“给我这个项目过去一周的事件和当前交易状态”）
- 输出中明确列出：调用了哪些工具、每个工具返回的关键证据。

## 每日计划（Day 视角）

### Day 1：接口规范日

- [x] 当日完成

- 定义工具通用协议（输入、输出、错误、超时、重试）
- 产出：工具协议草案 + 示例 JSON

### Day 2：行情工具实现

- [x] 当日完成

- 完成最小可用版
- 补 3 类测试：正常、异常、超时

### Day 3：交易所信息工具实现

- [x] 当日完成

- 完成数据抓取与结构化输出
- 补基础测试与样例

### Day 4：项目资料工具实现

- [x] 当日完成

- 完成项目元数据查询与缓存（可选）
- 补缺失字段容错测试

### Day 5：历史事件查询工具实现

- [x] 当日完成

- 复用现有事件库能力
- 补筛选逻辑测试

### Day 6：agent 工具路由联调

- [ ] 当日完成

- 增加工具选择策略（规则或 LLM）
- 完成多轮问题联调

### Day 7：验收与复盘

- [ ] 当日完成

- 跑端到端 demo
- 记录失败案例与下周改进项

## 开发顺序建议

1. 先做工具协议，再做具体工具。
2. 先打通单工具调用，再做多工具编排。
3. 优先保证可追溯和可复盘，再优化智能程度。

## 测试与验收清单

- 单元测试：每个工具至少 2 个成功样例 + 2 个失败样例。
- 集成测试：agent 对 5 条问题的调用路径正确。
- 回归检查：不影响当前 ingest/normalize/analyze/publish 主链路。

### 勾选清单（执行时直接打勾）

- [x] Step 1 单元测试通过
- [x] Step 2 单元测试通过
- [x] Step 3 单元测试通过
- [x] Step 4 单元测试通过
- [ ] Step 5 集成联调通过
- [ ] 主链路回归通过

## 每日进度记录（简版）

### Day 1 记录

- 计划：定义工具通用协议（输入、输出、错误、超时、重试），产出可复用骨架。
- 实际：已新增 `tools` 包，完成 `ToolRequest` / `ToolResult` / `ToolError` 协议与 `ToolRegistry` 注册调度；新增测试 `tests/test_tools_protocol.py`，共 4 个用例通过。
- 风险：当前仅完成协议层，尚未接入真实行情数据源。
- 明日：实现 Step 1 的 `market_data` 工具最小可用版，并补正常/异常/超时测试。

### Day 2 记录

- 计划：实现行情工具最小可用版，补正常/异常/超时测试。
- 实际：已新增 `MarketDataTool`（Binance 24h ticker 接口），支持 `symbol=BTC` 返回 `price/change_24h_pct/volume_24h/as_of/source`；异常路径包含 `invalid_symbol`、`timeout`、`empty_result`。
- 风险：真实外部接口可能受网络波动影响，后续需加缓存或降级源。
- 明日：实现 Step 2 交易所信息工具，并补基础测试与样例。

### Day 3 记录

- 计划：实现 Step 2 交易所信息工具，并补基础测试与样例。
- 实际：已新增 `ExchangeInfoTool`（Binance exchangeInfo 接口），支持 `exchange + symbol` 查询交易状态，返回 `exchange/symbol/tradable/pairs/status/reference_links/source`；异常路径包含 `invalid_exchange`、`invalid_symbol`、`timeout`、`empty_result`。新增测试 `tests/test_exchange_info_tool.py`，5 个用例通过；与 Step 1 回归测试合并执行共 13 个用例通过。
- 风险：当前仅支持 Binance，后续接入多交易所时需要抽象统一字段映射。
- 明日：实现 Step 3 项目资料工具，并补缺失字段容错测试。

### Day 4 记录

- 计划：实现 Step 3 项目资料工具，并补缺失字段容错测试。
- 实际：已新增 `ProjectInfoTool`（CoinGecko search + coin detail 接口），支持 `symbol` 查询项目资料，返回 `symbol/project_name/website/chain/tags/source`；缺失字段按约定返回 `null` 或空数组，不作为失败；异常路径包含 `invalid_symbol`、`timeout`、`empty_result`。新增测试 `tests/test_project_info_tool.py`，5 个用例通过；与 Step 1/2 协议和工具回归测试合并执行共 18 个用例通过。
- 风险：CoinGecko 公共接口存在限流风险，后续建议增加轻量缓存与降级策略。
- 明日：实现 Step 4 历史事件查询工具，并补筛选逻辑测试。

### Day 5 记录

- 计划：实现 Step 4 历史事件查询工具，并补筛选逻辑测试。
- 实际：已新增 `HistoryLookupTool`（基于本地 `events` 库查询），支持 `symbol + days` 最小查询组合，并支持可选 `event_type` 和 `limit`；返回 `query/total/events/source`，事件项包含 `event_id/event_time/event_type/importance_score` 等关键字段。新增测试 `tests/test_history_lookup_tool.py`，5 个用例通过；与 Step 1-3 及工具协议回归合并执行共 23 个用例通过。
- 风险：当前资产筛选基于 `assets_json` 的字符串匹配，后续数据量增大时需要考虑 JSON 字段索引或资产关联表优化查询性能。
- 明日：进入 Step 5，完成 agent 工具路由与多问题联调。

### Day 6 记录

- 计划：
- 实际：
- 风险：
- 明日：

### Day 7 记录

- 计划：
- 实际：
- 风险：
- 明日：

## 风险与回退策略

- 风险 1：第三方接口不稳定。
  - 回退：增加缓存与超时降级，保留最近一次有效快照。
- 风险 2：agent 选错工具。
  - 回退：先用规则路由兜底，再逐步放开 LLM 自主决策。
- 风险 3：工具返回格式不一致。
  - 回退：统一 ToolResponse 包装层。

## 与现有计划的对应关系

对应 [00_overall_plan.md](00_overall_plan.md) 中第 3 周 5 个未完成项，可作为执行清单直接推进。
