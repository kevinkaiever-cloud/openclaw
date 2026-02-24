# OpenClaw + DeepSeek 配置指南

本仓库已配置为使用 **DeepSeek API** 作为默认模型。

## 快速开始

### 1. 获取 DeepSeek API Key

访问 [DeepSeek 开放平台](https://platform.deepseek.com) 注册并获取 API Key。

### 2. 配置 API Key

**方式一：环境变量（推荐）**

编辑 `~/.openclaw/.env`，填入你的 API Key：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

**方式二：直接在配置中**

编辑 `~/.openclaw/openclaw.json` 中的 `env.DEEPSEEK_API_KEY` 字段。

### 3. 安装依赖并启动

```bash
cd openclaw
pnpm install
pnpm ui:build   # 首次需要
pnpm build      # Windows 若报 bash 找不到，改用: pnpm build:win
```

启动网关：

```bash
# Linux/macOS
pnpm gateway:watch
# 或
pnpm openclaw gateway --port 18789 --verbose
```

Windows 推荐直接双击 **启动网关.bat**，或先 `set PATH=C:\Program Files\Git\bin;%PATH%` 后执行 `pnpm.cmd openclaw gateway --port 18789 --verbose`。详见 **启动说明.txt**。

### 4. 测试对话

```bash
pnpm openclaw agent --message "你好，请用中文回复"
```

## 可用模型

| 模型 ID | 说明 |
|---------|------|
| `deepseek/deepseek-chat` | 通用对话，直接回复 |
| `deepseek/deepseek-reasoner` | 推理模式，适合复杂任务 |

在对话中使用 `/model deepseek/deepseek-reasoner` 可切换模型。

## 配置说明

- **API 端点**: `https://api.deepseek.com/v1`（OpenAI 兼容）
- **上下文窗口**: 128K tokens
- **配置文件**: `~/.openclaw/openclaw.json`
- **示例配置**: 项目根目录 `openclaw.deepseek.example.json`（通用）、`openclaw.windows.example.json`（Windows 本机免 Token + DeepSeek）

## 故障排查

### Unknown model: deepseek/chat

说明网关未识别到 DeepSeek 提供商。请确保 `openclaw.json` 中：

1. **模型 ID** 为 `deepseek/deepseek-chat`（不是 `deepseek/chat`）。
2. 存在 **models.providers.deepseek** 段（含 baseUrl、apiKey、models 列表）。

可直接参考 **openclaw.windows.example.json** 中的 `models` 与 `agents.defaults` 部分，复制到你的 `~/.openclaw/openclaw.json`，并保证 `~/.openclaw/.env` 中有 `DEEPSEEK_API_KEY=sk-...`。

### HTTP 401: API Key invalid

表示 DeepSeek 拒绝了你的 API Key。按以下步骤排查：

1. **验证 Key 是否有效**

   在项目目录运行：

   ```powershell
   .\test-deepseek-key.ps1
   ```

   脚本会从 `~/.openclaw/.env` 的 `DEEPSEEK_API_KEY` 读取并测试。若返回 401，说明 Key 本身无效。

2. **获取新 Key**

   - 打开 [API 密钥管理](https://platform.deepseek.com/api_keys)
   - 创建新密钥，复制完整内容（以 `sk-` 开头）
   - 更新 `~/.openclaw/.env` 中的 `DEEPSEEK_API_KEY=sk-...`

3. **检查余额**

   若为 402 错误，表示余额不足，请到 [充值页面](https://platform.deepseek.com/top_up) 充值。

4. **确保无多余空格**

   `.env` 中不要有多余空格，例如：

   ```
   DEEPSEEK_API_KEY=sk-xxxxxxxx
   ```

   不要写成 `DEEPSEEK_API_KEY = sk-xxx` 或 `DEEPSEEK_API_KEY=sk-xxx `（行末空格）。

## 参考链接

- [DeepSeek API 文档](https://platform.deepseek.com/api-docs)
- [OpenClaw 官方文档](https://docs.openclaw.ai)
