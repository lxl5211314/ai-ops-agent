@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
if not exist logs mkdir logs

set ACTION=%~1
set ARG2=%~2

if "%ACTION%"=="start"   goto :start
if "%ACTION%"=="stop"    goto :stop
if "%ACTION%"=="restart" goto :restart
if "%ACTION%"=="status"  goto :status

echo ============================================
echo   小龙 AI Ops Agent - 服务管理脚本
echo ============================================
echo.
echo   service.bat start        启动 基础设施 + 后端 + 前端
echo   service.bat stop         停止 后端 + 前端（容器保留）
echo   service.bat stop all     停止 后端 + 前端 + 基础设施容器
echo   service.bat restart      重启 后端 + 前端
echo   service.bat status       查看各组件状态
echo.
exit /b 1

:status
echo [基础设施容器]
docker compose ps
echo.
echo [应用端口]
call :portcheck 8000 后端uvicorn
call :portcheck 5173 前端vite
exit /b 0

:portcheck
set P=%~1
set NAME=%~2
netstat -ano | findstr /r /c:":%P% .*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo   %P% %NAME%: 未运行
) else (
    echo   %P% %NAME%: 运行中
)
exit /b 0

:start
echo [1/3] 启动基础设施容器...
docker compose up -d mysql etcd minio milvus neo4j

netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [2/3] 启动后端 :8000...
    powershell -NoProfile -Command "Start-Process -FilePath cmd -ArgumentList '/c uvicorn main:app --app-dir src --host 127.0.0.1 --port 8000' -WorkingDirectory '%CD%\backend' -RedirectStandardOutput '%CD%\logs\backend.log' -RedirectStandardError '%CD%\logs\backend.err' -WindowStyle Hidden"
) else (
    echo [2/3] 后端 :8000 已在运行，跳过
)

netstat -ano | findstr /r /c:":5173 .*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [3/3] 启动前端 :5173...
    powershell -NoProfile -Command "Start-Process -FilePath cmd -ArgumentList '/c npm run dev' -WorkingDirectory '%CD%\frontend' -RedirectStandardOutput '%CD%\logs\frontend.log' -RedirectStandardError '%CD%\logs\frontend.err' -WindowStyle Hidden"
) else (
    echo [3/3] 前端 :5173 已在运行，跳过
)

echo 等待后端就绪...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 60;$i++){ try{ Invoke-WebRequest 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 3 | Out-Null; $ok=$true; break }catch{ Start-Sleep 1 } }; if($ok){ Write-Output '后端健康检查 OK' } else { Write-Output '后端健康检查超时, 查看 logs/backend.err' }"

echo.
echo ============================================
echo   启动完成
echo   前端: http://localhost:5173
echo   后端: http://localhost:8000/api/v1/health
echo   日志: logs/backend.log 和 logs/frontend.log
echo ============================================
exit /b 0

:stop
echo [1/2] 停止后端+前端...
powershell -NoProfile -Command "$l=Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue; if($l){ $l | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; Write-Output '已停止 8000 后端 / 5173 前端' } else { Write-Output '后端/前端均未运行' }"

if /i "%ARG2%"=="all" (
    echo [2/2] 停止基础设施容器...
    docker compose stop
) else (
    echo [2/2] 基础设施容器保留运行, 一起停用: service.bat stop all
)
exit /b 0

:restart
call :stop
timeout /t 2 /nobreak >nul
call :start
exit /b 0
