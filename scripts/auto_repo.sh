#!/bin/bash
set -x

# 1. Start Gitea container
docker compose -f docker-compose-gitea.yml up -d

# 2. Wait for Gitea to respond (HTTP 200 or 404 - anything but connection refused)
echo "Waiting for Gitea HTTP..."
until curl -s http://localhost:13231 >/dev/null; do
    sleep 2
done
sleep 5 # Extra safety buffer for initialization

# 3. Create Aurora repository via Gitea API
echo "Creating repository..."
curl -s -X POST http://admin:adminpassword@localhost:13231/api/v1/user/repos \
    -H "Content-Type: application/json" \
    -d '{"name": "aureus", "private": true, "description": "Aureus Source Code"}'

# 4. Push local source code
echo "Configuring git and pushing..."
git config --global user.email "admin@localhost"
git config --global user.name "Aureus Admin"

# Remove Old origin_gitea if exists
git remote remove origin_gitea 2>/dev/null || true

# Add new Remote origin with auth tokens inline
git remote add origin_gitea http://admin:adminpassword@localhost:13231/admin/aureus.git

# Determine if we are on main or master
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Force pushing the current branch to 'main' on Gitea
git push -u origin_gitea ${CURRENT_BRANCH}:main

echo "Deployment Auto-Setup Finished Successfully!"
