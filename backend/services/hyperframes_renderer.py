"""Real HyperFrames HTML5/CSS3/SVG Motion Graphics Renderer via Headless Chromium."""

from __future__ import annotations

import html as html_lib
import json
from pathlib import Path
from typing import Any

from backend.services.browser_capture import capture_html_to_mp4

_HYPERFRAMES_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: 100%; height: 100%; overflow: hidden;
    background: radial-gradient(circle at 20% 20%, #172554 0%, #090d1a 55%, #03050a 100%);
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
  }
  .stage {
    position: relative; width: 100vw; height: 100vh;
    display: flex; flex-direction: column; justify-content: center; padding: 8vw;
  }
  .grid {
    position: absolute; inset: 0;
    background-image: linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(148,163,184,0.06) 1px, transparent 1px);
    background-size: 64px 64px;
    transform-origin: center;
  }
  .orb {
    position: absolute; right: 10vw; top: 18vh; width: 26vw; height: 26vw; border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, rgba(56,189,248,0.45), rgba(99,102,241,0.12) 65%, transparent 75%);
    filter: blur(8px);
  }
  .eyebrow {
    font-size: 1.3vw; letter-spacing: 0.24em; text-transform: uppercase;
    color: #38bdf8; margin-bottom: 1.4vh; font-weight: 600;
  }
  .headline {
    font-size: 4.4vw; line-height: 1.08; font-weight: 800; max-width: 70vw;
    background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .subline {
    margin-top: 2.2vh; font-size: 1.8vw; line-height: 1.45; color: #94a3b8; max-width: 58vw;
  }
  .visual {
    margin-top: 1.6vh; font-size: 1.35vw; line-height: 1.4; color: #cbd5e1; max-width: 62vw;
  }
  .bar-wrap {
    margin-top: 4vh; width: 32vw; height: 4px; background: rgba(148,163,184,0.2); border-radius: 99px; overflow: hidden;
  }
  body.film .bar-wrap { display: none; }
  body.film {
    background: radial-gradient(circle at 30% 20%, #3a2a1c 0%, #120e0b 55%, #070605 100%);
  }
  body.film .headline { font-family: Georgia, "Iowan Old Style", serif; font-weight: 600; }
  .bar-fill {
    height: 100%; width: 0%; background: linear-gradient(90deg, #38bdf8, #818cf8);
  }
</style>
</head>
<body class="__BODYCLASS__">
  <div class="stage">
    <div class="grid" id="grid"></div>
    <div class="orb" id="orb"></div>
    <div class="eyebrow" id="eyebrow">__EYEBROW__</div>
    <h1 class="headline" id="headline">__HEADLINE__</h1>
    <p class="subline" id="subline">__SUBLINE__</p>
    <p class="visual" id="visual">__VISUAL__</p>
    <div class="bar-wrap"><div class="bar-fill" id="bar"></div></div>
  </div>
<script>
const DURATION = __DURATION__;
window.__renderAtTime = (t) => {
  const p = Math.max(0, Math.min(1, t / Math.max(0.1, DURATION)));
  const ease = 1 - Math.pow(1 - p, 3);
  document.getElementById("grid").style.transform = `scale(${1 + 0.08 * p}) translateY(${-20 * p}px)`;
  document.getElementById("orb").style.transform = `translate(${-30 * p}px, ${25 * Math.sin(p * Math.PI)}px) scale(${0.92 + 0.16 * ease})`;
  document.getElementById("headline").style.opacity = Math.min(1, p * 3.5);
  document.getElementById("headline").style.transform = `translateY(${(1 - Math.min(1, p * 3.0)) * 28}px)`;
  document.getElementById("subline").style.opacity = Math.min(1, Math.max(0, (p - 0.12) * 3.2));
  document.getElementById("bar").style.width = `${(p * 100).toFixed(2)}%`;
};
window.__renderAtTime(0);
</script>
</body>
</html>
'''


def render_hyperframes_scene(
    scene: dict[str, Any],
    output_mp4: Path,
    category: str = "explainer",
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> dict[str, Any]:
    duration = max(2.0, float(scene.get("duration_sec", 4.0) or 4.0))
    title = html_lib.escape(str(scene.get("on_screen_text") or scene.get("title") or "Motion Graphic")[:80])
    subline = html_lib.escape(str(scene.get("narration_segment") or scene.get("narration") or "")[:160])
    visual = html_lib.escape(str(scene.get("picture_prompt") or scene.get("visual_description") or scene.get("generation_prompt") or "")[:220])
    eyebrow = html_lib.escape(category.replace("_", " ").upper())
    body_class = "film" if category in ("documentary", "cinematic", "historical", "film") else "graphic"

    html = (
        _HYPERFRAMES_TEMPLATE
        .replace("__EYEBROW__", eyebrow)
        .replace("__HEADLINE__", title)
        .replace("__SUBLINE__", subline)
        .replace("__VISUAL__", visual)
        .replace("__BODYCLASS__", body_class)
        .replace("__DURATION__", json.dumps(duration))
    )
    res = capture_html_to_mp4(
        html, output_mp4, width=width, height=height, fps=fps, duration_sec=duration,
        timeout_sec=max(180, int(duration * fps * 0.45) + 45),
    )
    res["engine"] = "hyperframes"
    return res
