#!/usr/bin/env node
/**
 * Windows 构建入口：将 Git\\bin 加入 PATH 后执行 pnpm build，
 * 解决 canvas:a2ui:bundle 依赖 bash 的问题。
 */
import { spawn } from "node:child_process";
import { pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const gitBin = process.platform === "win32" ? "C:\\Program Files\\Git\\bin" : "";
const env = { ...process.env };
if (gitBin) env.PATH = `${gitBin};${env.PATH || ""}`;

const child = spawn(process.platform === "win32" ? "pnpm.cmd" : "pnpm", ["build"], {
  cwd: root,
  env,
  stdio: "inherit",
  shell: true,
});
child.on("exit", (code) => process.exit(code ?? 0));
