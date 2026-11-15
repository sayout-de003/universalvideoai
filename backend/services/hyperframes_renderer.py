"""Pixar-Style 2D/3DShaded Character, Parallax World & Motion Graphics Canvas Renderer via Headless Chromium."""

from __future__ import annotations

import html as html_lib
import json
from pathlib import Path
from typing import Any

from backend.services.browser_capture import capture_html_to_mp4

_PIXAR_MOTION_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: 100vw; height: 100vh; overflow: hidden;
    background: #070b14;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Segoe UI", sans-serif;
    color: #f8fafc;
  }
  canvas {
    position: absolute; inset: 0; width: 100vw; height: 100vh; display: block;
  }
  .hud {
    position: absolute; inset: 0; pointer-events: none;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 5.5vh 6vw;
  }
  .top-row {
    display: flex; justify-content: space-between; align-items: flex-start;
  }
  .badge {
    display: inline-flex; align-items: center; gap: 10px;
    padding: 8px 18px; border-radius: 999px;
    background: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(56, 189, 248, 0.45);
    backdrop-filter: blur(12px);
    font-size: 1.05vw; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; color: #38bdf8;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  }
  .badge-dot {
    width: 9px; height: 9px; border-radius: 50%;
    background: #f59e0b; box-shadow: 0 0 12px #f59e0b;
  }
  .telemetry-card {
    width: 24vw; padding: 1.8vh 1.6vw; border-radius: 18px;
    background: rgba(15, 23, 42, 0.68);
    border: 1px solid rgba(255, 255, 255, 0.14);
    backdrop-filter: blur(14px);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45);
  }
  .telemetry-title {
    font-size: 0.9vw; text-transform: uppercase; letter-spacing: 0.15em;
    color: #94a3b8; margin-bottom: 1vh; font-weight: 600;
  }
  .telemetry-metric {
    font-size: 2.1vw; font-weight: 800; color: #f8fafc;
    display: flex; align-items: baseline; justify-content: space-between;
  }
  .telemetry-metric span {
    font-size: 1.0vw; color: #34d399; font-weight: 600;
  }
  .lower-third {
    max-width: 64vw;
    padding: 2.4vh 2.4vw; border-radius: 22px;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.84) 0%, rgba(15, 23, 42, 0.58) 100%);
    border: 1px solid rgba(255, 255, 255, 0.16);
    backdrop-filter: blur(16px);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
  }
  .headline {
    font-size: 3.1vw; line-height: 1.1; font-weight: 800;
    background: linear-gradient(135deg, #ffffff 0%, #fde68a 55%, #38bdf8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 1.1vh;
  }
  .subline {
    font-size: 1.45vw; line-height: 1.42; color: #e2e8f0; font-weight: 500;
  }
  .progress-track {
    margin-top: 1.6vh; width: 100%; height: 5px;
    background: rgba(148, 163, 184, 0.22); border-radius: 99px; overflow: hidden;
  }
  .progress-fill {
    height: 100%; width: 0%;
    background: linear-gradient(90deg, #f59e0b 0%, #38bdf8 55%, #818cf8 100%);
  }
</style>
</head>
<body>
  <canvas id="stageCanvas"></canvas>
  <div class="hud">
    <div class="top-row">
      <div class="badge" id="badge"><span class="badge-dot"></span><span>__EYEBROW__</span></div>
      <div class="telemetry-card" id="telemetry">
        <div class="telemetry-title">Scene Dynamics &amp; Motion Index</div>
        <div class="telemetry-metric"><div id="metricVal">94.2%</div><span id="metricTag">ACTIVE SYNC</span></div>
      </div>
    </div>
    <div class="lower-third" id="lowerThird">
      <h1 class="headline" id="headline">__HEADLINE__</h1>
      <p class="subline" id="subline">__SUBLINE__</p>
      <div class="progress-track"><div class="progress-fill" id="bar"></div></div>
    </div>
  </div>
<script>
const DURATION = __DURATION__;
const SCENE_SEED = __SEED__;
const THEME = __THEME__;

const canvas = document.getElementById("stageCanvas");
const ctx = canvas.getContext("2d");

function resize() {
  canvas.width = window.innerWidth || 1280;
  canvas.height = window.innerHeight || 720;
}
resize();
window.addEventListener("resize", resize);

const PALETTES = {
  pixar_character_world: {
    skyTop: "#0f172a", skyMid: "#1e293b", skyBot: "#f59e0b",
    sun: "#fde047", mountFar: "#1e1b4b", mountMid: "#312e81",
    groundTop: "#1e293b", groundBot: "#090d16",
    suit: "#f97316", suitRim: "#fdba74", accent: "#38bdf8"
  },
  painterly_parallax: {
    skyTop: "#132a3e", skyMid: "#2c5364", skyBot: "#e07a5f",
    sun: "#f4a261", mountFar: "#1d3557", mountMid: "#264653",
    groundTop: "#1b263b", groundBot: "#0d1b2a",
    suit: "#e63946", suitRim: "#f1faee", accent: "#a8dadc"
  },
  kinetic_data_hud: {
    skyTop: "#060b19", skyMid: "#0f172a", skyBot: "#1d4ed8",
    sun: "#38bdf8", mountFar: "#0f172a", mountMid: "#1e3a8a",
    groundTop: "#0f172a", groundBot: "#020617",
    suit: "#0ea5e9", suitRim: "#7dd3fc", accent: "#34d399"
  }
};
const pal = PALETTES[THEME] || PALETTES.pixar_character_world;

function drawPixarCharacter(ctx, cx, cy, scale, t) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale, scale);

  const stride = Math.sin(t * 5.4);
  const bounce = Math.abs(Math.cos(t * 5.4)) * -10;
  const breath = Math.sin(t * 2.6) * 2.5;

  // Soft contact ground shadow
  const shadowGrad = ctx.createRadialGradient(0, 96, 4, 0, 96, 56 - bounce * 0.8);
  shadowGrad.addColorStop(0, "rgba(0, 0, 0, 0.58)");
  shadowGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = shadowGrad;
  ctx.beginPath();
  ctx.ellipse(0, 96, 52, 14, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.translate(0, bounce);

  // Back leg
  ctx.save();
  ctx.translate(-8, 38);
  ctx.rotate(-stride * 0.42);
  ctx.fillStyle = "#1e293b";
  ctx.beginPath();
  ctx.roundRect(-9, 0, 18, 48, 9);
  ctx.fill();
  ctx.fillStyle = "#f8fafc";
  ctx.beginPath();
  ctx.roundRect(-7, 42, 24, 12, 6);
  ctx.fill();
  ctx.restore();

  // Back arm
  ctx.save();
  ctx.translate(-12, -14);
  ctx.rotate(stride * 0.48);
  ctx.fillStyle = pal.suit;
  ctx.beginPath();
  ctx.roundRect(-8, 0, 16, 42, 8);
  ctx.fill();
  ctx.restore();

  // 3D-shaded Torso / Jacket
  const torsoGrad = ctx.createLinearGradient(-28, -28, 28, 42);
  torsoGrad.addColorStop(0, pal.suitRim);
  torsoGrad.addColorStop(0.28, pal.suit);
  torsoGrad.addColorStop(1, "#7c2d12");
  ctx.fillStyle = torsoGrad;
  ctx.beginPath();
  ctx.roundRect(-24, -24 - breath * 0.4, 48, 66 + breath * 0.4, 20);
  ctx.fill();

  // Messenger strap & glowing badge
  ctx.strokeStyle = "#fde047";
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.moveTo(-18, -20);
  ctx.lineTo(18, 34);
  ctx.stroke();

  // Front leg
  ctx.save();
  ctx.translate(8, 38);
  ctx.rotate(stride * 0.42);
  ctx.fillStyle = "#334155";
  ctx.beginPath();
  ctx.roundRect(-9, 0, 18, 48, 9);
  ctx.fill();
  ctx.fillStyle = "#f8fafc";
  ctx.beginPath();
  ctx.roundRect(-7, 42, 24, 12, 6);
  ctx.fill();
  ctx.restore();

  // Head with 3D spherical subsurface shading
  ctx.save();
  ctx.translate(0, -52 - breath * 0.6);
  ctx.rotate(Math.sin(t * 1.8) * 0.08);
  const headGrad = ctx.createRadialGradient(-10, -12, 6, 0, 0, 34);
  headGrad.addColorStop(0, "#fed7aa");
  headGrad.addColorStop(0.65, "#fb923c");
  headGrad.addColorStop(1, "#9a3412");
  ctx.fillStyle = headGrad;
  ctx.beginPath();
  ctx.arc(0, 0, 29, 0, Math.PI * 2);
  ctx.fill();

  // Stylized swept hair
  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.arc(-3, -8, 29, Math.PI * 0.95, Math.PI * 2.05);
  ctx.quadraticCurveTo(18, -36, -18, -32);
  ctx.fill();

  // Expressive eyes (with periodic natural blink)
  const blink = (t % 2.8) > 2.66 ? 0.15 : 1.0;
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.ellipse(9, -2, 6.5, 7.5 * blink, 0, 0, Math.PI * 2);
  ctx.ellipse(21, -2, 5.5, 7.0 * blink, 0, 0, Math.PI * 2);
  ctx.fill();

  if (blink > 0.3) {
    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.arc(11, -2, 3.3, 0, Math.PI * 2);
    ctx.arc(22, -2, 3.0, 0, Math.PI * 2);
    ctx.fill();
    // Eye catchlight
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(12.2, -3.5, 1.3, 0, Math.PI * 2);
    ctx.arc(23.0, -3.5, 1.1, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  // Front arm
  ctx.save();
  ctx.translate(10, -14);
  ctx.rotate(-stride * 0.48);
  ctx.fillStyle = pal.suit;
  ctx.beginPath();
  ctx.roundRect(-8, 0, 16, 42, 8);
  ctx.fill();
  ctx.restore();

  ctx.restore();
}

window.__renderAtTime = (t) => {
  const w = canvas.width;
  const h = canvas.height;
  const p = Math.max(0, Math.min(1, t / Math.max(0.1, DURATION)));
  const ease = 1 - Math.pow(1 - Math.min(1, p * 2.8), 3);

  // 1. Sky gradient
  const sky = ctx.createLinearGradient(0, 0, 0, h * 0.72);
  sky.addColorStop(0, pal.skyTop);
  sky.addColorStop(0.55, pal.skyMid);
  sky.addColorStop(1, pal.skyBot);
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, w, h);

  // 2. Volumetric Sun & God-Rays
  const sunX = w * (0.68 - p * 0.06);
  const sunY = h * (0.28 - Math.sin(p * Math.PI) * 0.04);
  const sunGlow = ctx.createRadialGradient(sunX, sunY, 10, sunX, sunY, w * 0.34);
  sunGlow.addColorStop(0, pal.sun);
  sunGlow.addColorStop(0.25, "rgba(251, 191, 36, 0.32)");
  sunGlow.addColorStop(1, "rgba(251, 191, 36, 0)");
  ctx.fillStyle = sunGlow;
  ctx.fillRect(0, 0, w, h);

  // 3. Parallax Distant Mountains / Skyline
  ctx.fillStyle = pal.mountFar;
  ctx.beginPath();
  ctx.moveTo(0, h * 0.68);
  for (let x = 0; x <= w + 80; x += 80) {
    const wave = Math.sin((x + t * 28 + SCENE_SEED * 40) * 0.0045) * h * 0.09 + Math.cos((x + SCENE_SEED * 90) * 0.011) * h * 0.04;
    ctx.lineTo(x, h * 0.54 - wave);
  }
  ctx.lineTo(w, h * 0.75);
  ctx.lineTo(0, h * 0.75);
  ctx.closePath();
  ctx.fill();

  // 4. Midground Animated Architectural / Bridge Silhouette
  ctx.fillStyle = pal.mountMid;
  const scrollMid = (t * 75) % 180;
  for (let i = -1; i < Math.ceil(w / 180) + 2; i++) {
    const bx = i * 180 - scrollMid;
    const bh = h * (0.14 + ((i + SCENE_SEED) % 4) * 0.045);
    const by = h * 0.68 - bh;
    ctx.fillRect(bx, by, 110, bh);
    // Warm lit windows
    ctx.fillStyle = "rgba(253, 224, 71, 0.45)";
    for (let wy = by + 16; wy < h * 0.66; wy += 24) {
      ctx.fillRect(bx + 18, wy, 14, 10);
      ctx.fillRect(bx + 46, wy, 14, 10);
      ctx.fillRect(bx + 74, wy, 14, 10);
    }
    ctx.fillStyle = pal.mountMid;
  }

  // 5. Foreground Perspective Ground & Motion Lines
  const ground = ctx.createLinearGradient(0, h * 0.66, 0, h);
  ground.addColorStop(0, pal.groundTop);
  ground.addColorStop(1, pal.groundBot);
  ctx.fillStyle = ground;
  ctx.fillRect(0, h * 0.66, w, h * 0.34);

  ctx.strokeStyle = "rgba(56, 189, 248, 0.22)";
  ctx.lineWidth = 2;
  const gridShift = (t * 210) % 120;
  for (let gx = -gridShift; gx < w; gx += 120) {
    ctx.beginPath();
    ctx.moveTo(gx, h * 0.66);
    ctx.lineTo(gx - 90, h);
    ctx.stroke();
  }

  // 6. Animated Data Wave / Motion Graphics Curve in Upper Midground
  ctx.save();
  ctx.strokeStyle = pal.accent;
  ctx.lineWidth = 3.5;
  ctx.beginPath();
  for (let x = w * 0.52; x < w * 0.94; x += 12) {
    const norm = (x - w * 0.52) / (w * 0.42);
    const y = h * 0.36 + Math.sin(norm * Math.PI * 3 + t * 4.0) * 28 * Math.sin(norm * Math.PI);
    if (x === w * 0.52) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.restore();

  // 7. Articulated Pixar-Style Character Walking Across Stage
  const charX = w * (0.28 + p * 0.14);
  const charY = h * 0.62;
  drawPixarCharacter(ctx, charX, charY, Math.min(w, h) / 680, t);

  // 8. Atmospheric Bokeh & Floating Light Particles
  for (let i = 0; i < 28; i++) {
    const px = ((i * 197 + t * (35 + (i % 5) * 12)) % (w + 60)) - 30;
    const py = ((i * 131 - t * (18 + (i % 4) * 8)) % h + h) % h;
    const pr = 2 + (i % 4) * 1.8;
    ctx.fillStyle = i % 2 === 0 ? "rgba(253, 224, 71, 0.38)" : "rgba(56, 189, 248, 0.35)";
    ctx.beginPath();
    ctx.arc(px, py, pr, 0, Math.PI * 2);
    ctx.fill();
  }

  // HUD updates
  document.getElementById("lowerThird").style.opacity = Math.min(1, p * 4.0);
  document.getElementById("lowerThird").style.transform = `translateY(${(1 - ease) * 24}px)`;
  document.getElementById("bar").style.width = `${(p * 100).toFixed(1)}%`;
  const metricNum = (88 + SCENE_SEED % 9 + p * 3.6).toFixed(1);
  document.getElementById("metricVal").textContent = `${metricNum}%`;
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
    title = html_lib.escape(str(scene.get("on_screen_text") or scene.get("title") or "Cinematic Scene")[:80])
    subline = html_lib.escape(str(scene.get("narration_segment") or scene.get("narration") or "")[:180])
    eyebrow = html_lib.escape(f"{category.replace('_', ' ').upper()} • {scene.get('speaker_name') or 'STUDIO ANIMATION'}")
    theme = str(scene.get("animation_theme") or "pixar_character_world")
    seed = int(scene.get("order_index") or 1) + sum(ord(c) for c in title[:12])

    html = (
        _PIXAR_MOTION_TEMPLATE
        .replace("__EYEBROW__", eyebrow)
        .replace("__HEADLINE__", title)
        .replace("__SUBLINE__", subline)
        .replace("__THEME__", json.dumps(theme))
        .replace("__SEED__", json.dumps(seed))
        .replace("__DURATION__", json.dumps(duration))
    )
    res = capture_html_to_mp4(
        html, output_mp4, width=width, height=height, fps=fps, duration_sec=duration,
        timeout_sec=max(180, int(duration * fps * 0.45) + 45),
    )
    res["engine"] = "hyperframes"
    return res
