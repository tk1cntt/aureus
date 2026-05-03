"""Reasoning Bank embedding helpers."""
import asyncio
import json
import logging
import math
import urllib.error
import urllib.request
from datetime import datetime, timezone

DEFAULT_EMBEDDING_BASE_URL = "http://host.docker.internal:8005"
TEXT_SOURCE_FIELDS = ("reasoning_text", "prompt_text", "context_text")
DIGEST_FIELDS = {"prompt_digest", "decision_digest", "input_context_hash"}
REASONING_EMBEDDING_QUEUE_KEY = "aureus:reasoning:embedding_jobs"

logger = logging.getLogger(__name__)


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


async def enqueue_reasoning_embedding_job(redis_client, entry_id, sources, trace_id, queue_key=REASONING_EMBEDDING_QUEUE_KEY):
    clean_sources = select_embedding_sources(sources)
    if not clean_sources:
        return False
    job = {
        "entry_id": int(entry_id),
        "trace_id": str(trace_id),
        "sources": clean_sources,
    }
    try:
        payload = json.dumps(job, ensure_ascii=False)
        if hasattr(redis_client, "xadd"):
            await _maybe_await(redis_client.xadd(queue_key, {"job": payload}))
        else:
            await _maybe_await(redis_client.rpush(queue_key, payload))
        return True
    except Exception as exc:
        logger.warning("Reasoning embedding enqueue failed for trace_id=%s: %s", trace_id, exc)
        return False


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
        SELECT re.id,
               re.trace_id,
               COALESCE(tj.strategy_name, re.strategy_name) AS strategy_name,
               COALESCE(tj.symbol, re.symbol) AS symbol,
               COALESCE(tj.direction, re.direction) AS direction,
               ts.timeframe,
               ts.signal_schema_version,
               ts.atr,
               ts.session,
               ts.cisd_m5,
               ts.cisd_m15,
               ts.cisd_m30,
               ts.cisd_h1,
               re.reasoning_text,
               re.reasoning_embedding <=> $1::vector AS distance
        FROM aureus_reasoning_entries re
        LEFT JOIN aureus_trade_journal tj ON tj.id = re.trade_journal_id
        LEFT JOIN aureus_trade_signal_snapshots ts ON ts.id = re.signal_snapshot_id
        WHERE re.reasoning_embedding IS NOT NULL
        ORDER BY re.reasoning_embedding <=> $1::vector
        LIMIT $2
        """,
        vector_text,
        safe_limit,
    )


def _empty_strategy_insights(strategy_name, symbol=None, direction=None):
    return {
        "strategy_name": strategy_name,
        "symbol": symbol,
        "direction": direction,
        "sample_size": 0,
        "success_rate": None,
        "avg_reward": None,
        "avg_pnl_pips": None,
        "recent_lessons": [],
        "similar_lessons": [],
    }


def _trim_lesson(value, max_len=280):
    text = " ".join(str(value or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _strategy_scope_where(start_index, symbol=None, direction=None, embedding=False):
    clauses = [f"COALESCE(tj.strategy_name, re.strategy_name) = ${start_index}"]
    args_offset = start_index
    if symbol:
        args_offset += 1
        clauses.append(f"COALESCE(tj.symbol, re.symbol) = ${args_offset}")
    if direction:
        args_offset += 1
        clauses.append(f"COALESCE(tj.direction, re.direction) = ${args_offset}")
    if embedding:
        clauses.append("re.reasoning_embedding IS NOT NULL")
    return " AND ".join(clauses)


async def fetch_strategy_reasoning_insights(conn, strategy_name, symbol=None, direction=None, limit=5, query_text=None, client=None):
    strategy_name = str(strategy_name or "").strip()
    if not strategy_name:
        raise ValueError("strategy_name is required")
    safe_limit = int(limit)
    if safe_limit < 1 or safe_limit > 20:
        raise ValueError("limit must be between 1 and 20")

    args = [strategy_name]
    if symbol:
        args.append(symbol)
    if direction:
        args.append(direction)
    where = _strategy_scope_where(1, symbol=symbol, direction=direction)
    insights = _empty_strategy_insights(strategy_name, symbol=symbol, direction=direction)

    stats = await conn.fetchrow(
        f"""
        SELECT count(*)::int AS sample_size,
               avg(CASE WHEN tj.result = 'WIN' THEN 1.0 WHEN tj.result = 'LOSS' THEN 0.0 ELSE NULL END)::float AS success_rate,
               avg(COALESCE(tj.pnl_pips, tj.pnl))::float AS avg_reward,
               avg(tj.pnl_pips)::float AS avg_pnl_pips
        FROM aureus_reasoning_entries re
        LEFT JOIN aureus_trade_journal tj ON tj.id = re.trade_journal_id
        LEFT JOIN aureus_trade_signal_snapshots ts ON ts.id = re.signal_snapshot_id
        WHERE {where}
        """,
        *args,
    )
    if stats:
        insights["sample_size"] = int(stats.get("sample_size") or 0)
        insights["success_rate"] = stats.get("success_rate")
        insights["avg_reward"] = stats.get("avg_reward")
        insights["avg_pnl_pips"] = stats.get("avg_pnl_pips")

    recent_rows = await conn.fetch(
        f"""
        SELECT re.reasoning_text
        FROM aureus_reasoning_entries re
        LEFT JOIN aureus_trade_journal tj ON tj.id = re.trade_journal_id
        LEFT JOIN aureus_trade_signal_snapshots ts ON ts.id = re.signal_snapshot_id
        WHERE {where}
          AND re.reasoning_text IS NOT NULL
        ORDER BY COALESCE(re.evaluated_at, re.created_at) DESC NULLS LAST, re.id DESC
        LIMIT ${len(args) + 1}
        """,
        *args,
        safe_limit,
    )
    insights["recent_lessons"] = [_trim_lesson(row.get("reasoning_text")) for row in recent_rows if row.get("reasoning_text")]

    if query_text:
        try:
            client = client or ReasoningEmbeddingClient()
            vector = await _maybe_await(client.embed(query_text))
            vector_text = vector_to_pg(vector)
            similar_args = [vector_text, *args, safe_limit]
            similar_where = _strategy_scope_where(2, symbol=symbol, direction=direction, embedding=True)
            rows = await conn.fetch(
                f"""
                SELECT re.reasoning_text, re.reasoning_embedding <=> $1::vector AS distance
                FROM aureus_reasoning_entries re
                LEFT JOIN aureus_trade_journal tj ON tj.id = re.trade_journal_id
                LEFT JOIN aureus_trade_signal_snapshots ts ON ts.id = re.signal_snapshot_id
                WHERE {similar_where}
                  AND re.reasoning_text IS NOT NULL
                ORDER BY re.reasoning_embedding <=> $1::vector
                LIMIT ${len(similar_args)}
                """,
                *similar_args,
            )
            insights["similar_lessons"] = [_trim_lesson(row.get("reasoning_text")) for row in rows if row.get("reasoning_text")]
        except Exception:
            insights["similar_lessons"] = []

    return insights


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
