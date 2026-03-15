#!/bin/bash
set -e

echo "🔄 Synchronizing Database from Prod to Dev..."
echo "--------------------------------------------------------"

# Ensure containers are running
if ! docker ps | grep -q temp_prod_db; then
    echo "❌ Prod DB (temp_prod_db) is not running!"
    exit 1
fi

if ! docker ps | grep -q aureus_timescaledb_dev; then
    echo "❌ Dev DB (aureus_timescaledb_dev) is not running!"
    exit 1
fi

echo "📦 1. Exporting data from Prod DB..."
docker exec temp_prod_db pg_dump -U aureus -F c -O -x aureus > /tmp/aureus_prod_dump.bak

echo "🚚 2. Copying dump to Dev DB container..."
docker cp /tmp/aureus_prod_dump.bak aureus_timescaledb_dev:/tmp/aureus_prod_dump.bak

echo "📥 3. Restoring data into Dev DB..."
# We use --clean to drop existing records before restoring. Ignore errors if tables don't exist yet.
docker exec aureus_timescaledb_dev pg_restore -U aureus -d aureus -O -x --clean /tmp/aureus_prod_dump.bak || true

echo "🧹 4. Cleaning up temporary files..."
rm -f /tmp/aureus_prod_dump.bak
docker exec aureus_timescaledb_dev rm -f /tmp/aureus_prod_dump.bak

echo "--------------------------------------------------------"
echo "✅ Database synchronization complete! Dev DB is now a clone of Prod DB."
