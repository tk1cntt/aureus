# Aureus Implementation Plan - Phase 4: AI Brain & Decision Worker

This phase transforms technical signals into intelligent decisions using local Large Language Models.

## User Review Required

> [!CAUTION]
> - **GPU Resources**: The `aureus-ai-worker` requires significant VRAM (vLLM serving).
> - **Inference Latency**: AI analysis takes time (1-5s). Signals will be processed asynchronously; the technical signal triggers instantly, while AI validation follows.

## Proposed Changes

### AI Worker (Inference)

#### [NEW] [services/aureus-ai-worker/](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-ai-worker/)
- Implement a worker that listens to `aureus-ai-tasks` stream.
- Setup vLLM engine to serve models (e.g., DeepSeek-7B or Llama-3).
- Implement a **Prompt Factory** to build structured prompts containing:
    - Technical indicators (ZigZag, EMA, ATR).
    - Market regime (Trend, Volatility).
    - Recent price action context.

### Signal Engine Integration

#### [NEW] [services/aureus-signal/engine/ai_validator.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/engine/ai_validator.py)
- Logic to decide *when* to trigger an AI check (e.g., only on breakout or specific pattern).
- Send analysis requests to Redis and await result or proceed with fallback.

## Verification Plan

### Automated Tests
- **Mock Inference**: Test the Signal Engine's ability to handle AI response delays or failures.
- **Prompt Testing**: Verify that the generated prompts are valid JSON or follow the required model format.

### Manual Verification
- Inspect the `aureus_ai_analysis` table for logical consistency in the LLM's `debate_log` and `narrative`.
