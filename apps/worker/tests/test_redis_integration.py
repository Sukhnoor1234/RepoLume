"""Redis integration coverage for the worker consumer group."""

from os import environ
from uuid import uuid4

import pytest
from redis import Redis

from repolume_worker.analysis_queue import RedisAnalysisQueue

pytestmark = pytest.mark.integration


def test_reads_and_acknowledges_real_stream_delivery() -> None:
    redis_url = environ["REPOLUME_TEST_REDIS_URL"]
    stream = f"repolume:test:worker:{uuid4()}"
    group = f"test-workers-{uuid4()}"
    redis = Redis.from_url(redis_url, decode_responses=True)
    queue = RedisAnalysisQueue(redis, stream_name=stream, consumer_group=group)
    try:
        queue.ensure_consumer_group()
        redis.xadd(
            stream,
            {
                "schema_version": "1.0",
                "event_id": str(uuid4()),
                "analysis_id": "analysis_redis",
                "provider": "github",
                "owner": "octocat",
                "repository": "Hello-World",
                "ref": "main",
            },
        )

        messages = queue.read("worker-1", block_ms=100)
        queue.acknowledge(messages[0])
        pending = redis.xpending(stream, group)

        assert len(messages) == 1
        assert messages[0].analysis_id == "analysis_redis"
        assert pending["pending"] == 0
    finally:
        redis.delete(stream)
        redis.close()
