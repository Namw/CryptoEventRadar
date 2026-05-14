# Crypto Market Intel Agent

一个面向加密市场的事件研究 Agent：自动采集公告和新闻，完成事件抽取、分类、去重、资产映射与优先级排序，输出日报和告警。

## 第一版目标

- 本地可运行
- 可回溯事件数据
- 可生成 Markdown 日报

## 当前阶段

当前仓库已完成规划文档，正在进行 Week 1 的工程化落地。

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
