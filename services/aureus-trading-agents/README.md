# Aureus TradingAgents Compatibility Validation

Phase 21 validation container for TradingAgents decision provider compatibility.

## Setup

```bash
cp .env.example .env
# Fill in ALPHA_VANTAGE_API_KEY
```

## Run Test

```bash
docker build -t aureus-ta-validation:test .
mkdir -p output
docker run --rm --network host --env-file .env -v $(pwd)/output:/app/output aureus-ta-validation:test
```
