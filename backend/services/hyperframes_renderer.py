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

function drawDialogueSpeakerCharacter(ctx, cx, cy, scale, t, p, cfg) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale, scale);

  const breath = Math.sin(t * 2.5 + (cfg.seed || 0)) * 1.8;
  const isSpeaking = Boolean(cfg.isSpeaking);
  const nod = isSpeaking ? Math.sin(t * 4.6) * 0.05 : Math.sin(t * 1.8 + (cfg.seed || 0)) * 0.02;
  const turnAngle = cfg.turnAngle || 0;

  // 1. High-Back Ergonomic Executive Office Chair (behind character)
  ctx.save();
  ctx.fillStyle = "#0b0f19";
  ctx.strokeStyle = "#1e293b";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(-36, -75, 72, 92, 16);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#1e293b";
  ctx.beginPath();
  ctx.roundRect(-30, -68, 60, 80, 10);
  ctx.fill();
  ctx.fillStyle = "#0f172a";
  ctx.strokeStyle = "#64748b";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(-22, -92, 44, 18, 8);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  // 2. Seated Torso & Clothing
  ctx.save();
  const torsoGrad = ctx.createLinearGradient(-30, -28, 30, 42);
  torsoGrad.addColorStop(0, cfg.rim || "#93c5fd");
  torsoGrad.addColorStop(0.32, cfg.suit || "#1e3a8a");
  torsoGrad.addColorStop(1, "#0f172a");
  ctx.fillStyle = torsoGrad;
  ctx.beginPath();
  ctx.roundRect(-28, -26 - breath * 0.4, 56, 56, 18);
  ctx.fill();

  // Crisp Inner Shirt / Blouse & Lapels
  ctx.fillStyle = cfg.shirt || "#f8fafc";
  ctx.beginPath();
  ctx.moveTo(-10, -26 - breath * 0.4);
  ctx.lineTo(10, -26 - breath * 0.4);
  ctx.lineTo(6, 4);
  ctx.lineTo(-6, 4);
  ctx.closePath();
  ctx.fill();

  // Tie or Necklace / Details
  if (cfg.tie) {
    ctx.fillStyle = cfg.tie;
    ctx.beginPath();
    ctx.moveTo(-3, -22);
    ctx.lineTo(3, -22);
    ctx.lineTo(4, 16);
    ctx.lineTo(0, 22);
    ctx.lineTo(-4, 16);
    ctx.closePath();
    ctx.fill();
  } else if (cfg.necklace) {
    ctx.strokeStyle = cfg.necklace;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, -18, 9, 0.2, Math.PI - 0.2);
    ctx.stroke();
    ctx.fillStyle = "#fbbf24";
    ctx.beginPath();
    ctx.arc(0, -9, 2.8, 0, Math.PI * 2);
    ctx.fill();
  }

  // Lapel collars
  ctx.strokeStyle = cfg.rim || "#60a5fa";
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(-22, -26);
  ctx.lineTo(-6, 4);
  ctx.lineTo(0, 18);
  ctx.moveTo(22, -26);
  ctx.lineTo(6, 4);
  ctx.lineTo(0, 18);
  ctx.stroke();
  ctx.restore();

  // 3. Arms & Conversational Gestures
  ctx.save();
  // Left Arm (rests naturally on table)
  ctx.fillStyle = cfg.suit || "#1e3a8a";
  ctx.beginPath();
  ctx.roundRect(-34, -14, 14, 42, 7);
  ctx.fill();
  ctx.fillStyle = "#fed7aa";
  ctx.beginPath();
  ctx.ellipse(-26, 28, 8, 5.5, -0.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  // Right Arm (expressive gesture if speaking, resting/listening if not)
  ctx.save();
  if (isSpeaking) {
    ctx.translate(22, -14);
    ctx.rotate(0.35 + Math.sin(t * 4.6) * 0.18);
    ctx.fillStyle = cfg.suit || "#1e3a8a";
    ctx.beginPath();
    ctx.roundRect(-6, 0, 14, 38, 7);
    ctx.fill();
    ctx.translate(1, 34);
    ctx.rotate(-0.85 + Math.sin(t * 4.6) * 0.12);
    ctx.fillStyle = cfg.suit || "#1e3a8a";
    ctx.beginPath();
    ctx.roundRect(-5, 0, 12, 32, 6);
    ctx.fill();
    ctx.translate(1, 30);
    ctx.fillStyle = "#fed7aa";
    ctx.beginPath();
    ctx.ellipse(0, 0, 9, 7, 0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#fba562";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(-4, 0); ctx.lineTo(-6, -6);
    ctx.moveTo(0, 0); ctx.lineTo(0, -8);
    ctx.moveTo(4, 0); ctx.lineTo(5, -7);
    ctx.stroke();
  } else {
    ctx.fillStyle = cfg.suit || "#1e3a8a";
    ctx.beginPath();
    ctx.roundRect(20, -14, 14, 42, 7);
    ctx.fill();
    ctx.fillStyle = "#fed7aa";
    ctx.beginPath();
    ctx.ellipse(26, 28, 8, 5.5, 0.2, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  // 4. Head & Face
  ctx.save();
  ctx.translate(0, -52 - breath * 0.5);
  ctx.rotate(nod + turnAngle * 0.3);

  const headGrad = ctx.createRadialGradient(-8, -10, 5, 0, 0, 32);
  headGrad.addColorStop(0, "#fed7aa");
  headGrad.addColorStop(0.68, "#fb923c");
  headGrad.addColorStop(1, "#c2410c");
  ctx.fillStyle = headGrad;
  ctx.beginPath();
  ctx.arc(0, 0, 28, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = cfg.hair || "#0f172a";
  ctx.beginPath();
  if (cfg.name === "Maya") {
    ctx.arc(0, -6, 31, Math.PI * 0.9, Math.PI * 2.1);
    ctx.quadraticCurveTo(28, 18, 26, 34);
    ctx.quadraticCurveTo(16, 28, 12, 18);
    ctx.quadraticCurveTo(-14, 20, -26, 34);
    ctx.quadraticCurveTo(-28, 16, -30, -6);
  } else if (cfg.name === "Liam") {
    ctx.arc(-2, -6, 29, Math.PI * 0.95, Math.PI * 2.05);
    ctx.quadraticCurveTo(22, -34, -18, -30);
  } else {
    ctx.arc(-3, -8, 29, Math.PI * 0.95, Math.PI * 2.05);
    ctx.quadraticCurveTo(18, -36, -18, -32);
  }
  ctx.fill();

  // Eyebrows (Earnest / concerned expressions about layoffs)
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 2.4;
  ctx.beginPath();
  const browRaise = isSpeaking ? Math.sin(t * 4.6) * 1.5 : 0;
  ctx.moveTo(-18, -11 - browRaise);
  ctx.quadraticCurveTo(-11, -16 - browRaise, -4, -12 - browRaise);
  ctx.moveTo(4, -12 - browRaise);
  ctx.quadraticCurveTo(11, -16 - browRaise, 18, -11 - browRaise);
  ctx.stroke();

  // Expressive Eyes with natural blinking & gaze direction
  const blinkCycle = (t % 3.6 + (cfg.seed || 0) * 0.5) % 3.6;
  const blink = blinkCycle > 3.42 ? 0.12 : 1.0;
  const gazeX = cfg.turnAngle > 0 ? 2.5 : (cfg.turnAngle < 0 ? -2.5 : 0);

  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.ellipse(-11, -2, 6.2, 7.2 * blink, 0, 0, Math.PI * 2);
  ctx.ellipse(11, -2, 6.2, 7.2 * blink, 0, 0, Math.PI * 2);
  ctx.fill();

  if (blink > 0.3) {
    ctx.fillStyle = cfg.eyeColor || "#1e293b";
    ctx.beginPath();
    ctx.arc(-11 + gazeX, -2, 3.4, 0, Math.PI * 2);
    ctx.arc(11 + gazeX, -2, 3.4, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(-10 + gazeX, -3.5, 1.3, 0, Math.PI * 2);
    ctx.arc(12 + gazeX, -3.5, 1.3, 0, Math.PI * 2);
    ctx.fill();
  }

  if (cfg.glasses) {
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.roundRect(-19, -8, 16, 13, 3);
    ctx.roundRect(3, -8, 16, 13, 3);
    ctx.moveTo(-3, -2); ctx.lineTo(3, -2);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(154, 52, 18, 0.4)";
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  ctx.moveTo(0, -3);
  ctx.lineTo(2, 5);
  ctx.lineTo(-2, 7);
  ctx.stroke();

  // 5. AUTHENTIC ANIMATED MOUTH / VISEMES (Accurately positioned at y = 14)
  if (isSpeaking) {
    const talkCadence = Math.max(0, Math.sin(t * 4.2));
    const syllableWave = Math.abs(Math.sin(t * 9.2)) * 5.2 + Math.abs(Math.cos(t * 14.8)) * 2.2;
    const mouthOpen = Math.max(2.0, syllableWave * talkCadence);
    const mouthWidth = 7.0 + talkCadence * 2.5;

    ctx.fillStyle = "#1e1b4b";
    ctx.beginPath();
    ctx.ellipse(0, 14, mouthWidth, mouthOpen, 0, 0, Math.PI * 2);
    ctx.fill();

    if (mouthOpen > 3.5) {
      ctx.fillStyle = "#f8fafc";
      ctx.fillRect(-mouthWidth * 0.6, 14 - mouthOpen + 0.8, mouthWidth * 1.2, 2.4);
      ctx.fillStyle = "#f43f5e";
      ctx.beginPath();
      ctx.ellipse(0, 14 + mouthOpen - 1.5, mouthWidth * 0.55, 2.0, 0, 0, Math.PI);
      ctx.fill();
    }

    ctx.strokeStyle = "#9a3412";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.ellipse(0, 14, mouthWidth + 0.5, mouthOpen + 0.5, 0, 0, Math.PI * 2);
    ctx.stroke();
  } else {
    ctx.strokeStyle = "#9a3412";
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    ctx.moveTo(-6, 14);
    ctx.quadraticCurveTo(0, 15.8, 6, 14);
    ctx.stroke();
  }

  ctx.restore();
  ctx.restore();
}

function drawConferenceRoomScene(ctx, w, h, p, t, charMeta) {
  // 1. Sleek corporate wall & architectural downlights
  const wallGrad = ctx.createLinearGradient(0, 0, 0, h * 0.68);
  wallGrad.addColorStop(0, "#080d1a");
  wallGrad.addColorStop(0.5, "#0f172a");
  wallGrad.addColorStop(1, "#1e293b");
  ctx.fillStyle = wallGrad;
  ctx.fillRect(0, 0, w, h);

  // 2. Floor-to-Ceiling Skyline Windows (Left 50%)
  const winW = w * 0.52;
  const winH = h * 0.62;
  ctx.save();
  const skyGrad = ctx.createLinearGradient(0, 0, 0, winH);
  skyGrad.addColorStop(0, "#1e3a8a");
  skyGrad.addColorStop(0.65, "#3b82f6");
  skyGrad.addColorStop(1, "#93c5fd");
  ctx.fillStyle = skyGrad;
  ctx.fillRect(0, 0, winW, winH);

  for (let b = 0; b < 10; b++) {
    const bx = b * (winW / 9);
    const bw = winW / 11;
    const bh = winH * (0.35 + ((b * 37) % 5) * 0.08);
    ctx.fillStyle = b % 2 === 0 ? "#1e293b" : "#0f172a";
    ctx.fillRect(bx, winH - bh, bw, bh);
    ctx.fillStyle = "rgba(253, 224, 71, 0.45)";
    for (let wy = winH - bh + 12; wy < winH - 10; wy += 18) {
      if ((b + wy) % 3 !== 0) {
        ctx.fillRect(bx + 4, wy, bw - 8, 8);
      }
    }
  }

  ctx.strokeStyle = "rgba(15, 23, 42, 0.85)";
  ctx.lineWidth = 6;
  ctx.strokeRect(0, 0, winW, winH);
  ctx.beginPath();
  ctx.moveTo(winW * 0.33, 0); ctx.lineTo(winW * 0.33, winH);
  ctx.moveTo(winW * 0.66, 0); ctx.lineTo(winW * 0.66, winH);
  ctx.moveTo(0, winH * 0.45); ctx.lineTo(winW, winH * 0.45);
  ctx.stroke();

  const glassRef = ctx.createLinearGradient(0, 0, winW, winH);
  glassRef.addColorStop(0, "rgba(255, 255, 255, 0.12)");
  glassRef.addColorStop(0.3, "rgba(255, 255, 255, 0.02)");
  glassRef.addColorStop(1, "rgba(255, 255, 255, 0.06)");
  ctx.fillStyle = glassRef;
  ctx.fillRect(0, 0, winW, winH);
  ctx.restore();

  // 3. Acoustic Wood Slat Accent Wall (Right 50%)
  ctx.save();
  ctx.fillStyle = "#111827";
  ctx.fillRect(winW, 0, w - winW, winH);
  for (let s = winW + 10; s < w; s += 24) {
    ctx.fillStyle = "#451a03";
    ctx.fillRect(s, 0, 10, winH);
    ctx.fillStyle = "#78350f";
    ctx.fillRect(s + 2, 0, 6, winH);
  }

  // 4. Digital Wall Display / Smart Telemetry Screen
  const dispX = w * 0.58;
  const dispY = h * 0.08;
  const dispW = w * 0.38;
  const dispH = h * 0.46;
  ctx.fillStyle = "#030712";
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.roundRect(dispX, dispY, dispW, dispH, 12);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#38bdf8";
  ctx.font = "bold 13px Inter, sans-serif";
  ctx.fillText("● LIVE // WORKFORCE RESTRUCTURING METRICS", dispX + 16, dispY + 24);

  const barColors = ["#ef4444", "#f59e0b", "#38bdf8", "#10b981"];
  const barLabels = ["Overhead", "Impact", "Severance", "Resilience"];
  const barValues = [0.85, 0.72, 0.60, 0.94];
  for (let k = 0; k < 4; k++) {
    const kx = dispX + 24 + k * (dispW / 4.4);
    const kw = dispW / 5.5;
    const maxBarH = dispH * 0.42;
    const pulse = Math.sin(t * 3.0 + k) * 6;
    const kh = Math.max(12, maxBarH * barValues[k] + pulse);
    const ky = dispY + dispH - 42 - kh;
    ctx.fillStyle = barColors[k];
    ctx.beginPath();
    ctx.roundRect(kx, ky, kw, kh, 4);
    ctx.fill();
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px Inter, sans-serif";
    ctx.fillText(barLabels[k], kx, dispY + dispH - 24);
  }

  ctx.strokeStyle = "rgba(56, 189, 248, 0.75)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let wx = 0; wx < dispW - 32; wx += 8) {
    const waveY = dispY + dispH * 0.48 + Math.sin((wx + t * 50) * 0.06) * 14;
    if (wx === 0) ctx.moveTo(dispX + 16 + wx, waveY);
    else ctx.lineTo(dispX + 16 + wx, waveY);
  }
  ctx.stroke();
  ctx.restore();

  // 5. Three Characters Staged Around the Table
  let activeIdx = 0;
  const spkName = String((charMeta && charMeta.speaker_name) || "").toLowerCase();
  if (spkName.includes("maya") || (charMeta && charMeta.speaking_index === 1)) activeIdx = 1;
  else if (spkName.includes("liam") || (charMeta && charMeta.speaking_index === 2)) activeIdx = 2;
  else if (charMeta && charMeta.speaking_index !== undefined) activeIdx = Number(charMeta.speaking_index) % 3;

  const charScale = Math.min(w, h) / 640;
  const charY = h * 0.58;
  const positions = [
    {
      x: w * 0.22, name: "Alex", suit: "#1e3a8a", rim: "#93c5fd", shirt: "#e0f2fe", tie: "#1e40af",
      hair: "#0f172a", turnAngle: 0.15, seed: 0,
    },
    {
      x: w * 0.50, name: "Maya", suit: "#9d174d", rim: "#f472b6", shirt: "#fdf2f8", necklace: "#fbbf24",
      hair: "#271c19", turnAngle: (activeIdx === 0 ? -0.18 : (activeIdx === 2 ? 0.18 : 0.0)), seed: 1,
    },
    {
      x: w * 0.78, name: "Liam", suit: "#065f46", rim: "#6ee7b7", shirt: "#f0fdf4", glasses: true,
      hair: "#1c1917", turnAngle: -0.15, seed: 2,
    },
  ];

  positions.forEach((pos, idx) => {
    const isSpeaking = (idx === activeIdx);
    drawDialogueSpeakerCharacter(ctx, pos.x, charY, charScale * 0.88, t, p, {
      ...pos,
      isSpeaking: isSpeaking,
    });

    ctx.save();
    const tagY = charY - charScale * 135;
    ctx.font = "bold 13px Inter, sans-serif";
    const tagText = isSpeaking ? `● ${pos.name} (talking)` : pos.name;
    const tw = ctx.measureText(tagText).width;
    ctx.fillStyle = isSpeaking ? "rgba(225, 29, 72, 0.94)" : "rgba(15, 23, 42, 0.80)";
    ctx.beginPath();
    ctx.roundRect(pos.x - tw / 2 - 12, tagY - 14, tw + 24, 24, 8);
    ctx.fill();
    ctx.strokeStyle = isSpeaking ? "#fda4af" : "rgba(255, 255, 255, 0.25)";
    ctx.lineWidth = 1.4;
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.fillText(tagText, pos.x, tagY + 3);
    ctx.restore();
  });

  // 6. Perspective Conference Boardroom Table (Across Foreground)
  const tableY = h * 0.65;
  ctx.save();
  const tableGrad = ctx.createLinearGradient(0, tableY, 0, h);
  tableGrad.addColorStop(0, "#1e293b");
  tableGrad.addColorStop(0.2, "#0f172a");
  tableGrad.addColorStop(1, "#020617");
  ctx.fillStyle = tableGrad;
  ctx.beginPath();
  ctx.moveTo(0, tableY + 24);
  ctx.quadraticCurveTo(w * 0.5, tableY - 12, w, tableY + 24);
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = "#94a3b8";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(0, tableY + 24);
  ctx.quadraticCurveTo(w * 0.5, tableY - 12, w, tableY + 24);
  ctx.stroke();

  // 7. Desk Props in front of each participant
  positions.forEach((pos) => {
    ctx.save();
    const lapW = charScale * 68;
    const lapH = charScale * 42;
    const lapX = pos.x;
    const lapY = tableY + 32;

    ctx.fillStyle = "#1e293b";
    ctx.strokeStyle = "#475569";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(lapX - lapW * 0.45, lapY - lapH, lapW * 0.9, lapH, 4);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "#0284c7";
    ctx.fillRect(lapX - lapW * 0.40, lapY - lapH + 5, lapW * 0.8, lapH - 10);
    ctx.fillStyle = "#e0f2fe";
    for (let r = 0; r < 4; r++) {
      ctx.fillRect(lapX - lapW * 0.36, lapY - lapH + 10 + r * 6, (lapW * 0.45) + ((r * 13) % 15), 2.5);
    }

    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.roundRect(lapX - lapW * 0.5, lapY, lapW, 14, 3);
    ctx.fill();
    ctx.stroke();

    const mugX = lapX + lapW * 0.58;
    const mugY = lapY + 4;
    ctx.fillStyle = "#f8fafc";
    ctx.beginPath();
    ctx.roundRect(mugX, mugY - 18, 14, 20, 3);
    ctx.fill();
    ctx.strokeStyle = "#f8fafc";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(mugX + 14, mugY - 8, 4, -Math.PI / 2, Math.PI / 2);
    ctx.stroke();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.45)";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    const steamWisp = Math.sin(t * 3.2 + pos.seed) * 3;
    ctx.moveTo(mugX + 7, mugY - 20);
    ctx.quadraticCurveTo(mugX + 7 + steamWisp, mugY - 30, mugX + 7 - steamWisp, mugY - 38);
    ctx.stroke();
    ctx.restore();
  });
  ctx.restore();
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

  const isDialogueScene = Boolean(CHARACTER_META && (CHARACTER_META.three_people || CHARACTER_META.partner || (CHARACTER_META.characters && CHARACTER_META.characters.length >= 2)));
  const sceneDesc = ((CHARACTER_META && CHARACTER_META.desc) || "").toLowerCase();
  const sceneName = ((CHARACTER_META && CHARACTER_META.name) || "").toLowerCase();
  const isOfficeOrMeeting = isDialogueScene || /office|conference|meeting|boardroom|layoff|playoff|workplace|desk|indoor|interior|job layout|modern area/i.test(sceneDesc + " " + sceneName);

  if (isOfficeOrMeeting) {
    drawConferenceRoomScene(ctx, w, h, p, t, CHARACTER_META);
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

  // 7. Characters: One character, two people, or three people in animated group dialogue
  const charX = w * (0.28 + p * 0.14);
  const charY = h * 0.62;
  const charScale = Math.min(w, h) / 680;
  const partnerName = (CHARACTER_META && CHARACTER_META.partner) || "";
  const isThree = Boolean(CHARACTER_META && (CHARACTER_META.three_people || (CHARACTER_META.characters && CHARACTER_META.characters.length >= 3)));

  if (isThree) {
    const chars = (CHARACTER_META.characters && CHARACTER_META.characters.length >= 3)
      ? CHARACTER_META.characters
      : ["Alex", "Maya", "Liam"];
    const spk = String(CHARACTER_META.speaking || "").toLowerCase();
    const spkName = String(CHARACTER_META.speaker_name || "").toLowerCase();
    let activeIdx = 0;
    if (spk === "center" || spkName.includes("maya") || spk === "maya" || spk === "character_2") activeIdx = 1;
    else if (spk === "right" || spkName.includes("liam") || spk === "liam" || spk === "character_3") activeIdx = 2;
    else if (CHARACTER_META.speaking_index !== undefined) activeIdx = Number(CHARACTER_META.speaking_index) % 3;

    const talk = Math.abs(Math.sin(t * 8.5));
    const baseScale = charScale * 0.82;
    const positions = [
      { x: w * 0.22, name: chars[0], suit: "#1e3a8a", rim: "#93c5fd" },
      { x: w * 0.50, name: chars[1], suit: "#9d174d", rim: "#f472b6" },
      { x: w * 0.78, name: chars[2], suit: "#065f46", rim: "#6ee7b7" },
    ];

    positions.forEach((pos, idx) => {
      const isSpeaking = (idx === activeIdx);
      const nod = isSpeaking ? Math.sin(t * 3.5) * 4 : Math.sin(t * 2.2 + idx) * 2;
      const suitBackup = pal.suit;
      const rimBackup = pal.suitRim;
      pal.suit = pos.suit;
      pal.suitRim = pos.rim;

      ctx.save();
      if (idx === 0) {
        drawSceneCharacter(ctx, pos.x, charY + nod, baseScale, t, p);
      } else if (idx === 1) {
        drawSceneCharacter(ctx, pos.x, charY + nod, baseScale * 1.02, t, p);
      } else {
        ctx.translate(pos.x, 0);
        ctx.scale(-1, 1);
        ctx.translate(-pos.x, 0);
        drawSceneCharacter(ctx, pos.x, charY + nod, baseScale, t, p);
      }
      ctx.restore();

      pal.suit = suitBackup;
      pal.suitRim = rimBackup;

      if (isSpeaking) {
        const mouthX = pos.x;
        ctx.fillStyle = "#0f172a";
        ctx.beginPath();
        ctx.ellipse(mouthX, charY + nod - baseScale * 16, 5 + talk * 3, 2.5 + talk * 6, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.save();
      const tagY = charY - baseScale * 125;
      ctx.font = "bold 13px Inter, sans-serif";
      const tagText = isSpeaking ? `● ${pos.name} (talking)` : pos.name;
      const tw = ctx.measureText(tagText).width;
      ctx.fillStyle = isSpeaking ? "rgba(225, 29, 72, 0.92)" : "rgba(15, 23, 42, 0.75)";
      ctx.beginPath();
      ctx.roundRect(pos.x - tw / 2 - 10, tagY - 14, tw + 20, 22, 6);
      ctx.fill();
      ctx.strokeStyle = isSpeaking ? "#fda4af" : "rgba(255, 255, 255, 0.25)";
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.fillText(tagText, pos.x, tagY + 2);
      ctx.restore();
    });
  } else if (partnerName) {
    const talk = Math.abs(Math.sin(t * 8));
    const speakerOnRight = (CHARACTER_META.speaking || "") === "partner";
    drawSceneCharacter(ctx, w * 0.32, charY, charScale * 0.92, t, p);
    const suit = pal.suit;
    const rim = pal.suitRim;
    pal.suit = pal.accent;
    pal.suitRim = "#f8fafc";
    drawSceneCharacter(ctx, w * 0.68, charY, charScale * 0.92, t, p);
    pal.suit = suit;
    pal.suitRim = rim;
    const mouthX = speakerOnRight ? w * 0.68 : w * 0.32;
    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.ellipse(mouthX, charY - charScale * 16, 6 + talk * 3, 3 + talk * 7, 0, 0, Math.PI * 2);
    ctx.fill();
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

    chars_list = scene.get("characters") or []
    is_three = bool(scene.get("three_people")) or len(chars_list) >= 3 or any(
        k in (clean_title + " " + vis_desc_low).lower() for k in ("three people", "3 people", "three characters", "3 characters", "trio")
    )
    if is_three and len(chars_list) < 3:
        chars_list = ["Alex", "Maya", "Liam"]

    speaking_idx = 0
    if speaker_name:
        for idx, cname in enumerate(chars_list):
            if cname.lower() in speaker_name.lower():
                speaking_idx = idx
                break
    else:
        speaking_idx = int(scene.get("speaking_index") or 0) % max(1, len(chars_list))

    char_meta = {
        "name": clean_markdown_inline(str(scene.get("character_name") or scene.get("title") or "")),
        "desc": str(scene.get("character_description") or scene.get("visual_description") or ""),
        "partner": partner_name,
        "three_people": is_three,
        "characters": chars_list if is_three else [],
        "speaker_name": speaker_name or (chars_list[speaking_idx] if is_three else ""),
        "speaking_index": speaking_idx,
        "speaking": "partner" if partner_name and speaker_name.lower() == partner_name.lower() else "lead",
        "scene_style": "cyberpunk" if ("cyberpunk" in vis_desc_low or "flying car" in vis_desc_low or theme == "cyberpunk") else "",
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
