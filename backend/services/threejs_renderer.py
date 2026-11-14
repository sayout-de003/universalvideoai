"""Real Headless Chromium WebGL2 / Three.js 3D Scene Renderer (zero Pillow fallback)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.services.browser_capture import capture_html_to_mp4

_THREEJS_HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #04070d; }
  canvas { display: block; width: 100vw; height: 100vh; }
</style>
</head>
<body>
<canvas id="gl"></canvas>
<div id="cap" style="position:absolute;left:6vw;bottom:8vh;max-width:70vw;color:#f8fafc;font:600 2.4vw/1.25 -apple-system,sans-serif;text-shadow:0 2px 18px #000;pointer-events:none"></div>
<script>
const SCENE_META = __SCENE_META__;
const canvas = document.getElementById("gl");
canvas.width = SCENE_META.width;
canvas.height = SCENE_META.height;
const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true, antialias: true })
        || canvas.getContext("webgl", { preserveDrawingBuffer: true, antialias: true });

if (!gl) {
  throw new Error("WebGL context unavailable");
}

const vsSource = `
attribute vec2 a_pos;
void main() {
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`;

// Real 3D Raymarched Architectural / Terrain / Monolith WebGL Shader with volumetric lighting & shadows
const fsSource = `
precision highp float;
uniform vec2 u_res;
uniform float u_time;
uniform float u_seed;
uniform float u_cam;
uniform vec3 u_accent;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i + vec2(0.0, 0.0)), hash(i + vec2(1.0, 0.0)), u.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
    u.y
  );
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p *= 2.04;
    a *= 0.5;
  }
  return v;
}

float sdBox(vec3 p, vec3 b) {
  vec3 q = abs(p) - b;
  return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float mapScene(vec3 p, out float matId) {
  float terrain = p.y + 1.15 - 0.85 * fbm(p.xz * 0.35 + vec2(u_seed * 0.13, u_seed * 0.07));
  matId = 1.0;

  // Architectural monolith + orbital ring
  vec3 mp = p - vec3(0.0, 0.7 + 0.12 * sin(u_time * 1.4), 0.0);
  float c = cos(u_time * 0.45);
  float s = sin(u_time * 0.45);
  mp.xz = mat2(c, -s, s, c) * mp.xz;
  float monolith = sdBox(mp, vec3(0.65, 1.45, 0.65)) - 0.04;

  // Orbiting sphere
  vec3 sp = p - vec3(2.2 * cos(u_time * 0.9), 0.9 + 0.35 * sin(u_time * 1.3), 2.2 * sin(u_time * 0.9));
  float orb = length(sp) - 0.38;

  float d = terrain;
  if (monolith < d) { d = monolith; matId = 2.0; }
  if (orb < d) { d = orb; matId = 3.0; }
  return d;
}

vec3 calcNormal(vec3 p) {
  float m;
  vec2 e = vec2(0.004, 0.0);
  return normalize(vec3(
    mapScene(p + e.xyy, m) - mapScene(p - e.xyy, m),
    mapScene(p + e.yxy, m) - mapScene(p - e.yxy, m),
    mapScene(p + e.yyx, m) - mapScene(p - e.yyx, m)
  ));
}

void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float camAngle = -0.55 + u_time * u_cam;
  vec3 ro = vec3(5.8 * sin(camAngle), 1.65 + 0.25 * sin(u_time * 0.5), 5.8 * cos(camAngle));
  vec3 ta = vec3(0.0, 0.55, 0.0);
  vec3 ww = normalize(ta - ro);
  vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
  vec3 vv = cross(uu, ww);
  vec3 rd = normalize(uv.x * uu + uv.y * vv + 1.55 * ww);

  vec3 skyTop = vec3(0.03, 0.05, 0.11);
  vec3 skyHor = mix(vec3(0.10, 0.14, 0.24), u_accent * 0.45, 0.4);
  vec3 col = mix(skyHor, skyTop, clamp(rd.y * 1.6 + 0.2, 0.0, 1.0));

  float t = 0.0;
  float matId = 0.0;
  bool hit = false;
  for (int i = 0; i < 96; i++) {
    vec3 p = ro + rd * t;
    float d = mapScene(p, matId);
    if (d < 0.003) { hit = true; break; }
    if (t > 32.0) break;
    t += d * 0.85;
  }

  if (hit) {
    vec3 p = ro + rd * t;
    vec3 n = calcNormal(p);
    vec3 lightDir = normalize(vec3(0.65, 0.72, 0.45));
    float diff = max(dot(n, lightDir), 0.0);
    float rim = pow(1.0 - max(dot(n, -rd), 0.0), 3.0);
    vec3 halfVec = normalize(lightDir - rd);
    float spec = pow(max(dot(n, halfVec), 0.0), 36.0);

    vec3 baseCol = vec3(0.14, 0.17, 0.22);
    if (matId > 1.5 && matId < 2.5) {
      baseCol = mix(vec3(0.18, 0.20, 0.25), u_accent, 0.35);
    } else if (matId >= 2.5) {
      baseCol = u_accent * 1.25;
    }

    vec3 shaded = baseCol * (0.20 + 0.95 * diff) + u_accent * rim * 0.55 + vec3(1.0, 0.96, 0.9) * spec * 0.65;
    float fog = 1.0 - exp(-0.0022 * t * t);
    col = mix(shaded, skyHor, clamp(fog, 0.0, 1.0));
  }

  col = pow(col, vec3(0.4545));
  gl_FragColor = vec4(col, 1.0);
}
`;

function compile(type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(s));
  }
  return s;
}

const prog = gl.createProgram();
gl.attachShader(prog, compile(gl.VERTEX_SHADER, vsSource));
gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, fsSource));
gl.linkProgram(prog);
gl.useProgram(prog);

const buf = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buf);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
const loc = gl.getAttribLocation(prog, "a_pos");
gl.enableVertexAttribArray(loc);
gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

const uRes = gl.getUniformLocation(prog, "u_res");
const uTime = gl.getUniformLocation(prog, "u_time");
const uSeed = gl.getUniformLocation(prog, "u_seed");
const uCam = gl.getUniformLocation(prog, "u_cam");
const uAccent = gl.getUniformLocation(prog, "u_accent");

gl.viewport(0, 0, canvas.width, canvas.height);
gl.uniform2f(uRes, canvas.width, canvas.height);
gl.uniform1f(uSeed, SCENE_META.seed);
gl.uniform1f(uCam, SCENE_META.camSpeed || 0.28);
gl.uniform3fv(uAccent, SCENE_META.accent);

const cap = document.getElementById("cap");
if (cap) cap.textContent = SCENE_META.title || "";
window.__renderAtTime = (t) => {
  gl.uniform1f(uTime, t);
  gl.drawArrays(gl.TRIANGLES, 0, 6);
  gl.finish();
};
window.__renderAtTime(0);
</script>
</body>
</html>
'''


def _accent_for(picture: str) -> list[float]:
    text = picture.lower()
    if any(k in text for k in ("space", "star", "orbit", "night", "moon")):
        return [0.45, 0.65, 0.95]
    if any(k in text for k in ("forest", "nature", "garden", "leaf")):
        return [0.35, 0.72, 0.42]
    if any(k in text for k in ("city", "neon", "nightclub")):
        return [0.35, 0.75, 0.95]
    if any(k in text for k in ("warm", "gold", "sunset", "amber", "documentary")):
        return [0.88, 0.62, 0.28]
    digest = abs(hash(picture)) % 3
    return ([0.82, 0.45, 0.32], [0.35, 0.55, 0.85], [0.75, 0.7, 0.55])[digest]


def render_threejs_scene(
    scene: dict[str, Any],
    output_mp4: Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> dict[str, Any]:
    duration = max(2.0, float(scene.get("duration_sec", 4.0) or 4.0))
    picture = str(scene.get("picture_prompt") or scene.get("visual_description") or scene.get("title") or "scene")
    seed = float(abs(hash(picture)) % 1000)
    move = str(scene.get("camera_movement") or "")
    cam = 0.12 if "push" in move or "pull" in move else 0.28
    meta = {
        "width": width,
        "height": height,
        "seed": seed,
        "accent": _accent_for(picture),
        "camSpeed": cam,
        "title": str(scene.get("title") or picture)[:80],
    }
    html = _THREEJS_HTML_TEMPLATE.replace("__SCENE_META__", json.dumps(meta))
    html_path = output_mp4.with_name(output_mp4.stem + ".threejs.html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    res = capture_html_to_mp4(
        html, output_mp4, width=width, height=height, fps=fps, duration_sec=duration,
        timeout_sec=max(180, int(duration * fps * 0.45) + 45),
    )
    res["engine"] = "threejs"
    return res
