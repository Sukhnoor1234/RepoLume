"""Command-line boundary for the analysis worker."""

import argparse
import json
import sys
from collections.abc import Sequence
from typing import TextIO

from repolume_worker import __version__
from repolume_worker.config import WorkerSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RepoLume analysis worker")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate configuration and print worker readiness",
    )
    return parser


def main(argv: Sequence[str] | None = None, output: TextIO | None = None) -> int:
    """Run the supported worker command."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.check:
        parser.error("the worker currently supports only --check")

    settings = WorkerSettings.from_environment()
    payload = {
        "event": "worker.ready",
        "service": settings.service_name,
        "version": __version__,
        "environment": settings.environment,
        "queue_backend": "not_configured",
    }
    print(json.dumps(payload, sort_keys=True), file=output or sys.stdout)
    return 0


def entrypoint() -> None:
    """Run the console entry point."""

    raise SystemExit(main())
