#!/bin/bash
set -e

echo "🌐 Starting Aureus Dev Web Dashboard..."
echo "--------------------------------------------------------"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_ROOT/services/aureus-dashboard/web"

if [ ! -d "$WEB_DIR" ]; then
    echo "⚠️ Web directory not found at $WEB_DIR"
    exit 1
fi

cd "$WEB_DIR"

echo "📦 Installing npm dependencies..."
# Using --legacy-peer-deps to avoid upstream unresolved peer dependency issues
npm install --no-fund --legacy-peer-deps

echo "🏗️ Starting NextJS Application in DEV mode..."
export NEXT_PUBLIC_API_URL="http://localhost:${DEV_API_PORT:-8002}/api/v1"
PORT=${DEV_WEB_PORT:-17222} npm run dev
