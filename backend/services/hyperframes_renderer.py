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
  body.hide-hud .hud {
    display: none !important;
  }
  .cinematic-caption {
    position: absolute;
    bottom: 5vh;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(8, 10, 16, 0.72);
    padding: 1.2vh 2.4vw;
    border-radius: 12px;
    color: #f8fafc;
    font-size: 1.6vw;
    font-weight: 600;
    text-align: center;
    max-width: 80vw;
    line-height: 1.4;
    pointer-events: none;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  }
</style>
</head>
<body class="__BODY_CLASS__" style="__BODY_STYLE__">
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
  __CINEMATIC_CAPTION_HTML__
<script>
const DURATION = __DURATION__;
const SCENE_SEED = __SEED__;
const THEME = __THEME__;
const SHOW_HUD = __SHOW_HUD__;
const CHARACTER_META = __CHARACTER_META__;

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
  },
  pixel_art: {
    skyTop: "#1a1c2c", skyMid: "#3b5dc9", skyBot: "#ffcd75",
    sun: "#f4f4f4", mountFar: "#333c57", mountMid: "#29366f",
    groundTop: "#38b764", groundBot: "#257179",
    suit: "#b13e53", suitRim: "#ef7d57", accent: "#73eff7"
  },
  "2d_illustrated": {
    skyTop: "#1d3557", skyMid: "#457b9d", skyBot: "#f4a261",
    sun: "#e9c46a", mountFar: "#264653", mountMid: "#2a9d8f",
    groundTop: "#264653", groundBot: "#1d3557",
    suit: "#e76f51", suitRim: "#f4a261", accent: "#e9c46a"
  },
  hand_drawn_storybook: {
    skyTop: "#f6efe2", skyMid: "#ebd9be", skyBot: "#d9a066",
    sun: "#e07a5f", mountFar: "#81b29a", mountMid: "#3d405b",
    groundTop: "#6d597a", groundBot: "#355070",
    suit: "#b56576", suitRim: "#eaac8b", accent: "#e07a5f"
  },
  anime: {
    skyTop: "#0b1026", skyMid: "#1e1b4b", skyBot: "#fb7185",
    sun: "#fef08a", mountFar: "#2e1065", mountMid: "#4338ca",
    groundTop: "#1e1b4b", groundBot: "#020617",
    suit: "#2563eb", suitRim: "#93c5fd", accent: "#f43f5e"
  },
  cartoon_2d: {
    skyTop: "#38bdf8", skyMid: "#60a5fa", skyBot: "#fef08a",
    sun: "#facc15", mountFar: "#4ade80", mountMid: "#22c55e",
    groundTop: "#16a34a", groundBot: "#15803d",
    suit: "#ef4444", suitRim: "#f87171", accent: "#f59e0b"
  },
  cyberpunk: {
    skyTop: "#090218", skyMid: "#1e0836", skyBot: "#4c0f4d",
    sun: "#ff2a85", mountFar: "#140826", mountMid: "#220e42",
    groundTop: "#0c0618", groundBot: "#06030d",
    suit: "#00f5d4", suitRim: "#ff2a85", accent: "#00f5d4"
  }
};
const isCyberpunk = THEME === "cyberpunk" || (CHARACTER_META && /cyberpunk|flying car|neon/i.test(CHARACTER_META.scene_style || ""));
const pal = isCyberpunk ? PALETTES.cyberpunk : (PALETTES[THEME] || PALETTES.pixar_character_world);

