@echo off
chcp 65001 >nul
echo ========================================
echo   OpenClaw 网关启动
echo ========================================
echo.

cd /d "%~dp0"
set PATH=C:\Program Files\Git\bin;%PATH%

echo 正在启动网关（端口 18789）...
echo 启动后请访问: http://127.0.0.1:18789
echo 按 Ctrl+C 可停止
echo.

pnpm openclaw gateway --port 18789 --verbose

pause
