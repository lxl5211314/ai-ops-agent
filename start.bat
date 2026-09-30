@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

echo ============================================
echo   小龙 AI Ops Agent - 启动
echo ============================================
echo.
echo [1/4] 启动基础设施容器...
docker compose up -d mysql etcd minio milvus neo4j

echo [2/4] 等待 MySQL 就绪...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 60;$i++){ try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',3307); $c.Close(); $ok=$true; break }catch{ Start-Sleep 1 } }; if($ok){ Write-Output 'MySQL 3307 就绪' } else { Write-Output 'MySQL 等待超时（如改过端口请检查 .env 的 MYSQL_HOST_PORT）' }"

netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [3/4] 启动后端 :8000...
    powershell -NoProfile -Command "Start-Process -FilePath cmd -ArgumentList '/c uvicorn main:app --app-dir src --host 127.0.0.1 --port 8000' -WorkingDirectory '%CD%\backend' -RedirectStandardOutput '%CD%\logs\backend.log' -RedirectStandardError '%CD%\logs\backend.err' -WindowStyle Hidden"
) else (
    echo [3/4] 后端 :8000 已在运行，跳过
)

netstat -ano | findstr /r /c:":5173 .*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [4/4] 启动前端 :5173...
    powershell -NoProfile -Command "Start-Process -FilePath cmd -ArgumentList '/c npm run dev' -WorkingDirectory '%CD%\frontend' -RedirectStandardOutput '%CD%\logs\frontend.log' -RedirectStandardError '%CD%\logs\frontend.err' -WindowStyle Hidden"
) else (
    echo [4/4] 前端 :5173 已在运行，跳过
)

echo 等待后端就绪...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 60;$i++){ try{ $r=Invoke-WebRequest 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 3; if($r.Content -notmatch 'degraded'){ $ok=$true; break } }catch{ Start-Sleep 1 } }; if($ok){ Write-Output '后端健康检查 OK' } else { Write-Output '后端健康检查超时, 查看 logs/backend.err' }"

echo.
echo ============================================
echo   启动完成
echo   前端: http://localhost:5173
echo   后端: http://localhost:8000/api/v1/health
echo   日志: logs/backend.log 和 logs/frontend.log
echo ============================================
pause
exit /b 0
