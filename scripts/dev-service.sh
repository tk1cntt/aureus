#!/bin/bash
set -e

echo "🚀 Starting Aureus Dev Docker Services..."
echo "--------------------------------------------------------"

# Ensure we are in the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Optional: Add _dev suffix to container names on the fly if needed,
# but using docker-compose.dev.yml is already isolated from prod source paths.

echo "🔨 Building Dev containers..."
docker compose -f docker-compose.dev.yml --env-file .env build aureus-gateway-dev aureus-db-writer-dev aureus-signal-dev aureus-dashboard-api-dev

echo "🚀 Starting Dev services..."
docker compose -f docker-compose.dev.yml --env-file .env up -d redis-dev timescaledb-dev aureus-gateway-dev aureus-db-writer-dev aureus-signal-dev aureus-dashboard-api-dev

echo "--------------------------------------------------------"
echo "✅ Dev Docker Services are running!"
