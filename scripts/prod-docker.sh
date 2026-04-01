#!/bin/bash
set -e

# Usage: ./prod-docker.sh [-c commit_hash]
COMMIT_HASH="10d9edd824903866c7248088d2ebe324ba2a3f14"

while getopts c: flag
do
    case "${flag}" in
        c) COMMIT_HASH=${OPTARG};;
    esac
done

echo "🌟 Starting Production Deployment for Aureus Docker Services..."
echo "--------------------------------------------------------"

PROD_SOURCE_DIR="../../prod/aureus"

if [ ! -d "$PROD_SOURCE_DIR" ]; then
    echo "⚠️ Prod directory not found at $PROD_SOURCE_DIR."
    echo "Please clone the repo there first: git clone http://localhost:13231/aureus/aureus.git $PROD_SOURCE_DIR"
    exit 1
fi

echo "📦 Entering Prod Source directory ($PROD_SOURCE_DIR)..."
cd $PROD_SOURCE_DIR

echo "📥 Fetching latest code from Local Git Server..."
git config --global --add safe.directory "$PWD"
git fetch origin

if [ -n "$COMMIT_HASH" ]; then
    echo "🎯 Checking out specific version: $COMMIT_HASH"
    git checkout $COMMIT_HASH
else
    echo "🔄 No specific commit provided. Pulling latest from debug..."
    git pull origin debug
fi

# Go back to config directory where docker-compose.prod.yml lives
cd ../../workspace/aureus

echo "🔨 Building Prod logic containers..."
docker compose -f docker-compose.prod.yml --env-file .env.prod build aureus-gateway aureus-db-writer aureus-signal aureus-strategy-executor aureus-dashboard-api

echo "🚀 Starting / Restarting Production Docker services..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d redis timescaledb aureus-gateway aureus-db-writer aureus-signal aureus-strategy-executor aureus-dashboard-api

echo "--------------------------------------------------------"
echo "✅ Prod Docker Deployment completed successfully!"
