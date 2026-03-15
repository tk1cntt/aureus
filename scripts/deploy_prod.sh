#!/bin/bash
set -e

# Usage: ./deploy_prod.sh [-c commit_hash]
COMMIT_HASH=""

while getopts c: flag
do
    case "${flag}" in
        c) COMMIT_HASH=${OPTARG};;
    esac
done

echo "🌟 Starting Production Deployment for Aureus Live Engine..."
echo "--------------------------------------------------------"

# 1. CD to the Prod code directory (which is OUTSIDE the docker-compose path)
# Assuming directory structure:
# /mnt/x/Openclaw/aureus/workspace/aureus/ (Dev Code)
# /mnt/x/Openclaw/aureus/prod/aureus/ (Prod Code)
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

# 2. Go back to config directory where docker-compose.prod.yml lives
cd ../../workspace/aureus

# 3. Build Web and API using the Prod compose
echo "🔨 Building containers..."
docker compose -f docker-compose.prod.yml --env-file .env.prod build

# 4. Restart services gracefully
echo "🚀 Starting / Restarting production services..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 5. Native Native Build for Dashboard Web (Plan 2: Outside Docker)
echo "🌐 Deploying Web Dashboard (Native Node.js)..."
WEB_DIR="../../prod/aureus/workspace/aureus/services/aureus-dashboard/web"

if [ -d "$WEB_DIR" ]; then
    cd $WEB_DIR
    echo "📦 Installing npm dependencies for Production..."
    npm install --prefer-offline --no-audit --no-fund --legacy-peer-deps
    
    echo "🏗️ Building NextJS Application..."
    export NEXT_PUBLIC_API_URL="http://localhost:${API_PORT:-8001}/api/v1"
    npm run build
    
    echo "🚀 Starting Web Service directly via PM2..."
    # Install pm2 globally if not installed
    if ! command -v pm2 &> /dev/null; then
        echo "🔧 Installing pm2 globally..."
        npm install -g pm2
    fi
    
    # Run or Restart Next.js server in background using PM2
    if pm2 describe aureus-web > /dev/null 2>&1; then
        echo "🔄 Web service is already running. Restarting to apply changes..."
        PORT=12321 pm2 restart aureus-web --update-env
    else
        echo "🆕 Web service not found. Starting for the first time..."
        PORT=12321 pm2 start npm --name "aureus-web" -- run start
    fi
    pm2 save
    
    echo "✅ Web Dashboard running as PM2 service 'aureus-web' on port 12321."
else
    echo "⚠️ Web directory not found, skipping frontend deployment."
fi

cd /mnt/e/Openclaw/aureus/workspace/aureus

echo "--------------------------------------------------------"
echo "✅ Deployment completed successfully on Production Version!"
