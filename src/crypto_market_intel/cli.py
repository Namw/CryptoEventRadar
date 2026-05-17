from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from uuid import uuid4

from crypto_market_intel.agents.tool_router import answer_question
from crypto_market_intel.observability import emit_structured_log, set_trace_id
from crypto_market_intel.pipeline.deduplicate import run_deduplicate
from crypto_market_intel.pipeline.ingest import run_all_sources_ingest, run_binance_ingest, run_coindesk_ingest
from crypto_market_intel.pipeline.normalize import run_normalize
from crypto_market_intel.pipeline.publish import run_publish, run_publish_alerts
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

    dedupe_parser = subparsers.add_parser("deduplicate-events", help="Detect duplicate events and build clusters")
    dedupe_parser.add_argument("--limit", type=int, default=200, help="Max events to deduplicate")

    analyze_parser = subparsers.add_parser("analyze-events", help="Analyze normalized events")
    analyze_parser.add_argument("--limit", type=int, default=50, help="Max events to analyze")

    publish_parser = subparsers.add_parser("publish-report", help="Generate markdown daily report")
    publish_parser.add_argument("--limit", type=int, default=30, help="Max analyzed events to publish")
    publish_parser.add_argument("--reports-dir", type=str, default="reports", help="Output directory for reports")
    publish_parser.add_argument(
        "--translate-zh",
        action="store_true",
        help="Translate report card text into Simplified Chinese via LLM",
    )

    publish_alerts_parser = subparsers.add_parser("publish-alerts", help="Generate markdown alerts for high-importance events")
    publish_alerts_parser.add_argument("--limit", type=int, default=10, help="Max alert events to publish")
    publish_alerts_parser.add_argument("--reports-dir", type=str, default="reports", help="Output directory for alert reports")
    publish_alerts_parser.add_argument(
        "--min-importance",
        type=float,
        default=0.8,
        help="Minimum importance score required for alert output",
    )
    publish_alerts_parser.add_argument(
        "--notify",
        action="store_true",
        help="Send alert notification after alert markdown is generated",
    )

    tool_query_parser = subparsers.add_parser("tool-query", help="Route a natural language question to tools")
    tool_query_parser.add_argument("question", type=str, help="User question for tool routing")
    tool_query_parser.add_argument(
        "--backend",
        type=str,
        choices=["rules", "langchain_mcp"],
        default=None,
        help="Tool routing backend; default follows TOOL_ROUTER_BACKEND env",
    )

    args = parser.parse_args(argv)
    command = args.command or "noop"
    trace_id = f"cli-{command}-{uuid4().hex[:12]}"
    set_trace_id(trace_id)
    emit_structured_log("cli.command.start", command=command)

    if args.command == "ingest-binance":
        result = run_binance_ingest(limit=args.limit)
        emit_structured_log("cli.command.done", command=command, result=result)
        print(
            "ingest complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
        )
        return

    if args.command == "ingest-coindesk":
        result = run_coindesk_ingest(limit=args.limit)
        emit_structured_log("cli.command.done", command=command, result=result)
        print(
            "ingest complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
        )
        return

    if args.command == "ingest-all":
        results = run_all_sources_ingest(limit=args.limit)
        emit_structured_log("cli.command.done", command=command, result=results)
        for source_name, result in results.items():
            failed = result.get("failed", 0)
            print(
                f"{source_name}: "
                f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
                f" failed={failed}"
            )
        return

    if args.command == "normalize-events":
        result = run_normalize(limit=args.limit)
        emit_structured_log("cli.command.done", command=command, result=result)
        print(
            "normalize complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']}"
        )
        return

    if args.command == "deduplicate-events":
        result = run_deduplicate(limit=args.limit)
        emit_structured_log("cli.command.done", command=command, result=result)
        print(
            "deduplicate complete: "
            f"fetched={result['fetched']} updated={result['updated']} "
            f"clustered={result['clustered']} deduplicated={result['deduplicated']}"
        )
        return

    if args.command == "analyze-events":
        result = run_analyze_events(limit=args.limit)
        emit_structured_log("cli.command.done", command=command, result=result)
        print(
            "analyze complete: "
            f"fetched={result['fetched']} inserted={result['inserted']} skipped={result['skipped']} "
            f"llm_used={result['llm_used']} fallback_rules={result['fallback_rules']} "
            f"elapsed_seconds={result['elapsed_seconds']}"
        )
        return

    if args.command == "publish-report":
        result = run_publish(
            limit=args.limit,
            reports_dir=args.reports_dir,
            translate_to_zh=args.translate_zh,
        )
        emit_structured_log("cli.command.done", command=command, result=result)
        print(
            "publish complete: "
            f"events={result['events']} report_path={result['report_path']} "
            f"translate_to_zh={result['translate_to_zh']} translated_cards={result['translated_cards']} "
            f"translation_fallback_cards={result['translation_fallback_cards']} "
            f"translation_reason={result['translation_reason']}"
        )
        return

    if args.command == "publish-alerts":
        result = run_publish_alerts(
            limit=args.limit,
            reports_dir=args.reports_dir,
            min_importance=args.min_importance,
            notify=args.notify,
        )
        emit_structured_log("cli.command.done", command=command, result=result)
        print(
            "alert publish complete: "
            f"alerts={result['alerts']} report_path={result['report_path']} "
            f"min_importance={result['min_importance']} "
            f"notify_status={result['notify_status']}"
        )
        return

    if args.command == "tool-query":
        result = answer_question(args.question, backend=args.backend)
        emit_structured_log("cli.command.done", command=command, result=result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    emit_structured_log("cli.command.done", command=command, result="scaffold_ready")
    print("crypto-market-intel-agent: scaffold ready")


if __name__ == "__main__":
    main()
