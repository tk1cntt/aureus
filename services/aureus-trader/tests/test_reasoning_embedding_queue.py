import json

import pytest

from reasoning_embeddings import REASONING_EMBEDDING_QUEUE_KEY, ReasoningEmbeddingWorker, enqueue_reasoning_embedding_job


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


class FakeWorkerRedis:
    def __init__(self, payload):
        self.payload = payload
        self.deleted = []

    async def xread(self, streams, count=1, block=10000):
        return [(REASONING_EMBEDDING_QUEUE_KEY, [("1-0", {"job": json.dumps(self.payload)})])]

    async def xdel(self, stream, message_id):
        self.deleted.append((stream, message_id))
        return 1


class FakeWorkerPool:
    def __init__(self):
        self.conn = object()

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_worker_consumes_job_and_acknowledges_after_success(monkeypatch):
    redis = FakeWorkerRedis({
        "entry_id": 123,
        "trace_id": "trace-123",
        "sources": {"reasoning_text": "CISD aligned"},
    })
    pool = FakeWorkerPool()
    calls = []
    client = object()

    async def fake_embed(conn, entry_id, sources, embed_client):
        calls.append((conn, entry_id, sources, embed_client))
        return 1

    monkeypatch.setattr("reasoning_embeddings.embed_reasoning_entry", fake_embed)
    worker = ReasoningEmbeddingWorker(pool, redis, client=client)

    assert await worker.process_once(timeout=0.1) is True
    assert calls == [(pool.conn, 123, {"reasoning_text": "CISD aligned"}, client)]
    assert redis.deleted == [(REASONING_EMBEDDING_QUEUE_KEY, "1-0")]


@pytest.mark.asyncio
async def test_worker_embedding_exception_leaves_job_retryable(monkeypatch):
    redis = FakeWorkerRedis({
        "entry_id": 123,
        "trace_id": "trace-123",
        "sources": {"reasoning_text": "CISD aligned"},
    })

    async def fake_embed(conn, entry_id, sources, client):
        raise RuntimeError("embedding down")

    monkeypatch.setattr("reasoning_embeddings.embed_reasoning_entry", fake_embed)
    worker = ReasoningEmbeddingWorker(FakeWorkerPool(), redis, client=object())

    assert await worker.process_once(timeout=0.1) is False
    assert redis.deleted == []