function drawPixelArtScene(ctx, w, h, p, t) {
  const grid = Math.max(4, Math.floor(w / 160));
  const snap = (v) => Math.floor(v / grid) * grid;
  ctx.imageSmoothingEnabled = false;

  const bands = isCyberpunk
    ? [pal.skyTop, "#120428", pal.skyMid, "#340a47", pal.skyBot]
    : [pal.skyTop, "#29366f", pal.skyMid, "#41a6f6", pal.skyBot];
  const bh = Math.ceil((h * 0.72) / bands.length);
  for (let i = 0; i < bands.length; i++) {
    ctx.fillStyle = bands[i];
    ctx.fillRect(0, i * bh, w, bh + grid);
  }

  const sx = snap(w * 0.72 - p * w * 0.05);
  const sy = snap(h * 0.22);
  ctx.fillStyle = pal.sun;
  ctx.fillRect(sx - grid * 5, sy - grid * 5, grid * 10, grid * 10);

  if (isCyberpunk) {
    // Pixel-art neon skyscrapers & glowing windows
    for (let i = 0; i < 18; i++) {
      const bx = snap((i * w) / 18);
      const bw = snap(w / 18) - grid;
      const bheight = snap(h * (0.22 + ((i * 37 + SCENE_SEED) % 30) * 0.012));
      const by = snap(h * 0.70) - bheight;
      ctx.fillStyle = i % 2 === 0 ? pal.mountFar : pal.mountMid;
      ctx.fillRect(bx, by, bw, bheight);
      ctx.fillStyle = i % 3 === 0 ? "#00f5d4" : "#ff2a85";
      for (let wy = by + grid * 2; wy < snap(h * 0.68); wy += grid * 3) {
        if (((i + wy) % 5) !== 0) {
          ctx.fillRect(bx + grid, wy, Math.max(grid, bw - grid * 2), grid);
        }
      }
    }
    // Flying cars with neon trails
    for (let c = 0; c < 6; c++) {
      const dir = c % 2 === 0 ? 1 : -1;
      const speed = 0.14 + c * 0.04;
      const rawX = ((c * 0.19 + t * speed * dir) % 1.2 + 1.2) % 1.2 - 0.1;
      const fx = snap(rawX * w);
      const fy = snap(h * (0.20 + c * 0.07));
      ctx.fillStyle = c % 2 === 0 ? "#00f5d4" : "#ff2a85";
      ctx.fillRect(fx, fy, grid * 5, grid * 2);
      ctx.fillStyle = "rgba(255,255,255,0.65)";
      ctx.fillRect(fx + (dir > 0 ? -grid * 6 : grid * 5), fy, grid * 5, grid);
    }
    // Neon rain
    ctx.fillStyle = "rgba(0, 245, 212, 0.35)";
    for (let r = 0; r < 40; r++) {
      const rx = snap(((r * 97 + t * 40) % w));
      const ry = snap(((r * 53 + t * 260) % (h * 0.70)));
      ctx.fillRect(rx, ry, grid, grid * 2);
    }
  } else {
    ctx.fillStyle = pal.mountFar;
    for (let x = 0; x < w; x += grid * 4) {
      const mh = snap(h * 0.18 + Math.sin((x + t * 20) * 0.01) * h * 0.08);
      ctx.fillRect(x, snap(h * 0.68) - mh, grid * 4, mh);
    }
  }

  ctx.fillStyle = pal.groundTop;
  ctx.fillRect(0, snap(h * 0.68), w, grid * 3);
  ctx.fillStyle = pal.groundBot;
  ctx.fillRect(0, snap(h * 0.68) + grid * 3, w, h);

  const cx = snap(w * (0.26 + p * 0.18));
  const cy = snap(h * 0.60);
  const step = Math.floor(t * 6) % 2;
  ctx.fillStyle = "#ffccaa";
  ctx.fillRect(cx, cy - grid * 8, grid * 4, grid * 4);
  ctx.fillStyle = pal.suit;
  ctx.fillRect(cx - grid, cy - grid * 9, grid * 6, grid * 2);
  ctx.fillRect(cx, cy - grid * 4, grid * 4, grid * 5);
  ctx.fillStyle = "#1a1c2c";
  ctx.fillRect(cx + (step ? -grid : 0), cy + grid, grid * 2, grid * 4);
  ctx.fillRect(cx + (step ? grid * 3 : grid * 2), cy + grid, grid * 2, grid * 4);
}

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

  // Eyebrows
  ctx.strokeStyle = "#475569";
  ctx.lineWidth = 2.0;
  ctx.beginPath();
  ctx.moveTo(6, -11);
  ctx.quadraticCurveTo(12, -14, 17, -11);
  ctx.moveTo(19, -11);
  ctx.quadraticCurveTo(24, -13, 27, -10);
  ctx.stroke();

  // Animated expressive mouth on face
  const pixarTalk = Math.abs(Math.sin(t * 8.0));
  ctx.fillStyle = "#1e1b4b";
  ctx.beginPath();
  ctx.ellipse(15, 12, 5.5, Math.max(1.8, pixarTalk * 4.5), 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#9a3412";
  ctx.lineWidth = 1.4;
  ctx.stroke();

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

function drawAnimeCharacter(ctx, cx, cy, scale, t, p) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale * 1.05, scale * 1.05);

  const stride = Math.sin(t * 5.8);
  const bounce = Math.abs(Math.cos(t * 5.8)) * -7;
  const breath = Math.sin(t * 2.8) * 2;
  const wind = Math.sin(t * 4.2);

  // Soft shadow
  const shadowGrad = ctx.createRadialGradient(0, 96, 4, 0, 96, 52);
  shadowGrad.addColorStop(0, "rgba(0, 0, 0, 0.65)");
  shadowGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = shadowGrad;
  ctx.beginPath();
  ctx.ellipse(0, 96, 48, 12, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.translate(0, bounce);

  // Flowing Anime Cape / Scarf
  ctx.save();
  ctx.fillStyle = pal.accent;
  ctx.beginPath();
  ctx.moveTo(-16, -24);
  ctx.quadraticCurveTo(-48 + wind * 14, -10 + bounce, -74 + wind * 24, 18 + wind * 8);
  ctx.quadraticCurveTo(-46 + wind * 10, 8, -12, -8);
  ctx.closePath();
  ctx.fill();
  ctx.restore();

  // Back leg
  ctx.save();
  ctx.translate(-7, 36);
  ctx.rotate(-stride * 0.44);
  ctx.fillStyle = "#1e1b4b";
  ctx.beginPath();
  ctx.roundRect(-7, 0, 14, 52, 6);
  ctx.fill();
  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.roundRect(-6, 44, 20, 14, 4);
  ctx.fill();
  ctx.restore();

  // Back arm
  ctx.save();
  ctx.translate(-14, -16);
  ctx.rotate(stride * 0.52);
  ctx.fillStyle = pal.suit;
  ctx.beginPath();
  ctx.roundRect(-6, 0, 13, 44, 6);
  ctx.fill();
  ctx.restore();

  // Cel-shaded Torso / Anime Academy Coat
  ctx.fillStyle = pal.suit;
  ctx.beginPath();
  ctx.moveTo(-20, -28 - breath * 0.3);
  ctx.lineTo(20, -28 - breath * 0.3);
  ctx.lineTo(24, 38);
  ctx.lineTo(-24, 38);
  ctx.closePath();
  ctx.fill();

  // Sharp cel-shade shadow
  ctx.fillStyle = "rgba(0, 0, 0, 0.28)";
  ctx.beginPath();
  ctx.moveTo(0, -28 - breath * 0.3);
  ctx.lineTo(20, -28 - breath * 0.3);
  ctx.lineTo(24, 38);
  ctx.lineTo(4, 38);
  ctx.closePath();
  ctx.fill();

  // Gold trim / buttons
  ctx.fillStyle = "#fbbf24";
  ctx.beginPath();
  ctx.arc(-2, -12, 2.8, 0, Math.PI * 2);
  ctx.arc(-2, 4, 2.8, 0, Math.PI * 2);
  ctx.arc(-2, 20, 2.8, 0, Math.PI * 2);
  ctx.fill();

  // Front leg
  ctx.save();
  ctx.translate(7, 36);
  ctx.rotate(stride * 0.44);
  ctx.fillStyle = "#312e81";
  ctx.beginPath();
  ctx.roundRect(-7, 0, 14, 52, 6);
  ctx.fill();
  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.roundRect(-6, 44, 20, 14, 4);
  ctx.fill();
  ctx.restore();

  // Anime Head & Neck
  ctx.save();
  ctx.translate(0, -50 - breath * 0.5);
  ctx.rotate(Math.sin(t * 2.2) * 0.05);

  // Sharp anime jawline
  ctx.fillStyle = "#fff1e6";
  ctx.beginPath();
  ctx.moveTo(-18, -20);
  ctx.lineTo(18, -20);
  ctx.lineTo(16, 6);
  ctx.lineTo(0, 24);
  ctx.lineTo(-16, 6);
  ctx.closePath();
  ctx.fill();

  // Cel-shaded jaw shadow
  ctx.fillStyle = "#fcd5ce";
  ctx.beginPath();
  ctx.moveTo(2, -4);
  ctx.lineTo(16, 6);
  ctx.lineTo(0, 24);
  ctx.closePath();
  ctx.fill();

  // Large expressive anime eyes
  const blink = (t % 3.0) > 2.82 ? 0.12 : 1.0;
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.ellipse(8, 2, 6, 8 * blink, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = pal.accent;
  ctx.beginPath();
  ctx.ellipse(9, 2, 4.5, 6.5 * blink, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#090d16";
  ctx.beginPath();
  ctx.arc(9.5, 2, 2.5 * blink, 0, Math.PI * 2);
  ctx.fill();
  if (blink > 0.4) {
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(7.8, -1, 1.6, 0, Math.PI * 2);
    ctx.arc(11.2, 4, 1.0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.strokeStyle = "#090d16";
  ctx.lineWidth = 2.4;
  ctx.beginPath();
  ctx.moveTo(2, -3);
  ctx.lineTo(15, -2);
  ctx.stroke();

  // Stylized anime hair spikes reacting to wind
  ctx.fillStyle = "#1e1b4b";
  ctx.beginPath();
  ctx.moveTo(-22, -18);
  ctx.lineTo(-32 + wind * 6, -34);
  ctx.lineTo(-16, -32);
  ctx.lineTo(-10 + wind * 4, -48);
  ctx.lineTo(4, -36);
  ctx.lineTo(18 + wind * 5, -46);
  ctx.lineTo(18, -28);
  ctx.lineTo(26 + wind * 4, -32);
  ctx.lineTo(20, -12);
  ctx.lineTo(14, 4);
  ctx.lineTo(8, -12);
  ctx.lineTo(-8, -14);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = pal.suitRim;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-12, -34);
  ctx.lineTo(8, -32);
  ctx.stroke();

  ctx.restore();

  // Front arm
  ctx.save();
  ctx.translate(12, -16);
  ctx.rotate(-stride * 0.52);
  ctx.fillStyle = pal.suit;
  ctx.beginPath();
  ctx.roundRect(-6, 0, 13, 44, 6);
  ctx.fill();
  ctx.restore();

  ctx.restore();
}

function drawCartoonCharacter(ctx, cx, cy, scale, t, p) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale * 1.08, scale * 1.08);

  const stride = Math.sin(t * 6.6);
  const bounce = Math.abs(Math.sin(t * 6.6)) * -12;
  const squash = 1.0 + Math.sin(t * 6.6) * 0.08;
  const stretch = 1.0 / squash;

  ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
  ctx.beginPath();
  ctx.ellipse(0, 96, 52 + bounce * 0.5, 12, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.translate(0, bounce);
  ctx.scale(stretch, squash);

  ctx.strokeStyle = "#090d16";
  ctx.lineWidth = 4;

  // Back leg
  ctx.save();
  ctx.translate(-12, 34);
  ctx.rotate(-stride * 0.5);
  ctx.fillStyle = "#1e293b";
  ctx.beginPath();
  ctx.roundRect(-8, 0, 16, 46, 8);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#facc15";
  ctx.beginPath();
  ctx.roundRect(-8, 38, 28, 18, 9);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  // Back arm with glove
  ctx.save();
  ctx.translate(-18, -10);
  ctx.rotate(stride * 0.6);
  ctx.fillStyle = pal.suit;
  ctx.beginPath();
  ctx.roundRect(-8, 0, 16, 38, 8);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(0, 36, 12, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  // Round cartoon body
  ctx.fillStyle = pal.suit;
  ctx.beginPath();
  ctx.ellipse(0, 10, 26, 32, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  // Front leg
  ctx.save();
  ctx.translate(12, 34);
  ctx.rotate(stride * 0.5);
  ctx.fillStyle = "#1e293b";
  ctx.beginPath();
  ctx.roundRect(-8, 0, 16, 46, 8);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#facc15";
  ctx.beginPath();
  ctx.roundRect(-8, 38, 28, 18, 9);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  // Oversized round cartoon head
  ctx.save();
  ctx.translate(0, -42);
  ctx.fillStyle = "#fef08a";
  ctx.beginPath();
  ctx.arc(0, 0, 32, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  // Eyes
  const blink = (t % 2.5) > 2.35 ? 0.1 : 1.0;
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.ellipse(-10, -6, 9, 14 * blink, 0, 0, Math.PI * 2);
  ctx.ellipse(10, -6, 9, 14 * blink, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  if (blink > 0.3) {
    ctx.fillStyle = "#090d16";
    ctx.beginPath();
    ctx.arc(-8 + Math.sin(t * 3) * 2, -6, 4.5, 0, Math.PI * 2);
    ctx.arc(12 + Math.sin(t * 3) * 2, -6, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(-9, -8, 1.8, 0, Math.PI * 2);
    ctx.arc(11, -8, 1.8, 0, Math.PI * 2);
    ctx.fill();
  }

  // Smile
  ctx.beginPath();
  ctx.arc(0, 8, 14, 0.15 * Math.PI, 0.85 * Math.PI);
  ctx.stroke();
  ctx.restore();

  // Front arm
  ctx.save();
  ctx.translate(18, -10);
  ctx.rotate(-stride * 0.6);
  ctx.fillStyle = pal.suit;
  ctx.beginPath();
  ctx.roundRect(-8, 0, 16, 38, 8);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(0, 36, 12, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  ctx.restore();
}

function drawNapoleonCharacter(ctx, cx, cy, scale, t, p) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale * 1.05, scale * 1.05);

  const stride = Math.sin(t * 4.6);
  const bounce = Math.abs(Math.cos(t * 4.6)) * -6;
  const breath = Math.sin(t * 2.4) * 2;
  const wind = Math.sin(t * 3.8);

  const shadowGrad = ctx.createRadialGradient(0, 96, 4, 0, 96, 56);
  shadowGrad.addColorStop(0, "rgba(0, 0, 0, 0.62)");
  shadowGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = shadowGrad;
  ctx.beginPath();
  ctx.ellipse(0, 96, 54, 14, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.translate(0, bounce);

  // General's Cloak blowing behind
  ctx.save();
  ctx.fillStyle = "#64748b";
  ctx.beginPath();
  ctx.moveTo(-18, -20);
  ctx.quadraticCurveTo(-52 + wind * 16, 6 + wind * 8, -68 + wind * 20, 68);
  ctx.lineTo(-24, 72);
  ctx.lineTo(-12, 0);
  ctx.closePath();
  ctx.fill();
  ctx.restore();

  // Back leg
  ctx.save();
  ctx.translate(-8, 38);
  ctx.rotate(-stride * 0.38);
  ctx.fillStyle = "#f8fafc";
  ctx.beginPath();
  ctx.roundRect(-8, 0, 16, 38, 6);
  ctx.fill();
  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.roundRect(-8, 22, 22, 34, 4);
  ctx.fill();
  ctx.restore();

  // Dark Green / Navy Imperial Guard Uniform
  ctx.fillStyle = "#1e3a2b";
  ctx.beginPath();
  ctx.roundRect(-22, -26 - breath * 0.4, 44, 66 + breath * 0.4, 12);
  ctx.fill();

  // Red standing collar
  ctx.fillStyle = "#dc2626";
  ctx.beginPath();
  ctx.roundRect(-16, -34 - breath * 0.5, 32, 10, 4);
  ctx.fill();

  // White waistcoat
  ctx.fillStyle = "#f8fafc";
  ctx.beginPath();
  ctx.moveTo(-10, -24);
  ctx.lineTo(10, -24);
  ctx.lineTo(8, 28);
  ctx.lineTo(-8, 28);
  ctx.closePath();
  ctx.fill();

  // Gold epaulets
  ctx.fillStyle = "#eab308";
  ctx.beginPath();
  ctx.ellipse(-20, -24, 8, 5, 0, 0, Math.PI * 2);
  ctx.ellipse(20, -24, 8, 5, 0, 0, Math.PI * 2);
  ctx.fill();

  // Front leg
  ctx.save();
  ctx.translate(8, 38);
  ctx.rotate(stride * 0.38);
  ctx.fillStyle = "#f8fafc";
  ctx.beginPath();
  ctx.roundRect(-8, 0, 16, 38, 6);
  ctx.fill();
  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.roundRect(-8, 22, 22, 34, 4);
  ctx.fill();
  ctx.restore();

  // Head
  ctx.save();
  ctx.translate(0, -52 - breath * 0.6);
  ctx.fillStyle = "#fed7aa";
  ctx.beginPath();
  ctx.arc(0, 0, 24, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.arc(7, 2, 2.8, 0, Math.PI * 2);
  ctx.fill();

  // Iconic Black Bicorne Hat
  ctx.fillStyle = "#090d16";
  ctx.beginPath();
  ctx.moveTo(-38, -6);
  ctx.quadraticCurveTo(0, -38, 38, -6);
  ctx.quadraticCurveTo(16, -14, 0, -12);
  ctx.quadraticCurveTo(-16, -14, -38, -6);
  ctx.closePath();
  ctx.fill();

  // French Tricolor Cockade
  ctx.fillStyle = "#2563eb";
  ctx.beginPath();
  ctx.arc(14, -14, 5.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(14, -14, 3.8, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#dc2626";
  ctx.beginPath();
  ctx.arc(14, -14, 2.0, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();

  // Signature Napoleon Hand-in-Waistcoat pose
  ctx.save();
  ctx.translate(2, -4);
  ctx.fillStyle = "#1e3a2b";
  ctx.beginPath();
  ctx.roundRect(-4, -14, 16, 28, 8);
  ctx.fill();
  ctx.fillStyle = "#fed7aa";
  ctx.beginPath();
  ctx.arc(4, 12, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  ctx.restore();
}

function drawRobotCharacter(ctx, cx, cy, scale, t, p) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale * 1.05, scale * 1.05);

  const stride = Math.sin(t * 5.2);
  const bounce = Math.abs(Math.sin(t * 5.2)) * -6;

  ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
  ctx.beginPath();
  ctx.ellipse(0, 96, 46, 12, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.translate(0, bounce);

  // Metallic Legs
  ctx.fillStyle = "#475569";
  ctx.fillRect(-14, 38 - stride * 8, 10, 48);
  ctx.fillRect(4, 38 + stride * 8, 10, 48);
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(-16, 80 - stride * 8, 14, 14);
  ctx.fillRect(2, 80 + stride * 8, 14, 14);

  // Metallic Torso with glowing core
  ctx.fillStyle = "#334155";
  ctx.beginPath();
  ctx.roundRect(-22, -22, 44, 58, 10);
  ctx.fill();
  ctx.fillStyle = "#38bdf8";
  ctx.beginPath();
  ctx.arc(0, 6, 11, 0, Math.PI * 2);
  ctx.fill();

  // Robot Head
  ctx.fillStyle = "#475569";
  ctx.beginPath();
  ctx.roundRect(-20, -56, 40, 30, 8);
  ctx.fill();

  // Antenna
  ctx.strokeStyle = "#94a3b8";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(0, -56);
  ctx.lineTo(0, -72);
  ctx.stroke();
  ctx.fillStyle = (Math.sin(t * 8) > 0) ? "#ef4444" : "#f59e0b";
  ctx.beginPath();
  ctx.arc(0, -74, 4.5, 0, Math.PI * 2);
  ctx.fill();

  // Visor
  ctx.fillStyle = "#06b6d4";
  ctx.beginPath();
  ctx.roundRect(-14, -48, 28, 12, 4);
  ctx.fill();

  // Arms
  ctx.fillStyle = "#64748b";
  ctx.fillRect(-28, -16 + stride * 6, 8, 38);
  ctx.fillRect(20, -16 - stride * 6, 8, 38);

  ctx.restore();
}

const CONVERSATIONAL_CAST = {
  alex: { suit: "#1e3a8a", rim: "#93c5fd", skin: "#fde68a", hair: "#1f2937", glasses: false, type: "suit" },
  maya: { suit: "#9d174d", rim: "#fbcfe8", skin: "#fed7aa", hair: "#1f2937", glasses: false, type: "blazer" },
  sam: { suit: "#065f46", rim: "#6ee7b7", skin: "#fcd34d", hair: "#78350f", glasses: true, type: "hoodie" },
  liam: { suit: "#0f766e", rim: "#5eead4", skin: "#fcd34d", hair: "#78350f", glasses: true, type: "hoodie" },
  boss: { suit: "#1e1b4b", rim: "#818cf8", skin: "#c084fc", hair: "#0f172a", glasses: false, type: "suit" },
  employee: { suit: "#0284c7", rim: "#7dd3fc", skin: "#d8b4fe", hair: "#1e293b", glasses: false, type: "shirt" },
  friend: { suit: "#0f766e", rim: "#5eead4", skin: "#a855f7", hair: "#111827", glasses: false, type: "jacket" },
  sarah: { suit: "#1e3a8a", rim: "#38bdf8", skin: "#fed7aa", hair: "#3f2e21", glasses: true, type: "blazer", role: "CTO" },
  mark: { suit: "#334155", rim: "#94a3b8", skin: "#fde68a", hair: "#1e293b", glasses: false, type: "hoodie", role: "Lead Engineer" },
  david: { suit: "#334155", rim: "#cbd5e1", skin: "#fcd34d", hair: "#451a03", glasses: true, type: "suit" },
  founder: { suit: "#0f172a", rim: "#38bdf8", skin: "#fde68a", hair: "#18181b", glasses: false, type: "blazer" },
  investor: { suit: "#1e293b", rim: "#f59e0b", skin: "#fed7aa", hair: "#3f3f46", glasses: true, type: "suit" },
};

function _resolveCastStyle(name, fallbackKey, desc) {
  const low = (name || "").toLowerCase();
  const descLow = (desc || "").toLowerCase();
  let base = null;
  for (const key of Object.keys(CONVERSATIONAL_CAST)) {
    if (low.includes(key)) {
      base = { ...CONVERSATIONAL_CAST[key] };
      break;
    }
  }
  if (!base) {
    let h = 0;
    for (let i = 0; i < low.length; i++) h = (h * 31 + low.charCodeAt(i)) & 0xffffffff;
    const suits = ["#1e3a8a", "#0f766e", "#7c2d12", "#4338ca", "#047857", "#9f1239", "#1e293b", "#2563eb"];
    const rims = ["#93c5fd", "#5eead4", "#fdba74", "#a5b4fc", "#6ee7b7", "#fca5a5", "#94a3b8", "#60a5fa"];
    const skins = ["#fed7aa", "#fde68a", "#fcd34d", "#d8b4fe", "#fed7aa"];
    const hairs = ["#1f2937", "#451a03", "#78350f", "#0f172a", "#374151"];
    const idx = Math.abs(h);
    base = {
      suit: suits[idx % suits.length],
      rim: rims[idx % rims.length],
      skin: skins[idx % skins.length],
      hair: hairs[idx % hairs.length],
      glasses: (idx % 3) === 0,
      type: "suit",
    };
  }
  if (descLow.includes("glasses")) base.glasses = true;
  if (descLow.includes("navy blazer") || descLow.includes("blazer")) {
    base.suit = "#1e3a8a";
    base.type = "blazer";
  }
  if (descLow.includes("hoodie") || descLow.includes("charcoal")) {
    base.suit = "#334155";
    base.type = "hoodie";
  }
  return base;
}

function drawTechSaaSBackground(ctx, w, h, t, p) {
  const bg = ctx.createLinearGradient(0, 0, w, h);
  bg.addColorStop(0, "#030712");
  bg.addColorStop(0.5, "#0b1329");
  bg.addColorStop(1, "#020617");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  // Animated perspective tech grid
  ctx.strokeStyle = "rgba(56, 189, 248, 0.12)";
  ctx.lineWidth = 1.2;
  const gridY = h * 0.44;
  for (let x = 0; x <= w; x += 60) {
    ctx.beginPath();
    ctx.moveTo(x, gridY);
    ctx.lineTo(w * 0.5 + (x - w * 0.5) * 2.2, h);
    ctx.stroke();
  }
  const gridScroll = (t * 40) % 32;
  for (let y = gridY; y <= h; y += 32) {
    const curY = y + gridScroll;
    if (curY <= h) {
      ctx.beginPath();
      ctx.moveTo(0, curY);
      ctx.lineTo(w, curY);
      ctx.stroke();
    }
  }

  // Floating SaaS Dashboard Card in background
  const cardW = w * 0.72;
  const cardH = h * 0.44;
  const cardX = w * 0.14;
  const cardY = h * 0.08;

  ctx.fillStyle = "rgba(15, 23, 42, 0.82)";
  ctx.beginPath();
  ctx.roundRect(cardX, cardY, cardW, cardH, 16);
  ctx.fill();
  ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
  ctx.lineWidth = 2;
  ctx.stroke();

  // Dashboard Header Bar
  ctx.fillStyle = "rgba(30, 41, 59, 0.9)";
  ctx.beginPath();
  ctx.roundRect(cardX, cardY, cardW, 36, [16, 16, 0, 0]);
  ctx.fill();

  for (let i = 0; i < 3; i++) {
    ctx.fillStyle = ["#ef4444", "#f59e0b", "#10b981"][i];
    ctx.beginPath();
    ctx.arc(cardX + 22 + i * 16, cardY + 18, 5, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.fillStyle = "#38bdf8";
  ctx.font = "bold 13px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillText("UNIVERSAL AI VIDEO CLOUD ENGINE // LIVE TELEMETRY", cardX + 78, cardY + 22);

  // Live Animated Performance Metric Wave
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 3.2;
  ctx.beginPath();
  for (let x = 0; x < cardW - 60; x += 8) {
    const normX = x / (cardW - 60);
    const wave = Math.sin((normX * 12.0) + t * 4.2) * 22 + Math.cos((normX * 6.5) - t * 2.8) * 12;
    const py = cardY + cardH * 0.56 + wave;
    if (x === 0) ctx.moveTo(cardX + 30 + x, py);
    else ctx.lineTo(cardX + 30 + x, py);
  }
  ctx.stroke();

  // Live Metric Badges
  const badges = [
    { label: "PIPELINE UPTIME", val: "99.98%", col: "#10b981" },
    { label: "RENDER THROUGHPUT", val: "120 FPS", col: "#38bdf8" },
    { label: "VOICEOVER SYNC", val: "100.0%", col: "#a855f7" }
  ];
  const bW = (cardW - 60) / 3;
  badges.forEach((b, idx) => {
    const bx = cardX + 24 + idx * (bW + 6);
    const by = cardY + cardH * 0.70;
    ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
    ctx.beginPath();
    ctx.roundRect(bx, by, bW, 38, 8);
    ctx.fill();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = "#94a3b8";
    ctx.font = "9px -apple-system, sans-serif";
    ctx.fillText(b.label, bx + 10, by + 14);
    ctx.fillStyle = b.col;
    ctx.font = "bold 13px -apple-system, sans-serif";
    ctx.fillText(b.val, bx + 10, by + 30);
  });
}

function drawOfficeConferenceBackground(ctx, w, h, t, p) {
  // 1. Modern architectural office wall & ceiling
  const wallGrad = ctx.createLinearGradient(0, 0, 0, h);
  wallGrad.addColorStop(0, "#1e293b");
  wallGrad.addColorStop(0.65, "#334155");
  wallGrad.addColorStop(1, "#0f172a");
  ctx.fillStyle = wallGrad;
  ctx.fillRect(0, 0, w, h);

  // Subtle acoustic wood slats on left/right walls
  ctx.fillStyle = "rgba(120, 53, 15, 0.28)";
  for (let x = 20; x < w * 0.16; x += 18) ctx.fillRect(x, 0, 8, h * 0.72);
  for (let x = w * 0.84; x < w - 20; x += 18) ctx.fillRect(x, 0, 8, h * 0.72);

  // Recessed ceiling downlights
  for (let i = 0; i < 4; i++) {
    const lx = w * (0.2 + i * 0.2);
    const glow = ctx.createRadialGradient(lx, 18, 4, lx, 18, h * 0.28);
    glow.addColorStop(0, "rgba(254, 243, 199, 0.35)");
    glow.addColorStop(1, "rgba(254, 243, 199, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(lx - h * 0.28, 0, h * 0.56, h * 0.32);
  }

  // 2. Floor-to-ceiling window with soft-focus city skyline
  const winX = w * 0.18;
  const winY = h * 0.09;
  const winW = w * 0.64;
  const winH = h * 0.54;
  const skyGrad = ctx.createLinearGradient(winX, winY, winX, winY + winH);
  skyGrad.addColorStop(0, "#0f172a");
  skyGrad.addColorStop(0.55, "#1e3a5f");
  skyGrad.addColorStop(1, "#3b82f6");
  ctx.fillStyle = skyGrad;
  ctx.fillRect(winX, winY, winW, winH);

  // Skyline buildings inside window
  ctx.fillStyle = "rgba(15, 23, 42, 0.78)";
  for (let i = 0; i < 11; i++) {
    const bw = winW / 11;
    const bh = winH * (0.28 + ((i * 37 + SCENE_SEED) % 5) * 0.1);
    const bx = winX + i * bw;
    const by = winY + winH - bh;
    ctx.fillRect(bx + 2, by, bw - 4, bh);
    ctx.fillStyle = "rgba(253, 224, 71, 0.26)";
    for (let wy = by + 12; wy < winY + winH - 14; wy += 18) {
      ctx.fillRect(bx + 8, wy, 7, 6);
      ctx.fillRect(bx + bw - 16, wy, 7, 6);
    }
    ctx.fillStyle = "rgba(15, 23, 42, 0.78)";
  }

  // Window mullions
  ctx.strokeStyle = "#0f172a";
  ctx.lineWidth = 6;
  ctx.strokeRect(winX, winY, winW, winH);
  ctx.beginPath();
  ctx.moveTo(winX + winW * 0.33, winY);
  ctx.lineTo(winX + winW * 0.33, winY + winH);
  ctx.moveTo(winX + winW * 0.67, winY);
  ctx.lineTo(winX + winW * 0.67, winY + winH);
  ctx.stroke();

  // 3. Wall-mounted digital presentation screen (animated charts)
  const scrX = w * 0.36;
  const scrY = h * 0.14;
  const scrW = w * 0.28;
  const scrH = h * 0.24;
  ctx.fillStyle = "#090d16";
  ctx.fillRect(scrX - 5, scrY - 5, scrW + 10, scrH + 10);
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(scrX, scrY, scrW, scrH);
  // Chart bars & trend line
  for (let b = 0; b < 5; b++) {
    const bh = scrH * (0.22 + 0.38 * Math.abs(Math.sin(t * 0.7 + b * 0.9)));
    ctx.fillStyle = b === 4 ? "#f43f5e" : "#38bdf8";
    ctx.fillRect(scrX + 18 + b * (scrW * 0.17), scrY + scrH - 16 - bh, scrW * 0.1, bh);
  }
  ctx.strokeStyle = "#fbbf24";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  for (let i = 0; i <= 5; i++) {
    const px = scrX + 18 + i * (scrW * 0.15);
    const py = scrY + scrH * (0.36 + 0.12 * Math.sin(t * 1.1 + i));
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.stroke();
}

function drawConferenceTableForeground(ctx, w, h, t, isTech) {
  const tableY = h * 0.73;
  const tableGrad = ctx.createLinearGradient(0, tableY, 0, h);
  if (isTech) {
    tableGrad.addColorStop(0, "#0f172a");
    tableGrad.addColorStop(0.35, "#090d16");
    tableGrad.addColorStop(1, "#020617");
  } else {
    tableGrad.addColorStop(0, "#3f2e21");
    tableGrad.addColorStop(0.18, "#291d14");
    tableGrad.addColorStop(1, "#110c08");
  }
  ctx.fillStyle = tableGrad;
  ctx.beginPath();
  ctx.moveTo(w * 0.06, tableY);
  ctx.lineTo(w * 0.94, tableY);
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.fill();

  // Polished table rim highlight
  ctx.strokeStyle = isTech ? "#38bdf8" : "rgba(255, 255, 255, 0.16)";
  ctx.lineWidth = isTech ? 2.5 : 3;
  ctx.beginPath();
  ctx.moveTo(w * 0.06, tableY);
  ctx.lineTo(w * 0.94, tableY);
  ctx.stroke();

  // Laptops & coffee mugs on table
  const propsX = [w * 0.25, w * 0.5, w * 0.74];
  propsX.forEach((px, idx) => {
    // Laptop base & angled screen
    ctx.fillStyle = "#64748b";
    ctx.fillRect(px - 32, tableY + 12, 64, 8);
    ctx.fillStyle = idx === 1 ? "#1e293b" : "#334155";
    ctx.fillRect(px - 28, tableY - 22, 56, 34);
    ctx.fillStyle = isTech ? "rgba(56, 189, 248, 0.65)" : "rgba(56, 189, 248, 0.35)";
    ctx.fillRect(px - 24, tableY - 18, 48, 26);

    // Coffee mug
    const mx = px + (idx % 2 === 0 ? 48 : -54);
    ctx.fillStyle = "#f8fafc";
    ctx.fillRect(mx - 8, tableY - 4, 16, 18);
    ctx.strokeStyle = "#f8fafc";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(mx + 8, tableY + 5, 5, -Math.PI / 2, Math.PI / 2);
    ctx.stroke();
  });
}

function drawConversationalCharacter(ctx, cx, cy, scale, t, opts) {
  const style = _resolveCastStyle(opts.name, opts.fallbackKey || "alex", opts.desc || "");
  const isSpeaking = Boolean(opts.isSpeaking && CHARACTER_META && CHARACTER_META.has_speech);
  const lookDir = opts.lookDir || 0; // -1 left, 0 center, 1 right
  const breath = Math.sin(t * 2.1 + (opts.phase || 0)) * 2.2;
  const nod = !isSpeaking ? Math.sin(t * 2.8 + (opts.phase || 0)) * 0.035 : Math.sin(t * 5.2) * 0.04;
  const gesture = isSpeaking ? Math.sin(t * 4.8 + (opts.phase || 0)) : Math.sin(t * 1.2 + (opts.phase || 0)) * 0.15;
  const talkAmp = isSpeaking ? (0.35 + 0.65 * Math.abs(Math.sin(t * 11.5) * Math.cos(t * 5.7))) : 0;
  const blink = (Math.sin(t * 1.9 + (opts.phase || 0)) > 0.96) ? 0.15 : 1.0;

  ctx.save();
  ctx.translate(cx, cy + breath);
  ctx.scale(scale, scale);

  // Ergonomic chair back behind character
  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.roundRect(-42, -54, 84, 110, 18);
  ctx.fill();
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // Torso / Wardrobe
  const torsoGrad = ctx.createLinearGradient(-34, -8, 34, 85);
  torsoGrad.addColorStop(0, style.suit);
  torsoGrad.addColorStop(1, "#090d16");
  ctx.fillStyle = torsoGrad;
  ctx.beginPath();
  ctx.roundRect(-34, -6, 68, 90, 18);
  ctx.fill();

  // Inner Shirt / Top / V-neck
  if (style.type === "hoodie") {
    ctx.fillStyle = "#1e293b";
    ctx.beginPath();
    ctx.ellipse(0, 0, 20, 10, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-6, 6);
    ctx.lineTo(-6 + Math.sin(t * 2.5) * 1.5, 34);
    ctx.moveTo(6, 6);
    ctx.lineTo(6 + Math.sin(t * 2.5 + 1) * 1.5, 34);
    ctx.stroke();
  } else if (style.type === "blazer") {
    ctx.fillStyle = "#f8fafc";
    ctx.beginPath();
    ctx.moveTo(-10, -6);
    ctx.lineTo(0, 24);
    ctx.lineTo(10, -6);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = style.rim || "#38bdf8";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(-22, -6);
    ctx.lineTo(-4, 28);
    ctx.moveTo(22, -6);
    ctx.lineTo(4, 28);
    ctx.stroke();
  } else {
    ctx.fillStyle = "#f8fafc";
    ctx.beginPath();
    ctx.moveTo(-12, -6);
    ctx.lineTo(0, 26);
    ctx.lineTo(12, -6);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#991b1b";
    ctx.beginPath();
    ctx.moveTo(0, 2);
    ctx.lineTo(-5, 45);
    ctx.lineTo(0, 52);
    ctx.lineTo(5, 45);
    ctx.closePath();
    ctx.fill();
  }

  // Articulated arms & hands
  ctx.strokeStyle = style.suit;
  ctx.lineWidth = 14;
  ctx.lineCap = "round";
  // Left arm
  ctx.beginPath();
  ctx.moveTo(-30, 8);
  ctx.quadraticCurveTo(-46, 36, -24 + gesture * 8, 56 - Math.abs(gesture) * 14);
  ctx.stroke();
  // Right arm (main gesturing hand when speaking)
  ctx.beginPath();
  ctx.moveTo(30, 8);
  ctx.quadraticCurveTo(48, 34 - gesture * 10, 26 + gesture * 10, 52 - Math.max(0, gesture) * 20);
  ctx.stroke();
  // Hands
  ctx.fillStyle = style.skin;
  ctx.beginPath();
  ctx.arc(-24 + gesture * 8, 56 - Math.abs(gesture) * 14, 7.5, 0, Math.PI * 2);
  ctx.arc(26 + gesture * 10, 52 - Math.max(0, gesture) * 20, 7.5, 0, Math.PI * 2);
  ctx.fill();

  // Head group (anchored at y = -42)
  ctx.save();
  ctx.translate(0, -42);
  ctx.rotate(nod + lookDir * 0.05);

  // Neck
  ctx.fillStyle = style.skin;
  ctx.fillRect(-9, 18, 18, 16);

  // Head base with skin radial gradient
  const headGrad = ctx.createRadialGradient(-6, -6, 6, 0, 0, 34);
  headGrad.addColorStop(0, style.skin);
  headGrad.addColorStop(1, "#d97706");
  ctx.fillStyle = headGrad;
  ctx.beginPath();
  ctx.arc(0, 0, 31, 0, Math.PI * 2);
  ctx.fill();

  // Hair - dynamic styling based on character
  ctx.fillStyle = style.hair;
  if (style.type === "blazer" || (opts.name || "").toLowerCase().includes("sarah") || (opts.name || "").toLowerCase().includes("maya")) {
    ctx.beginPath();
    ctx.arc(0, -6, 33, Math.PI * 0.95, Math.PI * 2.05);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-32, -4);
    ctx.quadraticCurveTo(-36, 24, -28, 42);
    ctx.lineTo(-20, 38);
    ctx.quadraticCurveTo(-26, 18, -26, -4);
    ctx.closePath();
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(32, -4);
    ctx.quadraticCurveTo(36, 24, 28, 42);
    ctx.lineTo(20, 38);
    ctx.quadraticCurveTo(26, 18, 26, -4);
    ctx.closePath();
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.arc(0, -8, 33, Math.PI, Math.PI * 2);
    ctx.fill();
    ctx.fillRect(-32, -6, 5, 14);
    ctx.fillRect(27, -6, 5, 14);
  }

  // Expressive eyebrows
  const browLift = isSpeaking ? -3.0 * talkAmp : 0;
  ctx.strokeStyle = style.hair;
  ctx.lineWidth = 2.8;
  ctx.beginPath();
  ctx.moveTo(-16, -13 + browLift);
  ctx.lineTo(-5, -14 + browLift);
  ctx.moveTo(5, -14 + browLift);
  ctx.lineTo(16, -13 + browLift);
  ctx.stroke();

  // Eyes with colored iris, pupil, and specular highlight
  const gazeX = lookDir * 2.4;
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.ellipse(-10, -4, 5.8, 5.8 * blink, 0, 0, Math.PI * 2);
  ctx.ellipse(10, -4, 5.8, 5.8 * blink, 0, 0, Math.PI * 2);
  ctx.fill();
  if (blink > 0.35) {
    ctx.fillStyle = "#38bdf8";
    ctx.beginPath();
    ctx.arc(-10 + gazeX, -4, 3.2, 0, Math.PI * 2);
    ctx.arc(10 + gazeX, -4, 3.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#090d16";
    ctx.beginPath();
    ctx.arc(-10 + gazeX, -4, 2.0, 0, Math.PI * 2);
    ctx.arc(10 + gazeX, -4, 2.0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(-10 + gazeX - 1.1, -5.1, 1.1, 0, Math.PI * 2);
    ctx.arc(10 + gazeX - 1.1, -5.1, 1.1, 0, Math.PI * 2);
    ctx.fill();
  }

  // Modern Glasses with subtle glare
  if (style.glasses) {
    ctx.strokeStyle = "#cbd5e1";
    ctx.lineWidth = 2.2;
    ctx.strokeRect(-18, -10, 15, 11);
    ctx.strokeRect(3, -10, 15, 11);
    ctx.beginPath();
    ctx.moveTo(-3, -5);
    ctx.lineTo(3, -5);
    ctx.stroke();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.45)";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(-16, -8);
    ctx.lineTo(-8, -2);
    ctx.moveTo(5, -8);
    ctx.lineTo(13, -2);
    ctx.stroke();
  }

  // Real facial lip-sync mouth with teeth, tongue, and visemes
  if (talkAmp > 0.06) {
    const mouthW = 7.5 + talkAmp * 3.5;
    const mouthH = 2.8 + talkAmp * 6.5;
    ctx.fillStyle = "#3b0712";
    ctx.beginPath();
    ctx.ellipse(0, 14, mouthW, mouthH, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(-mouthW * 0.55, 14 - mouthH * 0.85, mouthW * 1.1, Math.max(2, mouthH * 0.45));
    ctx.fillStyle = "#fb7185";
    ctx.beginPath();
    ctx.ellipse(0, 14 + mouthH * 0.35, mouthW * 0.6, mouthH * 0.45, 0, 0, Math.PI);
    ctx.fill();
    ctx.strokeStyle = "#9f1239";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.ellipse(0, 14, mouthW, mouthH, 0, 0, Math.PI * 2);
    ctx.stroke();
  } else {
    ctx.strokeStyle = "#7c2d12";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.arc(0, 12, 6.5, 0.2, Math.PI - 0.2);
    ctx.stroke();
  }

  ctx.restore();
  ctx.restore();
}

function getActiveSpeakerAtTime(t) {
  const turns = (CHARACTER_META && CHARACTER_META.turns) || [];
  if (Array.isArray(turns) && turns.length > 0) {
    for (const tr of turns) {
      if (t >= tr.start_sec && t <= tr.end_sec) {
        return (tr.speaker || "").toLowerCase();
      }
    }
    return "";
  }
  if (CHARACTER_META && CHARACTER_META.has_speech) {
    return ((CHARACTER_META.speaker || "") + "").toLowerCase();
  }
  return "";
}

function drawSaaSSceneWideIntro(ctx, w, h, t, p, isTech) {
  drawTechSaaSBackground(ctx, w, h, t, p);
  const seatY = h * 0.65;
  const seatScale = (Math.min(w, h) / 680) * 1.15;
  const activeSpk = getActiveSpeakerAtTime(t);
  const leadName = (CHARACTER_META && CHARACTER_META.name) || "Sarah";
  const partnerName = (CHARACTER_META && CHARACTER_META.partner) || "Mark";

  const leadSpeaking = activeSpk ? activeSpk.includes(leadName.toLowerCase()) : true;
  const partnerSpeaking = activeSpk ? activeSpk.includes(partnerName.toLowerCase()) : false;

  drawConversationalCharacter(ctx, w * 0.34, seatY, seatScale, t, {
    name: leadName,
    fallbackKey: "sarah",
    desc: "CTO, wearing a navy blazer and glasses",
    isSpeaking: leadSpeaking,
    lookDir: partnerSpeaking ? 1 : 0.4,
    phase: 0,
  });
  drawConversationalCharacter(ctx, w * 0.66, seatY, seatScale, t, {
    name: partnerName,
    fallbackKey: "mark",
    desc: "Lead Engineer, wearing a charcoal hoodie",
    isSpeaking: partnerSpeaking,
    lookDir: leadSpeaking ? -1 : -0.4,
    phase: 2.3,
  });

  drawConferenceTableForeground(ctx, w, h, t, true);
}

function drawSaaSSpeakerSpotlight(ctx, w, h, t, p) {
  // Dark cinematic tech background with server rack neon indicators & soft bokeh
  const bg = ctx.createLinearGradient(0, 0, w, h);
  bg.addColorStop(0, "#020617");
  bg.addColorStop(0.6, "#0b1329");
  bg.addColorStop(1, "#030712");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  // Background server rack lights
  ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
  ctx.fillRect(w * 0.05, h * 0.08, w * 0.38, h * 0.75);
  for (let r = 0; r < 7; r++) {
    const ry = h * 0.12 + r * 56;
    ctx.strokeStyle = "rgba(56, 189, 248, 0.18)";
    ctx.lineWidth = 1;
    ctx.strokeRect(w * 0.07, ry, w * 0.34, 44);
    for (let c = 0; c < 8; c++) {
      const lit = (Math.sin(t * 5.0 + r * 2 + c) > 0.1);
      ctx.fillStyle = lit ? (c % 2 === 0 ? "#10b981" : "#38bdf8") : "#1e293b";
      ctx.fillRect(w * 0.09 + c * 18, ry + 18, 8, 8);
    }
  }

  // Floating Glassmorphic Holographic Cards on Right
  const cardX = w * 0.52;
  const cardW = w * 0.42;

  // Card 1: 30 FPS Cloud Engine
  const c1Y = h * 0.12;
  ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
  ctx.beginPath();
  ctx.roundRect(cardX, c1Y, cardW, 95, 14);
  ctx.fill();
  ctx.strokeStyle = "rgba(56, 189, 248, 0.45)";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = "#38bdf8";
  ctx.font = "bold 15px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillText("⚡ 30 FPS CLOUD VIDEO ENGINE", cardX + 22, c1Y + 32);
  ctx.fillStyle = "#94a3b8";
  ctx.font = "12px -apple-system, sans-serif";
  ctx.fillText("Real-time distributed compositor in the cloud", cardX + 22, c1Y + 54);
  // Animated progress bar
  ctx.fillStyle = "#1e293b";
  ctx.beginPath();
  ctx.roundRect(cardX + 22, c1Y + 68, cardW - 44, 8, 4);
  ctx.fill();
  ctx.fillStyle = "#38bdf8";
  ctx.beginPath();
  const fillW = (cardW - 44) * (0.65 + Math.sin(t * 3.5) * 0.25);
  ctx.roundRect(cardX + 22, c1Y + 68, fillW, 8, 4);
  ctx.fill();

  // Card 2: Sub-millisecond Voice Sync with Real-Time Audio Equalizer Bars
  const c2Y = h * 0.38;
  ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
  ctx.beginPath();
  ctx.roundRect(cardX, c2Y, cardW, 110, 14);
  ctx.fill();
  ctx.strokeStyle = "rgba(168, 85, 247, 0.45)";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = "#c084fc";
  ctx.font = "bold 15px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillText("🎙️ SUB-MILLISECOND VOICE SYNC", cardX + 22, c2Y + 32);
  ctx.fillStyle = "#94a3b8";
  ctx.font = "12px -apple-system, sans-serif";
  ctx.fillText("Phonetic viseme alignment & neural vocal contrast", cardX + 22, c2Y + 54);

  // 12 Animated Bouncing Equalizer Bars
  const eqX = cardX + 22;
  const eqY = c2Y + 70;
  for (let b = 0; b < 14; b++) {
    const barH = 8 + Math.abs(Math.sin(t * 8.5 + b * 0.7)) * 24;
    const barGrad = ctx.createLinearGradient(0, eqY + 28 - barH, 0, eqY + 28);
    barGrad.addColorStop(0, "#a855f7");
    barGrad.addColorStop(1, "#38bdf8");
    ctx.fillStyle = barGrad;
    ctx.fillRect(eqX + b * 18, eqY + 28 - barH, 11, barH);
  }

  // Card 3: Instant Automated SaaS Production
  const c3Y = h * 0.68;
  ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
  ctx.beginPath();
  ctx.roundRect(cardX, c3Y, cardW, 90, 14);
  ctx.fill();
  ctx.strokeStyle = "rgba(16, 185, 129, 0.45)";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = "#34d399";
  ctx.font = "bold 15px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillText("🚀 INSTANT AUTOMATED PRODUCTION", cardX + 22, c3Y + 32);
  ctx.fillStyle = "#94a3b8";
  ctx.font = "12px -apple-system, sans-serif";
  ctx.fillText("One-click pipeline execution for every SaaS team", cardX + 22, c3Y + 54);
  ctx.fillStyle = "#10b981";
  ctx.font = "bold 12px -apple-system, sans-serif";
  ctx.fillText("● 100% AUTOMATED QA VERIFIED", cardX + 22, c3Y + 72);

  // Prominent foreground speaker on left (scaled ~1.65x)
  const spkName = (CHARACTER_META && CHARACTER_META.speaker) || (CHARACTER_META && CHARACTER_META.name) || "Mark";
  const seatScale = (Math.min(w, h) / 680) * 1.65;
  drawConversationalCharacter(ctx, w * 0.28, h * 0.65, seatScale, t, {
    name: spkName,
    fallbackKey: "mark",
    desc: spkName.toLowerCase().includes("sarah") ? "navy blazer and glasses" : "charcoal hoodie",
    isSpeaking: true,
    lookDir: 0.8,
    phase: 0,
  });

  // Table Foreground
  drawConferenceTableForeground(ctx, w, h, t, true);
}

function drawSaaSArchitectureDemo(ctx, w, h, t, p) {
  drawTechSaaSBackground(ctx, w, h, t, p);

  // 4 Connected Pipeline Nodes in center
  const nodes = [
    { title: "1. PROMPT & SCRIPT", tag: "Hollywood Engine", x: w * 0.18, col: "#38bdf8" },
    { title: "2. NEURAL TTS & SYNC", tag: "Edge Neural Visemes", x: w * 0.40, col: "#a855f7" },
    { title: "3. MULTI-ENGINE RENDER", tag: "Hyperframes / Canvas", x: w * 0.62, col: "#10b981" },
    { title: "4. INSTANT 4K EXPORT", tag: "Automated QA Passed", x: w * 0.84, col: "#f59e0b" },
  ];
  const nodeY = h * 0.38;

  // Animated Glowing Data Stream Line between nodes
  ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(nodes[0].x, nodeY + 30);
  ctx.lineTo(nodes[3].x, nodeY + 30);
  ctx.stroke();

  // Moving glowing energy packets
  for (let pkt = 0; pkt < 5; pkt++) {
    const pktPos = ((t * 180 + pkt * 140) % (nodes[3].x - nodes[0].x)) + nodes[0].x;
    ctx.fillStyle = "#38bdf8";
    ctx.beginPath();
    ctx.arc(pktPos, nodeY + 30, 6, 0, Math.PI * 2);
    ctx.fill();
  }

  // Draw nodes
  nodes.forEach((nd) => {
    ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
    ctx.beginPath();
    ctx.roundRect(nd.x - 70, nodeY, 140, 60, 10);
    ctx.fill();
    ctx.strokeStyle = nd.col;
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 11px -apple-system, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(nd.title, nd.x, nodeY + 24);
    ctx.fillStyle = nd.col;
    ctx.font = "10px -apple-system, sans-serif";
    ctx.fillText(nd.tag, nd.x, nodeY + 44);
    ctx.textAlign = "left";
  });

  // Presenter in bottom-left corner
  const spkName = (CHARACTER_META && CHARACTER_META.speaker) || "Sarah";
  drawConversationalCharacter(ctx, w * 0.22, h * 0.70, (Math.min(w, h) / 680) * 1.35, t, {
    name: spkName,
    fallbackKey: "sarah",
    isSpeaking: true,
    lookDir: 0.6,
  });

  drawConferenceTableForeground(ctx, w, h, t, true);
}

function drawSaaSCallToAction(ctx, w, h, t, p) {
  const bg = ctx.createLinearGradient(0, 0, w, h);
  bg.addColorStop(0, "#020617");
  bg.addColorStop(0.5, "#0b1329");
  bg.addColorStop(1, "#030712");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  // Central Glowing SaaS Orbital Badge
  const badgeX = w * 0.5;
  const badgeY = h * 0.28;
  const pulse = Math.sin(t * 3.5) * 6;
  ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.arc(badgeX, badgeY, 55 + pulse, 0, Math.PI * 2);
  ctx.stroke();

  const bGrad = ctx.createRadialGradient(badgeX, badgeY, 10, badgeX, badgeY, 52);
  bGrad.addColorStop(0, "#38bdf8");
  bGrad.addColorStop(1, "#1d4ed8");
  ctx.fillStyle = bGrad;
  ctx.beginPath();
  ctx.arc(badgeX, badgeY, 46, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 32px -apple-system, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("AI", badgeX, badgeY + 11);

  // Hero Headlines
  ctx.font = "bold 28px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillStyle = "#f8fafc";
  ctx.fillText("AUTOMATE YOUR VIDEO PRODUCTION", badgeX, h * 0.48);

  ctx.font = "15px -apple-system, sans-serif";
  ctx.fillStyle = "#94a3b8";
  ctx.fillText("30 FPS Cloud Engine  •  Sub-Millisecond Voice Sync  •  100% Automated QA", badgeX, h * 0.54);

  // Animated CTA Button
  const btnW = 240;
  const btnH = 52;
  const btnX = badgeX - btnW / 2;
  const btnY = h * 0.60;
  const btnGrad = ctx.createLinearGradient(btnX, btnY, btnX + btnW, btnY);
  btnGrad.addColorStop(0, "#2563eb");
  btnGrad.addColorStop(1, "#7c3aed");
  ctx.fillStyle = btnGrad;
  ctx.beginPath();
  ctx.roundRect(btnX, btnY, btnW, btnH, 26);
  ctx.fill();
  ctx.strokeStyle = "#60a5fa";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 16px -apple-system, sans-serif";
  ctx.fillText("Get Started Free →", badgeX, btnY + 32);
  ctx.textAlign = "left";

  // Both founders standing together flanking the hero screen
  const seatScale = (Math.min(w, h) / 680) * 1.15;
  drawConversationalCharacter(ctx, w * 0.18, h * 0.68, seatScale, t, {
    name: "Sarah",
    fallbackKey: "sarah",
    isSpeaking: false,
    lookDir: 0.7,
  });
  drawConversationalCharacter(ctx, w * 0.82, h * 0.68, seatScale, t, {
    name: "Mark",
    fallbackKey: "mark",
    isSpeaking: false,
    lookDir: -0.7,
  });

  // Upward floating particle sparks
  for (let i = 0; i < 22; i++) {
    const px = ((i * 123 + t * 45) % w);
    const py = (h - ((t * 55 + i * 85) % h));
    ctx.fillStyle = i % 2 === 0 ? "rgba(56, 189, 248, 0.6)" : "rgba(168, 85, 247, 0.6)";
    ctx.beginPath();
    ctx.arc(px, py, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawSceneCharacter(ctx, cx, cy, scale, t, p) {
  const name = ((CHARACTER_META && CHARACTER_META.name) || "").toLowerCase();
  const desc = ((CHARACTER_META && CHARACTER_META.desc) || "").toLowerCase();
  const theme = (THEME || "").toLowerCase();

  if (name.includes("napoleon") || desc.includes("napoleon") || desc.includes("bicorne")) {
    drawNapoleonCharacter(ctx, cx, cy, scale, t, p);
  } else if (name.includes("robot") || desc.includes("robot") || desc.includes("cyborg") || desc.includes("android")) {
    drawRobotCharacter(ctx, cx, cy, scale, t, p);
  } else if (theme === "anime" || desc.includes("anime") || desc.includes("manga")) {
    drawAnimeCharacter(ctx, cx, cy, scale, t, p);
  } else if (theme === "cartoon_2d" || desc.includes("cartoon") || desc.includes("comic") || desc.includes("toon")) {
    drawCartoonCharacter(ctx, cx, cy, scale, t, p);
  } else {
    drawPixarCharacter(ctx, cx, cy, scale, t);
  }
}

window.__renderAtTime = (t) => {
  const w = canvas.width;
  const h = canvas.height;
  const p = Math.max(0, Math.min(1, t / Math.max(0.1, DURATION)));
  const ease = 1 - Math.pow(1 - Math.min(1, p * 2.8), 3);

  if (THEME === "pixel_art") {
    drawPixelArtScene(ctx, w, h, p, t);
    const lt = document.getElementById("lowerThird");
    if (lt && SHOW_HUD) {
      lt.style.opacity = Math.min(1, p * 4.0);
      document.getElementById("bar").style.width = `${(p * 100).toFixed(1)}%`;
    }
    return;
  }

  const isTech = Boolean(CHARACTER_META && CHARACTER_META.is_tech_saas);
  if (isTech) {
    // Dynamic Scene-by-Scene Staging for SaaS Products
    const shotType = String((CHARACTER_META && CHARACTER_META.shot_type) || "").toLowerCase();
    const visDesc = String((CHARACTER_META && CHARACTER_META.desc) || "").toLowerCase();
    const sceneIdx = Number(CHARACTER_META && CHARACTER_META.scene_index !== undefined ? CHARACTER_META.scene_index : 0);
    const totalScenes = Number((CHARACTER_META && CHARACTER_META.total_scenes) || 2);

    let shotMode = "wide_intro";
    if (shotType.includes("close") || shotType.includes("medium") || visDesc.includes("close-up") || visDesc.includes("close up") || (totalScenes === 2 && sceneIdx === 1) || (totalScenes >= 3 && sceneIdx === 1)) {
      shotMode = "speaker_spotlight";
    } else if (shotType.includes("architecture") || visDesc.includes("architecture") || visDesc.includes("workflow") || (totalScenes >= 3 && sceneIdx === 2 && totalScenes > 3)) {
      shotMode = "architecture_demo";
    } else if (shotType.includes("cta") || shotType.includes("outro") || visDesc.includes("cta") || visDesc.includes("call to action") || (totalScenes >= 3 && sceneIdx === totalScenes - 1)) {
      shotMode = "call_to_action";
    } else {
      shotMode = "wide_intro";
    }

    if (shotMode === "speaker_spotlight") {
      drawSaaSSpeakerSpotlight(ctx, w, h, t, p);
    } else if (shotMode === "architecture_demo") {
      drawSaaSArchitectureDemo(ctx, w, h, t, p);
    } else if (shotMode === "call_to_action") {
      drawSaaSCallToAction(ctx, w, h, t, p);
    } else {
      drawSaaSSceneWideIntro(ctx, w, h, t, p, isTech);
    }

    const lt = document.getElementById("lowerThird");
    if (lt && SHOW_HUD) {
      lt.style.opacity = Math.min(1, p * 4.0);
      document.getElementById("bar").style.width = `${(p * 100).toFixed(1)}%`;
    }
    return;
  }

  if (CHARACTER_META && CHARACTER_META.is_interior) {
    drawOfficeConferenceBackground(ctx, w, h, t, p);
    const seatY = h * 0.65;
    const seatScale = (Math.min(w, h) / 680) * 1.15;
    const activeSpk = getActiveSpeakerAtTime(t);
    const leadName = CHARACTER_META.name || "Alex";
    const partnerName = CHARACTER_META.partner || "Maya";
    const thirdName = CHARACTER_META.third || "";

    if (thirdName) {
      drawConversationalCharacter(ctx, w * 0.25, seatY, seatScale * 0.94, t, {
        name: leadName,
        fallbackKey: "alex",
        isSpeaking: activeSpk ? activeSpk.includes(leadName.toLowerCase()) : true,
        lookDir: 1,
        phase: 0,
      });
      drawConversationalCharacter(ctx, w * 0.50, seatY - 6, seatScale * 0.92, t, {
        name: thirdName,
        fallbackKey: "sam",
        isSpeaking: activeSpk ? activeSpk.includes(thirdName.toLowerCase()) : false,
        lookDir: -1,
        phase: 1.7,
      });
      drawConversationalCharacter(ctx, w * 0.75, seatY, seatScale * 0.94, t, {
        name: partnerName,
        fallbackKey: "maya",
        isSpeaking: activeSpk ? activeSpk.includes(partnerName.toLowerCase()) : false,
        lookDir: -1,
        phase: 3.1,
      });
    } else if (partnerName) {
      const isLeadSpeaking = activeSpk ? activeSpk.includes(leadName.toLowerCase()) : true;
      const isPartnerSpeaking = activeSpk ? activeSpk.includes(partnerName.toLowerCase()) : false;
      drawConversationalCharacter(ctx, w * 0.34, seatY, seatScale, t, {
        name: leadName,
        fallbackKey: "alex",
        isSpeaking: isLeadSpeaking,
        lookDir: 1,
        phase: 0,
      });
      drawConversationalCharacter(ctx, w * 0.66, seatY, seatScale, t, {
        name: partnerName,
        fallbackKey: "maya",
        isSpeaking: isPartnerSpeaking,
        lookDir: -1,
        phase: 2.3,
      });
    } else {
      drawConversationalCharacter(ctx, w * 0.50, seatY, seatScale * 1.05, t, {
        name: leadName,
        fallbackKey: "alex",
        isSpeaking: Boolean(activeSpk),
        lookDir: 0,
        phase: 0,
      });
    }
    drawConferenceTableForeground(ctx, w, h, t, false);
    const lt = document.getElementById("lowerThird");
    if (lt && SHOW_HUD) {
      lt.style.opacity = Math.min(1, p * 4.0);
      document.getElementById("bar").style.width = `${(p * 100).toFixed(1)}%`;
    }
    return;
  }

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

  // 4. Midground Animated Architectural / Landscape Silhouette
  ctx.fillStyle = pal.mountMid;
  const scrollMid = (t * 75) % 180;
  for (let i = -1; i < Math.ceil(w / 180) + 2; i++) {
    const bx = i * 180 - scrollMid;
    const bh = h * (0.14 + ((i + SCENE_SEED) % 4) * 0.045);
    const by = h * 0.68 - bh;
    ctx.fillRect(bx, by, 110, bh);
    ctx.fillStyle = "rgba(253, 224, 71, 0.45)";
    for (let wy = by + 16; wy < h * 0.66; wy += 24) {
      ctx.fillRect(bx + 18, wy, 14, 10);
      ctx.fillRect(bx + 46, wy, 14, 10);
      ctx.fillRect(bx + 74, wy, 14, 10);
    }
    ctx.fillStyle = pal.mountMid;
  }

  // 5. Foreground Perspective Ground
  const ground = ctx.createLinearGradient(0, h * 0.66, 0, h);
  ground.addColorStop(0, pal.groundTop);
  ground.addColorStop(1, pal.groundBot);
  ctx.fillStyle = ground;
  ctx.fillRect(0, h * 0.66, w, h * 0.34);

  // 6. Dynamic Visual Style Effects (Anime Speed Lines or Cartoon Outlines)
  if (THEME === "anime") {
    ctx.save();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.22)";
    ctx.lineWidth = 2.5;
    for (let i = 0; i < 9; i++) {
      const ly = (h * 0.11 * i + t * 240) % h;
      ctx.beginPath();
      ctx.moveTo(0, ly);
      ctx.lineTo(w * (0.28 + ((i * 17) % 10) * 0.06), ly);
      ctx.stroke();
    }
    ctx.restore();
  } else if (THEME === "cartoon_2d") {
    ctx.save();
    ctx.strokeStyle = "#090d16";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(0, h * 0.66);
    ctx.lineTo(w, h * 0.66);
    ctx.stroke();
    ctx.restore();
  }

  // 7. One character, or two people facing each other when the scene is a conversation
  const charX = w * (0.28 + p * 0.14);
  const charY = h * 0.62;
  const charScale = Math.min(w, h) / 680;
  const partnerName = (CHARACTER_META && CHARACTER_META.partner) || "";
  if (partnerName) {
    drawSceneCharacter(ctx, w * 0.32, charY, charScale * 0.92, t, p);
    const suit = pal.suit;
    const rim = pal.suitRim;
    pal.suit = pal.accent;
    pal.suitRim = "#f8fafc";
    drawSceneCharacter(ctx, w * 0.68, charY, charScale * 0.92, t, p);
    pal.suit = suit;
    pal.suitRim = rim;
  } else {
    drawSceneCharacter(ctx, charX, charY, charScale, t, p);
  }

  if (THEME === "hand_drawn_storybook") {
    ctx.save();
    ctx.strokeStyle = "rgba(61, 64, 91, 0.42)";
    ctx.lineWidth = 3;
    ctx.strokeRect(18, 18, w - 36, h - 36);
    const vig = ctx.createRadialGradient(w * 0.5, h * 0.5, w * 0.25, w * 0.5, h * 0.5, w * 0.68);
    vig.addColorStop(0, "rgba(246, 239, 226, 0)");
    vig.addColorStop(1, "rgba(109, 89, 122, 0.28)");
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }

  // 8. Atmospheric Particles
  for (let i = 0; i < 28; i++) {
    const px = ((i * 197 + t * (35 + (i % 5) * 12)) % (w + 60)) - 30;
    const py = ((i * 131 - t * (18 + (i % 4) * 8)) % h + h) % h;
    const pr = 2 + (i % 4) * 1.8;
    ctx.fillStyle = i % 2 === 0 ? "rgba(253, 224, 71, 0.38)" : "rgba(56, 189, 248, 0.35)";
    ctx.beginPath();
    ctx.arc(px, py, pr, 0, Math.PI * 2);
    ctx.fill();
  }

  // HUD updates (if enabled)
  if (SHOW_HUD) {
    const lt = document.getElementById("lowerThird");
    if (lt) {
      lt.style.opacity = Math.min(1, p * 4.0);
      lt.style.transform = `translateY(${(1 - ease) * 24}px)`;
      document.getElementById("bar").style.width = `${(p * 100).toFixed(1)}%`;
      const metricNum = (88 + SCENE_SEED % 9 + p * 3.6).toFixed(1);
      document.getElementById("metricVal").textContent = `${metricNum}%`;
    }
  }
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
    from backend.services.document_parser import clean_markdown_inline
    from backend.orchestration.audio_studio import sanitize_spoken_voiceover

    raw_headline = str(scene.get("on_screen_text") or scene.get("title") or "Cinematic Scene")
    clean_title = clean_markdown_inline(raw_headline)[:80]
    title = html_lib.escape(clean_title)

    raw_subline = str(scene.get("narration_segment") or scene.get("narration") or "")
    clean_subline = sanitize_spoken_voiceover(raw_subline, default="")[:180]
    subline = html_lib.escape(clean_subline)

    clean_speaker = clean_markdown_inline(str(scene.get("speaker_name") or "STUDIO ANIMATION"))
    eyebrow = html_lib.escape(f"{category.replace('_', ' ').upper()} • {clean_speaker}")
    raw_style = str(scene.get("visual_style") or scene.get("animation_theme") or "").strip().lower()
    if raw_style in ("anime", "cartoon_2d", "pixel_art", "2d_illustrated", "hand_drawn_storybook", "pixar_character_world", "painterly_parallax", "kinetic_data_hud", "cyberpunk"):
        theme = raw_style
    elif raw_style == "3d_stylized":
        theme = "pixar_character_world"
    elif any(k in raw_style for k in ("anime", "manga", "ghibli", "shonen")):
        theme = "anime"
    elif any(k in raw_style for k in ("cartoon", "comic", "toon")):
        theme = "cartoon_2d"
    elif any(k in raw_style for k in ("cyberpunk", "neon", "sci-fi")):
        theme = "cyberpunk"
    else:
        theme = str(scene.get("animation_theme") or "pixar_character_world")
    vis_desc_low = str(scene.get("visual_description") or "").lower()
    if theme == "pixar_character_world" and any(k in vis_desc_low for k in ("cyberpunk", "flying car", "neon city")):
        theme = "cyberpunk"
    seed = int(scene.get("order_index") or 1) + sum(ord(c) for c in clean_title[:12])

    partner_name = clean_markdown_inline(str(scene.get("partner_name") or ""))
    speaker_name = clean_markdown_inline(str(scene.get("speaker_name") or scene.get("character_name") or ""))
    cat_low = category.lower()
    is_cinematic_narrative = (
        bool(partner_name)
        or theme in ("anime", "cartoon_2d", "hand_drawn_storybook", "pixel_art", "cyberpunk")
        or cat_low in ("documentary", "historical", "film", "cinema", "brand_film", "narrative", "animation")
    )
    show_hud = not is_cinematic_narrative

    is_outdoor_walk = any(k in vis_desc_low for k in ("outdoor", "mountain", "park", "street", "walking outside", "forest"))
    is_tech_saas = any(k in vis_desc_low or k in clean_title.lower() for k in ("saas", "tech", "software", "dashboard", "cloud", "api", "metric", "analytics", "telemetry", "code", "ai model", "platform", "architecture", "database", "server"))
    is_interior = (
        bool(partner_name)
        or is_tech_saas
        or any(k in vis_desc_low for k in ("conference", "office", "layoff", "meeting", "boardroom", "desk", "table", "discussion", "dialogue", "interview", "break room", "two-shot", "three-shot"))
    ) and not is_outdoor_walk
    third_name = clean_markdown_inline(str(scene.get("third_character") or ""))
    if not third_name and is_interior and any(k in vis_desc_low for k in ("three", "three-shot", "sam", "liam")):
        third_name = "Liam" if "liam" in vis_desc_low else "Sam"

    char_meta = {
        "name": clean_markdown_inline(str(scene.get("character_name") or scene.get("title") or "")),
        "desc": str(scene.get("character_description") or scene.get("visual_description") or ""),
        "partner": partner_name,
        "third": third_name,
        "speaker": speaker_name,
        "speaking": "partner" if partner_name and speaker_name.lower() == partner_name.lower() else "lead",
        "is_interior": is_interior,
        "is_tech_saas": is_tech_saas,
        "shot_type": str(scene.get("shot_type") or ""),
        "has_speech": bool(clean_subline and clean_subline.lower() != "silence."),
        "scene_style": "cyberpunk" if ("cyberpunk" in vis_desc_low or "flying car" in vis_desc_low or theme == "cyberpunk") else "",
        "scene_index": int(scene.get("scene_index", scene.get("order_index", 0))),
        "total_scenes": int(scene.get("total_scenes", 2)),
        "turns": scene.get("scene_turns_meta") or [],
        "characters": scene.get("characters_roster") or [],
        "title": clean_title,
    }

    body_class = "" if show_hud else "hide-hud"
    grade_css = {
        "teal_orange": "filter:contrast(1.08) saturate(1.25) hue-rotate(-12deg)",
        "film_noir": "filter:grayscale(1) contrast(1.2)",
        "vibrant_anime": "filter:saturate(1.45) contrast(1.05)",
        "vintage_warm": "filter:sepia(0.25) saturate(1.1)",
        "warm_cinema": "filter:sepia(0.25) saturate(1.1)",
    }.get(str(scene.get("color_grade") or ""), "")
    cinematic_caption_html = ""
    if not show_hud and clean_subline and clean_subline.lower() != "silence.":
        cinematic_caption_html = f'<div class="cinematic-caption">{subline}</div>'

    html = (
        _PIXAR_MOTION_TEMPLATE
        .replace("__BODY_CLASS__", body_class)
        .replace("__BODY_STYLE__", grade_css)
        .replace("__EYEBROW__", eyebrow)
        .replace("__HEADLINE__", title)
        .replace("__SUBLINE__", subline)
        .replace("__THEME__", json.dumps(theme))
        .replace("__SEED__", json.dumps(seed))
        .replace("__DURATION__", json.dumps(duration))
        .replace("__SHOW_HUD__", "true" if show_hud else "false")
        .replace("__CHARACTER_META__", json.dumps(char_meta))
        .replace("__CINEMATIC_CAPTION_HTML__", cinematic_caption_html)
    )
    res = capture_html_to_mp4(
        html, output_mp4, width=width, height=height, fps=fps, duration_sec=duration,
        timeout_sec=max(180, int(duration * fps * 0.45) + 45),
    )
    res["engine"] = "hyperframes"
    return res
