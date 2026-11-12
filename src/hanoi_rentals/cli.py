"""Command line entry point; run `hanoi-rentals --help`."""

import argparse
from datetime import date, datetime
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
        sub.add_argument("--max-pages", type=int, default=120)
    commands.add_parser("eda")
    commands.add_parser("train")
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
        )
        if args.command == "refresh":
            from .pipeline import train

            train(args.root, summary)
    elif args.command == "eda":
        from .pipeline import eda

        eda(args.root)
    elif args.command == "train":
        from .pipeline import train

        train(args.root)
    elif args.command == "serve":
        import os
        import uvicorn

        os.environ["RENTAL_ROOT"] = str(args.root.resolve())
        uvicorn.run(
            "hanoi_rentals.api:create_app", factory=True, host=args.host, port=args.port
        )


if __name__ == "__main__":
    main()
