# OpenClaw 网关启动脚本（已优化本地网络连接）
$env:PATH = "C:\Program Files\Git\bin;$env:PATH"
Set-Location $PSScriptRoot
& "$env:APPDATA\npm\pnpm.cmd" openclaw gateway --port 18789 --verbose
