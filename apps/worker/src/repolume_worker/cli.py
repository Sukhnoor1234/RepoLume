"""Command-line boundary for the analysis worker."""

import argparse
import json
import sys
from collections.abc import Sequence
from os import getenv
from typing import TextIO

from repolume_worker import __version__
from repolume_worker.analysis_queue import (
    RedisAnalysisQueue,
    WorkerQueueSettings,
    create_redis_client,
)
from repolume_worker.config import WorkerSettings
from repolume_worker.database import WorkerDatabaseSettings, create_database_engine
from repolume_worker.pipeline import RepositoryAnalysisPipeline
from repolume_worker.retrieval import GitHubRepositoryRetriever
from repolume_worker.runtime import AnalysisWorkerRuntime, WorkerRunResult
from repolume_worker.runtime_storage import WorkerAnalysisStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RepoLume analysis worker")
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument(
        "--check",
        action="store_true",
        help="validate configuration and print worker readiness",
    )
    commands.add_argument(
        "--once",
        action="store_true",
        help="process at most one recovered or new analysis request",
    )
    return parser


def _runtime_is_configured() -> bool:
    database_configured = bool(getenv("REPOLUME_DATABASE_URL", ""))
    redis_configured = bool(getenv("REPOLUME_REDIS_URL", ""))
    if database_configured != redis_configured:
        raise ValueError("REPOLUME_DATABASE_URL and REPOLUME_REDIS_URL must be configured together")
    return database_configured


def run_once_from_environment() -> WorkerRunResult:
    """Own concrete runtime resources for one bounded worker invocation."""

    database_settings = WorkerDatabaseSettings.from_environment()
    queue_settings = WorkerQueueSettings.from_environment()
    engine = create_database_engine(database_settings)
    redis = create_redis_client(queue_settings)
    consumer_name = getenv("REPOLUME_WORKER_CONSUMER", "worker-1")
    try:
        queue = RedisAnalysisQueue(
            redis,
            stream_name=queue_settings.stream_name,
            consumer_group=queue_settings.consumer_group,
            claim_idle_ms=queue_settings.claim_idle_ms,
        )
        storage = WorkerAnalysisStorage(engine)
        with GitHubRepositoryRetriever() as retriever:
            runtime = AnalysisWorkerRuntime(
                queue,
                storage,
                RepositoryAnalysisPipeline(retriever),
            )
            return runtime.process_once(consumer_name)
    finally:
        redis.close()
        engine.dispose()


def main(argv: Sequence[str] | None = None, output: TextIO | None = None) -> int:
    """Run a readiness check or one bounded analysis delivery."""

    parser = build_parser()
    args = parser.parse_args(argv)
    settings = WorkerSettings.from_environment()
    configured = _runtime_is_configured()

    if args.check:
        if configured:
            WorkerDatabaseSettings.from_environment()
            WorkerQueueSettings.from_environment()
        payload = {
            "event": "worker.ready",
            "service": settings.service_name,
            "version": __version__,
            "environment": settings.environment,
            "queue_backend": "redis_streams" if configured else "not_configured",
        }
    else:
        if not configured:
            parser.error("--once requires the database and Redis runtime configuration")
        result = run_once_from_environment()
        payload = {
            "event": "worker.run_once",
            "service": settings.service_name,
            "version": __version__,
            "environment": settings.environment,
            "outcome": result.outcome,
            "analysis_id": result.analysis_id,
        }
    print(json.dumps(payload, sort_keys=True), file=output or sys.stdout)
    return 0


def entrypoint() -> None:
    """Run the console entry point."""

    raise SystemExit(main())
