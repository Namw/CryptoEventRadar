# 当前仓库的落地方式

目标：不要再把这个仓库继续长成 demo 杂物间，而是让它开始服务于一个主项目。

## 建议的仓库使用方式

### 现在保留什么

- `planning/crypto-market-intel-agent/`：保留，作为项目规划区
- `pyproject.toml`：保留，后续会替换成主项目配置
- `.gitignore`：保留

### 现在不要急着做什么

- 不要立刻删掉旧 demo，如果它们还在别处备份不足
- 不要先写前端
- 不要先接太多 source
- 不要先做自动交易

## 推荐的下一步目录

在当前仓库根目录下，新建真正的主项目目录：

```text
crypto-market-intel-agent/
```

后面所有实际代码都放进这个目录，`planning/` 只保存规划文档。

## 建议的开发顺序

### Step 1

先创建项目骨架。

- `crypto-market-intel-agent/README.md`
- `crypto-market-intel-agent/.env.example`
- `crypto-market-intel-agent/src/`
- `crypto-market-intel-agent/tests/`
- `crypto-market-intel-agent/data/`
- `crypto-market-intel-agent/reports/`

### Step 2

先做两个数据源，不要更多。

- 一个交易所公告源
- 一个新闻源

### Step 3

先用 SQLite，不要升级数据库。

### Step 4

先打通命令行跑通流程，再考虑服务化。

## 你今天完成就够了的事情

- [ ] 读完 `01_project_blueprint.md`
- [ ] 读完 `02_data_model.md`
- [ ] 创建 `crypto-market-intel-agent/`
- [ ] 创建项目骨架目录
- [ ] 写一句项目目标到新项目 README
- [ ] 把今天冒出来的新想法写进 `backlog.md`

## 明天的第一优先级

- [ ] 接 Binance 公告源
- [ ] 抓到第一批真实数据
- [ ] 落地 `source_records`
