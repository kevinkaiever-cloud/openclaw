@echo off
chcp 65001 >nul
set OPENCLAW_HOME=%USERPROFILE%\.openclaw
set SRC=%~dp0openclaw.windows.example.json
set DST=%OPENCLAW_HOME%\openclaw.json

if not exist "%OPENCLAW_HOME%" mkdir "%OPENCLAW_HOME%"
if exist "%DST%" (
  echo 已存在配置文件: %DST%
  echo 若需重置，请先删除该文件再运行本脚本。
  pause
  exit /b 0
)
copy /Y "%SRC%" "%DST%" >nul
echo 已复制示例配置到: %DST%
echo 请编辑 %OPENCLAW_HOME%\.env 填入 DEEPSEEK_API_KEY 后启动网关。
pause
