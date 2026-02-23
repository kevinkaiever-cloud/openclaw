# 验证 DeepSeek API Key 是否有效
# 用法: .\test-deepseek-key.ps1 [你的API密钥]
# 或先设置环境变量: $env:DEEPSEEK_API_KEY = "sk-xxx"; .\test-deepseek-key.ps1

param([string]$ApiKey = $env:DEEPSEEK_API_KEY)

if (-not $ApiKey) {
    Write-Host "错误: 请提供 API Key" -ForegroundColor Red
    Write-Host "用法: .\test-deepseek-key.ps1 sk-你的密钥"
    Write-Host "或: `$env:DEEPSEEK_API_KEY = 'sk-xxx'; .\test-deepseek-key.ps1"
    exit 1
}

$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $ApiKey"
}
$body = @{
    model = "deepseek-chat"
    messages = @(@{ role = "user"; content = "Hi" })
    max_tokens = 5
} | ConvertTo-Json -Depth 5

try {
    $r = Invoke-RestMethod -Uri "https://api.deepseek.com/v1/chat/completions" `
        -Method Post -Headers $headers -Body $body -TimeoutSec 15
    Write-Host "成功: API Key 有效" -ForegroundColor Green
    Write-Host ("回复: " + ($r.choices[0].message.content))
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    $errBody = $_.ErrorDetails.Message
    Write-Host "请求失败 (HTTP $statusCode)" -ForegroundColor Red
    if ($statusCode -eq 401) {
        Write-Host "401 = API Key 无效。请到 https://platform.deepseek.com/api_keys 检查并创建新密钥" -ForegroundColor Yellow
    } elseif ($statusCode -eq 402) {
        Write-Host "402 = 余额不足，请到 https://platform.deepseek.com/top_up 充值" -ForegroundColor Yellow
    }
    if ($errBody) { Write-Host $errBody }
    exit 1
}
