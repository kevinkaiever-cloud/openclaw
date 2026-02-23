# Telegram 机器人无响应 - 排查指南

## 问题现象
给 @kevinkaibot 发「你好」没有回复。

## 最可能的原因：网络限制（中国大陆）

在中国大陆，`api.telegram.org` 被屏蔽，OpenClaw 无法直接连接 Telegram 服务器接收消息。

### 解决方案：配置代理

1. **确认你有可用的代理**（Clash、V2Ray、SSR 等），并记下：
   - HTTP 代理：通常是 `http://127.0.0.1:7890`（Clash 默认）
   - SOCKS5 代理：通常是 `socks5://127.0.0.1:1080`

2. **编辑 `~/.openclaw/openclaw.json`**，在 `channels.telegram` 下添加 `proxy`：

```json
"channels": {
  "telegram": {
    "enabled": true,
    "botToken": "8767481674:AAHp6cE1VM7sN_QZIRmSj5P61NKuiHusktM",
    "dmPolicy": "pairing",
    "proxy": "http://127.0.0.1:7890"
  }
}
```

将 `http://127.0.0.1:7890` 换成你的实际代理地址。Clash 常用 7890，V2Ray 可能用 10808。

3. **重启网关**：
```powershell
cd C:\Users\Administrator\Desktop\openclaw
pnpm openclaw gateway stop
# 等待几秒后
pnpm openclaw gateway --port 18789 --verbose
```

4. **验证**：运行 `openclaw status --deep`，Channels 表格中应出现 Telegram 且状态正常。

---

## 其他检查

- **确认代理已开启**：在发消息前，确保 Clash/V2Ray 等正在运行
- **确认 Bot Token 正确**：在配置中检查是否有多余空格或复制错误
- **首次需配对**：发消息后若收到配对码，在电脑执行：
  ```powershell
  pnpm openclaw pairing approve telegram <配对码>
  ```
