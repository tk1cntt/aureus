"""Reasoning Bank embedding helpers."""
import asyncio
import json
import math
import urllib.error
import urllib.request
from datetime import datetime, timezone

DEFAULT_EMBEDDING_BASE_URL = "http://localhost:8005"
TEXT_SOURCE_FIELDS = ("reasoning_text", "prompt_text", "context_text")
DIGEST_FIELDS = {"prompt_digest", "decision_digest", "input_context_hash"}


class ReasoningEmbeddingError(RuntimeError):
    """Raised when embedding service cannot return a usable vector."""


class ReasoningEmbeddingClient:
    def __init__(self, base_url=DEFAULT_EMBEDDING_BASE_URL, model=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.embedding_path = None

    def _request_json(self, method, path, payload=None):
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)

    def discover(self):
        health_errors = []
        for path in ("/health", "/v1/models", "/docs"):
            try:
                self._request_json("GET", path)
                return True
            except Exception as exc:
                health_errors.append(f"{path}: {exc}")
        raise ReasoningEmbeddingError("embedding service not reachable: " + "; ".join(health_errors))

    def embed(self, text):
        if not isinstance(text, str) or not text.strip():
            raise ReasoningEmbeddingError("embedding text must be non-empty string")
        if self.embedding_path:
            return self._embed_path(self.embedding_path, text)
        errors = []
        for path in ("/v1/embeddings", "/embed"):
            try:
                vector = self._embed_path(path, text)
                self.embedding_path = path
                return vector
            except Exception as exc:
                errors.append(f"{path}: {exc}")
        raise ReasoningEmbeddingError("embedding endpoint discovery failed: " + "; ".join(errors))

    def _embed_path(self, path, text):
        if path == "/v1/embeddings":
            payload = {"input": text}
            if self.model:
                payload["model"] = self.model
        else:
            payload = {"text": text}
            if self.model:
                payload["model"] = self.model
        response = self._request_json("POST", path, payload)
        return _extract_vector(response)


def _extract_vector(response):
    if isinstance(response, dict):
        if isinstance(response.get("data"), list) and response["data"]:
            candidate = response["data"][0].get("embedding") if isinstance(response["data"][0], dict) else None
        else:
            candidate = response.get("embedding", response.get("vector"))
    else:
        candidate = response
    if not isinstance(candidate, list) or not candidate:
        raise ReasoningEmbeddingError("embedding response missing vector")
    vector = []
    for value in candidate:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ReasoningEmbeddingError("embedding vector must contain finite numbers")
        vector.append(float(value))
    return vector


def verify_embedding_service(base_url=DEFAULT_EMBEDDING_BASE_URL):
    client = ReasoningEmbeddingClient(base_url=base_url)
    client.discover()
    return client


def select_embedding_sources(row):
    sources = {}
    for field in TEXT_SOURCE_FIELDS:
        value = row.get(field) if isinstance(row, dict) else None
        if isinstance(value, str) and value.strip():
            sources[field] = value.strip()
    return sources


def vector_to_pg(vector):
    _extract_vector(vector)
    return "[" + ",".join(str(float(v)) for v in vector) + "]"


async def semantic_search_reasoning_entries(conn, query_text, limit=10, client=None):
    safe_limit = int(limit)
    if safe_limit < 1 or safe_limit > 100:
        raise ValueError("limit must be between 1 and 100")
    client = client or ReasoningEmbeddingClient()
    vector = await _maybe_await(client.embed(query_text))
    vector_text = vector_to_pg(vector)
    return await conn.fetch(
        """
        SELECT id, trace_id, strategy_name, symbol, reasoning_text,
               reasoning_embedding <=> $1::vector AS distance
        FROM aureus_reasoning_entries
        WHERE reasoning_embedding IS NOT NULL
        ORDER BY reasoning_embedding <=> $1::vector
        LIMIT $2
        """,
        vector_text,
        safe_limit,
    )


async def embed_reasoning_entry(conn, entry_id, sources, client=None):
    client = client or ReasoningEmbeddingClient()
    updates = {}
    if sources.get("reasoning_text"):
        updates["reasoning_embedding"] = await _maybe_await(client.embed(sources["reasoning_text"]))
    if sources.get("prompt_text"):
        updates["prompt_embedding"] = await _maybe_await(client.embed(sources["prompt_text"]))
    if sources.get("context_text"):
        updates["context_embedding"] = await _maybe_await(client.embed(sources["context_text"]))
    if not updates:
        return 0
    await conn.execute(
        """
        UPDATE aureus_reasoning_entries
        SET reasoning_embedding = COALESCE($2::vector, reasoning_embedding),
            prompt_embedding = COALESCE($3::vector, prompt_embedding),
            context_embedding = COALESCE($4::vector, context_embedding),
            embedding_model = COALESCE($5, embedding_model),
            embedded_at = $6,
            updated_at = now()
        WHERE id = $1
        """,
        entry_id,
        vector_to_pg(updates["reasoning_embedding"]) if "reasoning_embedding" in updates else None,
        vector_to_pg(updates["prompt_embedding"]) if "prompt_embedding" in updates else None,
        vector_to_pg(updates["context_embedding"]) if "context_embedding" in updates else None,
        client.model,
        datetime.now(timezone.utc),
    )
    return len(updates)


async def _maybe_await(value):
    if asyncio.iscoroutine(value):
        return await value
    return value
