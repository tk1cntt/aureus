-- Quick 260503-a2k: Reasoning Bank embeddings
-- Adds pgvector columns and raw text capture fields for semantic search.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE aureus_reasoning_entries
    ADD COLUMN IF NOT EXISTS prompt_text TEXT,
    ADD COLUMN IF NOT EXISTS context_text TEXT,
    ADD COLUMN IF NOT EXISTS reasoning_embedding vector,
    ADD COLUMN IF NOT EXISTS prompt_embedding vector,
    ADD COLUMN IF NOT EXISTS context_embedding vector,
    ADD COLUMN IF NOT EXISTS embedding_model TEXT,
    ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ;

DO $$
BEGIN
    BEGIN
        CREATE INDEX IF NOT EXISTS idx_reasoning_entries_reasoning_embedding
            ON aureus_reasoning_entries USING hnsw (reasoning_embedding vector_cosine_ops)
            WHERE reasoning_embedding IS NOT NULL;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'hnsw index unavailable for reasoning_embedding: %', SQLERRM;
    END;

    BEGIN
        CREATE INDEX IF NOT EXISTS idx_reasoning_entries_prompt_embedding
            ON aureus_reasoning_entries USING hnsw (prompt_embedding vector_cosine_ops)
            WHERE prompt_embedding IS NOT NULL;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'hnsw index unavailable for prompt_embedding: %', SQLERRM;
    END;

    BEGIN
        CREATE INDEX IF NOT EXISTS idx_reasoning_entries_context_embedding
            ON aureus_reasoning_entries USING hnsw (context_embedding vector_cosine_ops)
            WHERE context_embedding IS NOT NULL;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'hnsw index unavailable for context_embedding: %', SQLERRM;
    END;
END $$;

COMMENT ON COLUMN aureus_reasoning_entries.prompt_text IS 'Optional raw prompt text captured for future semantic embedding; never derived from prompt_digest';
COMMENT ON COLUMN aureus_reasoning_entries.context_text IS 'Optional raw context text captured for future semantic embedding; never derived from input_context_hash';
COMMENT ON COLUMN aureus_reasoning_entries.reasoning_embedding IS 'pgvector embedding generated only from reasoning_text';
COMMENT ON COLUMN aureus_reasoning_entries.prompt_embedding IS 'pgvector embedding generated only from prompt_text';
COMMENT ON COLUMN aureus_reasoning_entries.context_embedding IS 'pgvector embedding generated only from context_text';
