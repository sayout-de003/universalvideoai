"""Headless Chromium CDP frame-capture bridge using Node 24 built-in WebSocket + FFmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from backend.config import detect_chromium_path

_CDP_CAPTURE_JS = r'''
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

const [chromePath, htmlPath, outDir, widthStr, heightStr, fpsStr, durationStr] = process.argv.slice(2);
const width = parseInt(widthStr, 10);
const height = parseInt(heightStr, 10);
const fps = parseInt(fpsStr, 10);
const duration = parseFloat(durationStr);
const totalFrames = Math.max(12, Math.round(fps * duration));

const userDataDir = fs.mkdtempSync(path.join(outDir, "chrome-prof-"));
const chrome = spawn(
  chromePath,
  [
    "--headless=new",
    "--disable-gpu-sandbox",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--remote-debugging-port=0",
    `--user-data-dir=${userDataDir}`,
    `--window-size=${width},${height}`,
    `file://${htmlPath}`,
  ],
  { stdio: ["ignore", "ignore", "pipe"] }
);

let port = null;
const portPromise = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error("Chrome DevTools port timeout")), 15000);
  chrome.stderr.on("data", (chunk) => {
    const text = chunk.toString();
    const m = text.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\//);
    if (m) {
      clearTimeout(timer);
      resolve(parseInt(m[1], 10));
    }
  });
  chrome.on("exit", (code) => {
    clearTimeout(timer);
    if (!port) reject(new Error(`Chrome exited early with code ${code}`));
  });
});

async function run() {
  try {
    port = await portPromise;
    await new Promise((r) => setTimeout(r, 400));
    const listRes = await fetch(`http://127.0.0.1:${port}/json/list`);
    const targets = await listRes.json();
    const pageTarget = targets.find((t) => t.type === "page") || targets[0];
    if (!pageTarget?.webSocketDebuggerUrl) {
      throw new Error("No DevTools page target found");
    }

    const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve);
      ws.addEventListener("error", reject);
    });

    let msgId = 1;
    const pending = new Map();
    ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data.toString());
      if (msg.id && pending.has(msg.id)) {
        const { resolve, reject } = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    });

    const send = (method, params = {}) =>
      new Promise((resolve, reject) => {
        const id = msgId++;
        pending.set(id, { resolve, reject });
        ws.send(JSON.stringify({ id, method, params }));
      });

    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await new Promise((r) => setTimeout(r, 350));

    for (let i = 0; i < totalFrames; i++) {
      const t = (i / Math.max(1, totalFrames - 1)) * duration;
      await send("Runtime.evaluate", {
        expression: `window.__renderAtTime && window.__renderAtTime(${t.toFixed(4)}, ${i}, ${totalFrames})`,
        awaitPromise: true,
      });
      const shot = await send("Page.captureScreenshot", { format: "png" });
      const frameFile = path.join(outDir, `frame_${String(i).padStart(4, "0")}.png`);
      fs.writeFileSync(frameFile, Buffer.from(shot.data, "base64"));
    }

    ws.close();
  } finally {
    chrome.kill("SIGKILL");
    await new Promise((r) => setTimeout(r, 250));
    try {
      fs.rmSync(userDataDir, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
    } catch {
      // Chrome can still hold the profile dir. Frames are already on disk.
    }
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
'''


def capture_html_to_mp4(
    html_content: str,
    output_mp4: Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
    duration_sec: float = 4.0,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    """Render deterministic HTML/WebGL/Canvas frames via headless Chromium and encode to MP4."""
    chrome_path = detect_chromium_path()
    node_path = shutil.which("node")
    ffmpeg_path = shutil.which("ffmpeg")
    if not chrome_path or not node_path or not ffmpeg_path:
        return {
            "ok": False,
            "status": "UNAVAILABLE",
            "reason": f"Missing dependency: chrome={bool(chrome_path)}, node={bool(node_path)}, ffmpeg={bool(ffmpeg_path)}",
        }

    with tempfile.TemporaryDirectory(prefix="studio_cdp_") as tmp:
        tmp_dir = Path(tmp)
        html_path = tmp_dir / "scene.html"
        script_path = tmp_dir / "capture.mjs"
        frames_dir = tmp_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        html_path.write_text(html_content, encoding="utf-8")
        script_path.write_text(_CDP_CAPTURE_JS, encoding="utf-8")

        proc = subprocess.run(
            [
                node_path,
                str(script_path),
                chrome_path,
                str(html_path),
                str(frames_dir),
                str(width),
                str(height),
                str(fps),
                str(duration_sec),
            ],
            capture_output=True,
            text=True,
            timeout=max(30, int(timeout_sec)),
        )
        if proc.returncode != 0:
            return {"ok": False, "status": "UNAVAILABLE", "reason": (proc.stderr or proc.stdout)[-400:]}

        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        ff = subprocess.run(
            [
                ffmpeg_path, "-y",
                "-framerate", str(fps),
                "-i", str(frames_dir / "frame_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output_mp4),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if ff.returncode != 0 or not output_mp4.is_file():
            return {"ok": False, "status": "UNAVAILABLE", "reason": ff.stderr[-300:]}

        return {"ok": True, "status": "READY", "output": str(output_mp4)}
