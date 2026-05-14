from __future__ import annotations

import argparse
from collections.abc import Sequence

from crypto_market_intel.pipeline.ingest import run_binance_ingest


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="crypto-market-intel")
    subparsers = parser.add_subparsers(dest="command")

    ingest_binance_parser = subparsers.add_parser("ingest-binance", help="Ingest Binance announcements")
    ingest_binance_parser.add_argument("--limit", type=int, default=20, help="Max records to fetch")

    args = parser.parse_args(argv)
    if args.command == "ingest-binance":
        result = run_binance_ingest(limit=args.limit)
        print(
            "ingest complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
        )
        return

    print("crypto-market-intel-agent: scaffold ready")


if __name__ == "__main__":
    main()
