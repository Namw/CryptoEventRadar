# 第一周开发清单

目标：本地跑通一个最小闭环，从真实数据到 markdown 日报。

## Day 1

- [x] 在仓库根目录初始化主项目结构
- [x] 初始化 `uv` 项目
- [x] 建立 `src/`、`tests/`、`data/`、`reports/`
- [x] 写 `.env.example`
- [x] 写 `README.md` 的项目目标和运行方式草稿

交付标准：目录结构固定下来，别人能看懂项目目标。

## Day 2

- [x] 接入第一个 source：Binance 公告
- [x] 拉到原始数据
- [x] 保存到本地 JSON 或 SQLite
- [x] 给原始数据计算 `content_hash`

交付标准：能稳定抓到第一类真实数据。

## Day 3

- [x] 接入第二个 source：新闻源或项目公告源
- [x] 统一 source 接口
- [x] 两个 source 的输出都能写入 `source_records`

交付标准：两个来源的数据都能入库。

## Day 4

- [x] 定义 `UnifiedEvent` Pydantic 模型
- [x] 实现 `normalize.py`
- [x] 把 source records 规范化为统一事件
- [x] 给事件打基础标签：source、title、url、event_time

交付标准：你不再面对两套乱结构，而是统一事件对象。

## Day 5

- [x] 写 `event_analyst` 的第一版 prompt
- [x] 对单条事件生成摘要
- [x] 输出事件分类
- [x] 输出涉及资产
- [x] 输出重要度说明

交付标准：单条事件已经像一个研究助手的输出。

## Day 6

- [x] 写 `publish.py`
- [x] 生成 markdown 日报
- [x] 把重要事件列成卡片
- [x] 在日报中附原始链接和时间

交付标准：形成一份能发给别人看的日报。

## Day 7

- [x] 从头跑一次完整流程
- [x] 修掉阻塞性 bug
- [x] 补 README 的运行步骤
- [x] 记录已知问题

交付标准：你可以完整演示“抓取 -> 分析 -> 输出”。

## 本周完成定义

- [x] 两个真实 source 已接入
- [x] 原始数据可回溯
- [x] 统一事件模型已落地
- [x] 单条事件可分析
- [x] 日报可生成
- [x] README 可指导运行
