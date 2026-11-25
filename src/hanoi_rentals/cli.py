"""Command line entry point; run `hanoi-rentals --help`."""

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(
        description="Hanoi apartment and room rental pipeline"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["crawl", "refresh"]:
        sub = commands.add_parser(name)
        sub.add_argument("--since", default=None)
        sub.add_argument("--until", default=None)
        sub.add_argument(
            "--max-pages",
            type=int,
            default=0,
            help="Page limit per category; 0 traverses all accessible pages",
        )
        sub.add_argument(
            "--resume",
            default=None,
            help="Resume this run_id using only its verified raw responses",
        )
        sub.add_argument(
            "--sources", nargs="+", choices=["nhatot", "alonhadat"], default=None
        )
        sub.add_argument(
            "--categories", nargs="+", choices=["can_ho_chung_cu", "nha_tro"], default=None
        )
    commands.add_parser(
        "experiment-improvements",
        help="Run paired experiments on the frozen October development population",
    )
    history = commands.add_parser(
        "backfill-archives",
        help="Retrieve verified historical captures of the two Hanoi sources",
    )
    history.add_argument("--since", required=True)
    history.add_argument("--until", required=True)
    commands.add_parser("eda")
    commands.add_parser("train")
    commands.add_parser(
        "evaluate-temporal-holdout",
        help="Score the frozen candidate once after December 2026",
    )
    commands.add_parser(
        "replay-observations",
        help="Recover dated observations from checksummed raw archives",
    )
    commands.add_parser(
        "temporal-coverage",
        help="Report posting and observed-price coverage for all 14 months",
    )
    commands.add_parser(
        "train-temporal",
        help="Evaluate a dated candidate and export an isolated preview",
    )
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command in ["crawl", "refresh"]:
        from .ingestion.crawler import crawl

        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        summary = crawl(
            args.root,
            args.since or today.replace(day=1).isoformat(),
            args.until or today.isoformat(),
            args.max_pages,
            resume=args.resume,
            sources=args.sources,
            categories=args.categories,
        )
        if args.command == "refresh":
            from hanoi_rentals.operations.pipeline import train

            train(args.root, summary)
    elif args.command == "experiment-improvements":
        from .modeling.improvement import run

        run(args.root)
    elif args.command == "backfill-archives":
        from .ingestion.historical import run

        run(args.root, args.since, args.until)
    elif args.command == "eda":
        from hanoi_rentals.operations.pipeline import eda

        eda(args.root)
    elif args.command == "train":
        from hanoi_rentals.operations.pipeline import train

        train(args.root)
    elif args.command in ["replay-observations", "temporal-coverage"]:
        import json
        from .ingestion.observations import replay_archives, coverage_report

        function = (
            replay_archives
            if args.command == "replay-observations"
            else coverage_report
        )
        print(json.dumps(function(args.root.resolve()), ensure_ascii=False, indent=2))
    elif args.command == "train-temporal":
        from .modeling.temporal import train_temporal

        train_temporal(args.root)
    elif args.command == "evaluate-temporal-holdout":
        import json
        from .modeling.temporal_holdout import evaluate_holdout

        print(json.dumps(evaluate_holdout(args.root), ensure_ascii=False, indent=2))
    elif args.command == "serve":
        import os
        import uvicorn

        os.environ["RENTAL_ROOT"] = str(args.root.resolve())
        uvicorn.run(
            "hanoi_rentals.serving.api:create_app",
            factory=True,
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()
