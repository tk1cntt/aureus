#!/usr/bin/env bash
set -euo pipefail

CONTAINER="aureus-signal-dev"
EXPECTED="shadow"
LOG_WINDOW_MINUTES="${1:-30}"

echo "[1/4] Kiểm tra container tồn tại..."
if ! docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "❌ Không tìm thấy container: $CONTAINER"
  exit 1
fi

echo "[2/4] Kiểm tra container đang chạy..."
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "⚠ Container chưa chạy. Bạn hãy restart trước:"
  echo "   docker restart $CONTAINER"
  exit 2
fi

echo "[3/4] Kiểm tra env AUREUS_STRUCTURE_OPT_MODE..."
ACTUAL=$(docker exec "$CONTAINER" printenv AUREUS_STRUCTURE_OPT_MODE 2>/dev/null || true)
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "❌ Env chưa đúng. expected='$EXPECTED', actual='${ACTUAL:-<empty>}'"
  exit 3
fi
echo "✅ Env OK: AUREUS_STRUCTURE_OPT_MODE=$ACTUAL"

echo "[4/4] Kiểm tra mismatch trong log ${LOG_WINDOW_MINUTES} phút gần nhất..."
LOGS=$(docker logs --since "${LOG_WINDOW_MINUTES}m" "$CONTAINER" 2>&1 || true)

MISMATCH_COUNT=$(printf "%s" "$LOGS" | grep -Eic 'mismatch|shadow.*diff|diff_fields' || true)

if [[ "$MISMATCH_COUNT" -eq 0 ]]; then
  echo "✅ Không thấy mismatch marker trong ${LOG_WINDOW_MINUTES} phút gần nhất."
else
  echo "⚠ Phát hiện $MISMATCH_COUNT dòng có thể là mismatch marker."
  echo "--- Mismatch excerpts ---"
  printf "%s\n" "$LOGS" | grep -Ei 'mismatch|shadow.*diff|diff_fields' | tail -n 30 || true
  echo "--- End excerpts ---"
fi

echo "\nDone."
