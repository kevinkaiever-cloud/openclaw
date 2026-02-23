# 上传 openclaw 项目到 GitHub (kevinkaiever-cloud)
# 使用前请先在 https://github.com/new 创建名为 openclaw 的仓库

$git = "C:\Program Files\Git\cmd\git.exe"
$repoPath = "C:\Users\Administrator\Desktop\openclaw"

Set-Location $repoPath

# 添加你的 GitHub 仓库为远程（保留 origin 指向原项目）
Write-Host "添加远程仓库 kevinkaiever-cloud/openclaw..." -ForegroundColor Cyan
& $git remote remove my-github 2>$null  # 若已存在则移除
& $git remote add my-github https://github.com/kevinkaiever-cloud/openclaw.git

# 添加所有更改
Write-Host "添加文件..." -ForegroundColor Cyan
& $git add -A

# 提交
Write-Host "提交更改..." -ForegroundColor Cyan
& $git commit -m "Update: 本地修改与配置" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "无新更改需要提交，或已有未提交更改。" -ForegroundColor Yellow
}

# 推送到你的 GitHub
Write-Host "推送到 GitHub..." -ForegroundColor Cyan
& $git push -u my-github main
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n完成！项目已上传到 https://github.com/kevinkaiever-cloud/openclaw" -ForegroundColor Green
} else {
    Write-Host "`n推送失败。请确保：" -ForegroundColor Red
    Write-Host "1. 已在 GitHub 创建 https://github.com/kevinkaiever-cloud/openclaw 仓库" -ForegroundColor Red
    Write-Host "2. 已配置 Git 凭证（用户名 + 个人访问令牌）" -ForegroundColor Red
}
