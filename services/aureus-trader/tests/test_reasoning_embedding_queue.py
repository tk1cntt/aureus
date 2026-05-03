import json

import pytest

from reasoning_embeddings import REASONING_EMBEDDING_QUEUE_KEY, enqueue_reasoning_embedding_job


class FakeRedisStream:
    def __init__(self):
        self.calls = []

    async def xadd(self, key, fields):
        self.calls.append((key, fields))
        return "1-0"


class FailingRedisStream:
    async def xadd(self, key, fields):
        raise RuntimeError("redis down")


@pytest.mark.asyncio
async def test_enqueue_reasoning_embedding_job_writes_json_job_to_stream():
    redis = FakeRedisStream()

    result = await enqueue_reasoning_embedding_job(
        redis,
        entry_id=123,
        sources={"reasoning_text": "CISD aligned"},
        trace_id="trace-123",
    )

    assert result is True
    assert len(redis.calls) == 1
    key, fields = redis.calls[0]
    assert key == REASONING_EMBEDDING_QUEUE_KEY
    payload = json.loads(fields["job"])
    assert payload == {
        "entry_id": 123,
        "trace_id": "trace-123",
        "sources": {"reasoning_text": "CISD aligned"},
    }


@pytest.mark.asyncio
async def test_enqueue_reasoning_embedding_job_empty_sources_does_not_enqueue():
    redis = FakeRedisStream()

    result = await enqueue_reasoning_embedding_job(
        redis,
        entry_id=123,
        sources={},
        trace_id="trace-123",
    )

    assert result is False
    assert redis.calls == []


@pytest.mark.asyncio
async def test_enqueue_reasoning_embedding_job_redis_failure_returns_false():
    result = await enqueue_reasoning_embedding_job(
        FailingRedisStream(),
        entry_id=123,
        sources={"reasoning_text": "CISD aligned"},
        trace_id="trace-123",
    )

    assert result is False
