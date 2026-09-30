@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   小龙 AI Ops Agent - 停止
echo ============================================
echo.
echo [1/2] 停止后端+前端...
powershell -NoProfile -Command "$l=Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue; if($l){ $l | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; Write-Output '已停止 8000 后端 / 5173 前端' } else { Write-Output '后端/前端均未运行' }"

echo [2/2] 停止基础设施容器...
docker compose stop

echo.
echo ============================================
echo   已全部停止（数据保留在数据卷中）
echo   重新启动: start.bat
echo ============================================
pause
exit /b 0
