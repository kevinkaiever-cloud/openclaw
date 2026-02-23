#!/usr/bin/env node
/**
 * Generate placeholder icons for the Chrome extension.
 * Uses sharp (or minimal PNG fallback) to create 16, 32, 48, 128 px icons.
 */
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const outDir = join(root, "assets", "chrome-extension", "icons");

// Minimal valid 1x1 transparent PNG (scalable fallback if sharp fails)
const MINIMAL_PNG_B64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";

async function main() {
  await mkdir(outDir, { recursive: true });

  try {
    const sharp = (await import("sharp")).default;
    const sizes = [16, 32, 48, 128];
    const accent = "#ff5a36";

    for (const size of sizes) {
      const svg = `
        <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
          <rect width="${size}" height="${size}" rx="${Math.max(2, size / 8)}" fill="${accent}"/>
          <path d="M${size * 0.3} ${size * 0.4} L${size * 0.5} ${size * 0.6} L${size * 0.7} ${size * 0.35}" 
                stroke="white" stroke-width="${size * 0.08}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      `;
      const buf = await sharp(Buffer.from(svg)).png().toBuffer();
      await writeFile(join(outDir, `icon${size}.png`), buf);
      console.log(`Created icons/icon${size}.png`);
    }
  } catch (e) {
    console.warn("sharp failed, writing minimal PNG placeholders:", e.message);
    for (const size of [16, 32, 48, 128]) {
      const buf = Buffer.from(MINIMAL_PNG_B64, "base64");
      await writeFile(join(outDir, `icon${size}.png`), buf);
      console.log(`Created icons/icon${size}.png (minimal fallback)`);
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
