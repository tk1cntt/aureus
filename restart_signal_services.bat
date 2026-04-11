@echo off
echo ========================================
echo Restarting Aureus Signal Services
echo ========================================

cd /d D:\Aureus

echo.
echo [1/2] Restarting aureus-signal-dev...
docker compose -f docker-compose.dev.yml restart aureus-signal-dev

echo.
echo [2/2] Restarting aureus-strategy-executor-dev...
docker compose -f docker-compose.dev.yml restart aureus-strategy-executor-dev

echo.
echo ========================================
echo Checking service status...
echo ========================================
docker compose -f docker-compose.dev.yml ps

echo.
echo ========================================
echo Viewing recent logs (aureus-signal-dev)...
echo ========================================
docker compose -f docker-compose.dev.yml logs --tail=20 aureus-signal-dev

echo.
echo ========================================
echo Viewing recent logs (aureus-strategy-executor-dev)...
echo ========================================
docker compose -f docker-compose.dev.yml logs --tail=20 aureus-strategy-executor-dev

echo.
echo Done! Press any key to exit...
pause >nul
