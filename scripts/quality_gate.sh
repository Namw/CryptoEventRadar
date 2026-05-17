#!/usr/bin/env bash
set -euo pipefail

# 统一质量门禁：类型检查 + 单元测试
if command -v uv >/dev/null 2>&1; then
  uv run pyright src tests
  uv run pytest -q
else
  pyright src tests
  pytest -q
fi
