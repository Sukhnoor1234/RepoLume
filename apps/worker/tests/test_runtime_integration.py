"""PostgreSQL and Redis integration coverage for worker runtime orchestration."""

from os import environ
from types import SimpleNamespace
from uuid import uuid4

import pytest
from redis import Redis
from sqlalchemy import create_engine, insert, select

from repolume_worker.analysis_queue import RedisAnalysisQueue
from repolume_worker.architecture import RepositoryArchitectureComposer
from repolume_worker.jobs import AnalysisJob
from repolume_worker.runtime import AnalysisWorkerRuntime
from repolume_worker.runtime_storage import (
    WorkerAnalysisStorage,
    analysis_architectures,
    analysis_jobs,
    metadata,
)

pytestmark = pytest.mark.integration
_COMMIT_SHA = "a" * 40


class CompletingPipeline:
    def run(self, job: AnalysisJob, request, *, observer=None):
        assert observer is not None
        observer.on_cloning()
        observer.on_analyzing(_COMMIT_SHA)
        return SimpleNamespace(
            repository=SimpleNamespace(commit_sha=_COMMIT_SHA),
            architecture=RepositoryArchitectureComposer().compose(()),
        )


def test_real_queue_delivery_persists_and_acknowledges_result() -> None:
    database_url = environ["REPOLUME_TEST_DATABASE_URL"]
    redis_url = environ["REPOLUME_TEST_REDIS_URL"]
    analysis_id = f"analysis_{uuid4().hex}"
    stream = f"repolume:test:runtime:{uuid4()}"
    group = f"test-runtime-{uuid4()}"
    engine = create_engine(database_url)
    redis = Redis.from_url(redis_url, decode_responses=True)
    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(analysis_jobs).values(
                    analysis_id=analysis_id,
                    provider="github",
                    owner="octocat",
                    repository="Hello-World",
                    canonical_url="https://github.com/octocat/Hello-World",
                    requested_ref="main",
                    status="queued",
                    version=1,
                )
            )
        redis.xadd(
            stream,
            {
                "schema_version": "1.0",
                "event_id": str(uuid4()),
                "analysis_id": analysis_id,
                "provider": "github",
                "owner": "octocat",
                "repository": "Hello-World",
                "ref": "main",
            },
        )
        queue = RedisAnalysisQueue(redis, stream_name=stream, consumer_group=group)
        storage = WorkerAnalysisStorage(engine)

        result = AnalysisWorkerRuntime(queue, storage, CompletingPipeline()).process_once(
            "worker-integration", block_ms=100
        )
        with engine.connect() as connection:
            architecture_id = connection.scalar(select(analysis_architectures.c.analysis_id))

        assert result.outcome == "completed"
        assert storage.get_job(analysis_id).status.value == "completed"
        assert architecture_id == analysis_id
        assert redis.xpending(stream, group)["pending"] == 0
    finally:
        redis.delete(stream)
        metadata.drop_all(engine)
        redis.close()
        engine.dispose()
