from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parent
    src_path = repo_root / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


_ensure_src_on_path()

try:
    from crypto_market_intel.cli import main as cli_main
    from crypto_market_intel.config import load_env
except ModuleNotFoundError as exc:
    if exc.name == "sqlalchemy":
        print("缺少依赖 sqlalchemy。请先使用 `uv sync` 安装依赖，并通过 `uv run python main.py ...` 运行。")
        raise SystemExit(1) from exc
    raise


if __name__ == "__main__":
    load_env()
    cli_main()
