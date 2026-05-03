import json
import urllib.error
from unittest.mock import AsyncMock, patch

import pytest

from reasoning_embeddings import (
    ReasoningEmbeddingClient,
    ReasoningEmbeddingError,
    select_embedding_sources,
    semantic_search_reasoning_entries,
    vector_to_pg,
)
from scripts.backfill_reasoning_embeddings import backfill


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeConn:
    def __init__(self):
        self.calls = []

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return [{"id": 1, "distance": 0.1}]


def test_client_discovers_openai_embedding_contract():
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, req.get_method(), req.data))
        if req.get_method() == "GET":
            return FakeResponse({"status": "ok"})
        return FakeResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    client = ReasoningEmbeddingClient(base_url="http://localhost:8005")
    with patch("urllib.request.urlopen", fake_urlopen):
        client.discover()
        assert client.embed("CISD sweep aligned") == [0.1, 0.2, 0.3]

    assert any(url.endswith("/health") for url, method, _ in calls if method == "GET")
    assert any(url.endswith("/v1/embeddings") for url, method, _ in calls if method == "POST")


def test_client_falls_back_to_embed_contract():
    def fake_urlopen(req, timeout):
        if req.get_method() == "GET":
            return FakeResponse({"status": "ok"})
        if req.full_url.endswith("/v1/embeddings"):
            raise urllib.error.HTTPError(req.full_url, 404, "missing", {}, None)
        return FakeResponse({"embedding": [1, 2, 3]})

    client = ReasoningEmbeddingClient(base_url="http://localhost:8005")
    with patch("urllib.request.urlopen", fake_urlopen):
        assert client.embed("fallback text") == [1.0, 2.0, 3.0]
        assert client.embedding_path == "/embed"


def test_client_rejects_malformed_vector():
    client = ReasoningEmbeddingClient()
    with patch.object(client, "_request_json", return_value={"vector": [1.0, "bad"]}):
        with pytest.raises(ReasoningEmbeddingError):
            client.embed("bad vector")


def test_select_embedding_sources_skips_digest_fields():
    row = {
        "reasoning_text": "real reasoning",
        "prompt_text": "raw prompt",
        "context_text": "raw context",
        "prompt_digest": "abc123",
        "decision_digest": "def456",
        "input_context_hash": "hash789",
    }
    sources = select_embedding_sources(row)
    assert sources == {
        "reasoning_text": "real reasoning",
        "prompt_text": "raw prompt",
        "context_text": "raw context",
    }
    assert "abc123" not in sources.values()
    assert "hash789" not in sources.values()


@pytest.mark.asyncio
async def test_semantic_search_uses_parameterized_pgvector_query():
    conn = FakeConn()

    class Client:
        def embed(self, text):
            assert text == "similar CISD setup"
            return [0.1, 0.2]

    rows = await semantic_search_reasoning_entries(conn, "similar CISD setup", limit=5, client=Client())
    assert rows[0]["id"] == 1
    query, args = conn.calls[0]
    assert "reasoning_embedding <=> $1::vector" in query
    assert args == ("[0.1,0.2]", 5)


def test_vector_to_pg_rejects_non_finite_values():
    with pytest.raises(ReasoningEmbeddingError):
        vector_to_pg([0.1, float("nan")])


@pytest.mark.asyncio
async def test_backfill_reports_hash_only_prompt_context_unavailable(monkeypatch):
    calls = []

    class FakePool:
        def __init__(self):
            self.conn = FakeBackfillConn()

        def acquire(self):
            return FakeAcquire(self.conn)

        async def close(self):
            pass

    class FakeAcquire:
        def __init__(self, conn):
            self.conn = conn

        async def __aenter__(self):
            return self.conn

        async def __aexit__(self, *args):
            pass

    class FakeBackfillConn:
        async def execute(self, *args):
            calls.append(("execute", args))
            return "OK"

        async def fetch(self, *args):
            return [{
                "id": 10,
                "reasoning_text": None,
                "prompt_text": None,
                "context_text": None,
                "prompt_digest": "digest-only",
                "decision_digest": "decision-only",
                "input_context_hash": "hash-only",
            }]

    class Client:
        model = None

        def embed(self, text):
            raise AssertionError("hash/digest must not be embedded")

    async def fake_create_pool(*args, **kwargs):
        return FakePool()

    monkeypatch.setattr("scripts.backfill_reasoning_embeddings.verify_embedding_service", lambda base_url: Client())
    monkeypatch.setattr("scripts.backfill_reasoning_embeddings.asyncpg.create_pool", fake_create_pool)
    monkeypatch.setattr("scripts.backfill_reasoning_embeddings._ensure_schema", AsyncMock())
    monkeypatch.setattr("scripts.backfill_reasoning_embeddings._dsn", lambda: "postgresql://test")

    stats = await backfill(limit=1)

    assert stats["updated_rows"] == 0
    assert stats["skipped_rows"] == 1
    assert stats["unavailable_raw_prompt_context"] == 1
