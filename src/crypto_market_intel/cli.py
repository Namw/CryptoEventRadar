from __future__ import annotations

import argparse
from collections.abc import Sequence

from crypto_market_intel.pipeline.ingest import run_all_sources_ingest, run_binance_ingest, run_coindesk_ingest
from crypto_market_intel.pipeline.normalize import run_normalize
from crypto_market_intel.services.event_service import run_analyze_events


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="crypto-market-intel")
    subparsers = parser.add_subparsers(dest="command")

    ingest_binance_parser = subparsers.add_parser("ingest-binance", help="Ingest Binance announcements")
    ingest_binance_parser.add_argument("--limit", type=int, default=20, help="Max records to fetch")

    ingest_coindesk_parser = subparsers.add_parser("ingest-coindesk", help="Ingest Coindesk RSS news")
    ingest_coindesk_parser.add_argument("--limit", type=int, default=20, help="Max records to fetch")

    ingest_all_parser = subparsers.add_parser("ingest-all", help="Ingest all enabled sources")
    ingest_all_parser.add_argument("--limit", type=int, default=20, help="Max records to fetch per source")

    normalize_parser = subparsers.add_parser("normalize-events", help="Normalize source_records into events")
    normalize_parser.add_argument("--limit", type=int, default=50, help="Max source records to normalize")

    analyze_parser = subparsers.add_parser("analyze-events", help="Analyze normalized events")
    analyze_parser.add_argument("--limit", type=int, default=50, help="Max events to analyze")

    args = parser.parse_args(argv)
    if args.command == "ingest-binance":
        result = run_binance_ingest(limit=args.limit)
        print(
            "ingest complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
        )
        return

    if args.command == "ingest-coindesk":
        result = run_coindesk_ingest(limit=args.limit)
        print(
            "ingest complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
        )
        return

    if args.command == "ingest-all":
        results = run_all_sources_ingest(limit=args.limit)
        for source_name, result in results.items():
            print(
                f"{source_name}: "
                f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
            )
        return

    if args.command == "normalize-events":
        result = run_normalize(limit=args.limit)
        print(
            "normalize complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
        )
        return

    if args.command == "analyze-events":
        result = run_analyze_events(limit=args.limit)
        print(
            "analyze complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']} "
            f"llm_used={result['llm_used']} fallback_rules={result['fallback_rules']} "
            f"elapsed_seconds={result['elapsed_seconds']}"
        )
        return

    print("crypto-market-intel-agent: scaffold ready")


if __name__ == "__main__":
    main()
