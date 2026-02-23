---
summary: "Android app (node): connection runbook + Canvas/Chat/Camera + Local Agent"
read_when:
  - Pairing or reconnecting the Android node
  - Debugging Android gateway discovery or auth
  - Verifying chat history parity across clients
  - Running local agent on mobile
title: "Android App"
---

# Android App (Node)

## Support snapshot

- Role: companion node app (Android does not host the Gateway).
- Gateway required: no (Local Agent mode can run standalone); yes for full node features.
- Install: [Getting Started](/start/getting-started) + [Pairing](/gateway/pairing).
- Gateway: [Runbook](/gateway) + [Configuration](/gateway/configuration).
  - Protocols: [Gateway protocol](/gateway/protocol) (nodes + control plane).

## System control

System control (launchd/systemd) lives on the Gateway host. See [Gateway](/gateway).

## Connection Runbook

Android node app ⇄ (mDNS/NSD + WebSocket) ⇄ **Gateway**

Android connects directly to the Gateway WebSocket (default `ws://<host>:18789`) and uses Gateway-owned pairing.

### Prerequisites

- You can run the Gateway on the “master” machine.
- Android device/emulator can reach the gateway WebSocket:
  - Same LAN with mDNS/NSD, **or**
  - Same Tailscale tailnet using Wide-Area Bonjour / unicast DNS-SD (see below), **or**
  - Manual gateway host/port (fallback)
- You can run the CLI (`openclaw`) on the gateway machine (or via SSH).

### 1) Start the Gateway

```bash
openclaw gateway --port 18789 --verbose
```

Confirm in logs you see something like:

- `listening on ws://0.0.0.0:18789`

For tailnet-only setups (recommended for Vienna ⇄ London), bind the gateway to the tailnet IP:

- Set `gateway.bind: "tailnet"` in `~/.openclaw/openclaw.json` on the gateway host.
- Restart the Gateway / macOS menubar app.

### 2) Verify discovery (optional)

From the gateway machine:

```bash
dns-sd -B _openclaw-gw._tcp local.
```

More debugging notes: [Bonjour](/gateway/bonjour).

#### Tailnet (Vienna ⇄ London) discovery via unicast DNS-SD

Android NSD/mDNS discovery won’t cross networks. If your Android node and the gateway are on different networks but connected via Tailscale, use Wide-Area Bonjour / unicast DNS-SD instead:

1. Set up a DNS-SD zone (example `openclaw.internal.`) on the gateway host and publish `_openclaw-gw._tcp` records.
2. Configure Tailscale split DNS for your chosen domain pointing at that DNS server.

Details and example CoreDNS config: [Bonjour](/gateway/bonjour).

### 3) Connect from Android

In the Android app:

- The app keeps its gateway connection alive via a **foreground service** (persistent notification).
- Open **Settings**.
- Under **Discovered Gateways**, select your gateway and hit **Connect**.
- If mDNS is blocked, use **Advanced → Manual Gateway** (host + port) and **Connect (Manual)**.

After the first successful pairing, Android auto-reconnects on launch:

- Manual endpoint (if enabled), otherwise
- The last discovered gateway (best-effort).

### 4) Approve pairing (CLI)

On the gateway machine:

```bash
openclaw nodes pending
openclaw nodes approve <requestId>
```

Pairing details: [Gateway pairing](/gateway/pairing).

### 5) Verify the node is connected

- Via nodes status:

  ```bash
  openclaw nodes status
  ```

- Via Gateway:

  ```bash
  openclaw gateway call node.list --params "{}"
  ```

### 6) Chat + history

The Android node’s Chat sheet uses the gateway’s **primary session key** (`main`), so history and replies are shared with WebChat and other clients:

- History: `chat.history`
- Send: `chat.send`
- Push updates (best-effort): `chat.subscribe` → `event:"chat"`

### 7) Canvas + camera

#### Gateway Canvas Host (recommended for web content)

If you want the node to show real HTML/CSS/JS that the agent can edit on disk, point the node at the Gateway canvas host.

Note: nodes load canvas from the Gateway HTTP server (same port as `gateway.port`, default `18789`).

1. Create `~/.openclaw/workspace/canvas/index.html` on the gateway host.

2. Navigate the node to it (LAN):

```bash
openclaw nodes invoke --node "<Android Node>" --command canvas.navigate --params '{"url":"http://<gateway-hostname>.local:18789/__openclaw__/canvas/"}'
```

Tailnet (optional): if both devices are on Tailscale, use a MagicDNS name or tailnet IP instead of `.local`, e.g. `http://<gateway-magicdns>:18789/__openclaw__/canvas/`.

This server injects a live-reload client into HTML and reloads on file changes.
The A2UI host lives at `http://<gateway-host>:18789/__openclaw__/a2ui/`.

Canvas commands (foreground only):

- `canvas.eval`, `canvas.snapshot`, `canvas.navigate` (use `{"url":""}` or `{"url":"/"}` to return to the default scaffold). `canvas.snapshot` returns `{ format, base64 }` (default `format="jpeg"`).
- A2UI: `canvas.a2ui.push`, `canvas.a2ui.reset` (`canvas.a2ui.pushJSONL` legacy alias)

Camera commands (foreground only; permission-gated):

- `camera.snap` (jpg)
- `camera.clip` (mp4)

See [Camera node](/nodes/camera) for parameters and CLI helpers.

## Local Agent Mode

Local Agent mode lets you run AI agents directly on your Android device without requiring a Gateway server. This is ideal for mobile use when you want a standalone AI assistant.

### Setup

1. Open **Settings** in the Android app.
2. Scroll to the **Local Agent** section.
3. Toggle **Enable Local Agent** on.
4. Choose your AI provider (Anthropic Claude or OpenAI).
5. Select a model from the available list.
6. Enter your API key (stored in Android EncryptedSharedPreferences).
7. Close settings and tap the **Chat** button to start chatting.

### Supported providers

| Provider | Models |
|----------|--------|
| Anthropic | Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Haiku |
| OpenAI | GPT-4o, GPT-4o mini, GPT-4 Turbo, o1-mini |

### Advanced options

- **System Prompt**: customize the agent personality and behavior.
- **Max Tokens**: control the maximum response length (default: 4096).
- **Custom API Endpoint**: use a proxy or self-hosted model endpoint.

### How it works

- Messages are sent directly from your device to the AI provider API via OkHttp.
- Conversation history is stored locally on the device.
- Streaming responses show text as it arrives.
- Sessions are persisted between app launches.
- No Gateway connection is needed; the status pill shows "Connected" when local agent is enabled.

### Switching modes

When Local Agent mode is enabled, the Chat button routes to the local agent chat. Gateway node features (camera, screen, location, voice wake) remain available when connected to a Gateway. To switch back to Gateway-only chat, disable Local Agent in Settings.
