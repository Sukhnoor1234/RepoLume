"""Redis integration coverage for transactional outbox publication."""

from os import environ
from uuid import uuid4

import pytest
from redis import Redis
from sqlalchemy import create_engine

from repolume_api.analysis_outbox import AnalysisOutboxStorage, RedisOutboxPublisher
from repolume_api.analysis_storage import AnalysisStorage
from repolume_api.database_models import Base
from repolume_api.repositories import RepositoryReference

pytestmark = pytest.mark.integration


def test_publishes_pending_request_to_real_redis_stream() -> None:
    redis_url = environ["REPOLUME_TEST_REDIS_URL"]
    stream = f"repolume:test:api:{uuid4()}"
    redis = Redis.from_url(redis_url, decode_responses=True)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        AnalysisStorage(engine).create_job(
            "analysis_redis",
            RepositoryReference(owner="octocat", repository="Hello-World", ref="main"),
        )

        published = RedisOutboxPublisher(
            AnalysisOutboxStorage(engine), redis, stream_name=stream
        ).publish_batch()
        messages = redis.xrange(stream)

        assert published == 1
        assert len(messages) == 1
        assert messages[0][1]["analysis_id"] == "analysis_redis"
        assert messages[0][1]["schema_version"] == "1.0"
    finally:
        redis.delete(stream)
        Base.metadata.drop_all(engine)
        engine.dispose()
        redis.close()
