"""Real Remotion CLI Renderer via OpenMontage remotion-composer (Motion Graphics, Charts, Typography, Captions, Transitions)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from backend.config import OPENMONTAGE_DIR


def get_remotion_status() -> dict[str, Any]:
    rc_dir = OPENMONTAGE_DIR / "remotion-composer"
    has_npx = shutil.which("npx") is not None
    has_modules = (rc_dir / "node_modules" / ".bin" / "remotion").is_file() or (rc_dir / "node_modules" / "@remotion").is_dir()
    if not rc_dir.is_dir() or not has_npx or not has_modules:
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "reason": "Remotion dependencies not installed in integrations/OpenMontage/remotion-composer (run npm install).",
        }
    return {"available": True, "status": "READY", "reason": None}


def _build_cuts_from_scene(scene: dict[str, Any], duration: float) -> list[dict[str, Any]]:
    if isinstance(scene.get("remotion_cuts"), list) and scene["remotion_cuts"]:
        return scene["remotion_cuts"]

    title = str(scene.get("on_screen_text") or scene.get("title") or "Scene")[:90]
    visual = str(scene.get("picture_prompt") or scene.get("visual_description") or scene.get("generation_prompt") or "")[:180]
    text_blob = f"{title} {visual}".lower()

    if scene.get("chart_data"):
        chart_type = str(scene.get("chart_type") or "bar_chart")
        return [
            {
                "type": chart_type,
                "chartData": scene["chart_data"],
                "chartAnimation": "spring",
                "showValues": True,
                "showGrid": True,
                "in_seconds": 0,
                "out_seconds": round(duration, 3),
            }
        ]

    if any(k in text_blob for k in ("chart", "growth", "metric", "revenue", "percent", "benchmark", "analytics")):
        mid = round(duration * 0.42, 3)
        return [
            {
                "type": "hero_title",
                "text": title,
                "heroSubtitle": visual,
                "in_seconds": 0,
                "out_seconds": mid,
            },
            {
                "type": "bar_chart",
                "chartData": [
                    {"label": "Phase 1", "value": 34},
                    {"label": "Phase 2", "value": 62},
                    {"label": "Phase 3", "value": 91},
                ],
                "chartAnimation": "spring",
                "showValues": True,
                "showGrid": True,
                "in_seconds": mid,
                "out_seconds": round(duration, 3),
            },
        ]

    if any(k in text_blob for k in ("typography", "quote", "callout", "explainer", "step")):
        mid = round(duration * 0.45, 3)
        return [
            {
                "type": "text_card",
                "text": title,
                "fontSize": 64,
                "in_seconds": 0,
                "out_seconds": mid,
            },
            {
                "type": "callout",
                "title": title,
                "text": visual or title,
                "callout_type": "info",
                "in_seconds": mid,
                "out_seconds": round(duration, 3),
            },
        ]

    if duration >= 3.0:
        mid = round(duration * 0.48, 3)
        return [
            {
                "type": "hero_title",
                "text": title,
                "heroSubtitle": visual or title,
                "in_seconds": 0,
                "out_seconds": mid,
            },
            {
                "type": "callout",
                "title": title,
                "text": visual or title,
                "callout_type": "info",
                "in_seconds": mid,
                "out_seconds": round(duration, 3),
            },
        ]

    return [
        {
            "type": "hero_title",
            "text": title,
            "heroSubtitle": visual,
            "in_seconds": 0,
            "out_seconds": round(duration, 3),
        }
    ]


def _ffprobe_valid(mp4_path: Path) -> bool:
    if not mp4_path.is_file() or mp4_path.stat().st_size < 1024:
        return False
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(mp4_path)],
            text=True,
            timeout=15,
        )
        data = json.loads(out)
        return len(data.get("streams", [])) > 0
    except Exception:
        return False


def render_remotion_scene(
    scene: dict[str, Any],
    output_mp4: Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
) -> dict[str, Any]:
    st = get_remotion_status()
    if not st["available"]:
        return {"ok": False, "status": "UNAVAILABLE", "engine": "remotion", "reason": st["reason"]}

    rc_dir = OPENMONTAGE_DIR / "remotion-composer"
    duration = max(2.0, float(scene.get("duration_sec", 4.0) or 4.0))
    title = str(scene.get("on_screen_text") or scene.get("title") or "Scene")[:90]
    narration = str(scene.get("narration_segment") or scene.get("narration") or "")
    words = narration.split()
    captions = list(scene.get("captions") or [])
    if not captions and len(words) > 1:
        step = duration / max(1, len(words))
        for i, word in enumerate(words[:32]):
            captions.append({
                "word": word,
                "startMs": int(round(i * step * 1000)),
                "endMs": int(round(min(duration, (i + 1) * step) * 1000)),
            })

    cuts = _build_cuts_from_scene(scene, duration)
    for idx, c in enumerate(cuts):
        c.setdefault("id", f"cut_{idx + 1}")
    overlays = list(scene.get("overlays") or [])
    if not overlays and scene.get("section_label"):
        overlays.append({
            "type": "section_title",
            "text": str(scene["section_label"]),
            "position": "top-left",
            "in_seconds": 0,
            "out_seconds": round(duration, 3),
        })

    theme = str(scene.get("remotion_theme") or "")
    if not theme:
        theme = "clean-professional" if "clean" in str(scene.get("lighting") or "").lower() else "flat-motion-graphics"

    composition = str(scene.get("remotion_composition") or "Explainer")
    props = {
        "cuts": cuts,
        "overlays": overlays,
        "captions": captions,
        "audio": {},
        "theme": theme,
    }
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(props, tf)
        props_path = tf.name

    try:
        native_fps = 30
        total_frames = max(1, int(round(duration * native_fps)))
        render_target = output_mp4 if (width == 1920 and height == 1080 and fps == native_fps) else output_mp4.with_suffix(".native.mp4")
        cmd = [
            "npx", "remotion", "render", "src/index.tsx", composition,
            str(render_target),
            f"--props={props_path}",
            f"--frames=0-{total_frames - 1}",
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(rc_dir),
            capture_output=True,
            text=True,
            timeout=240,
        )
        if proc.returncode != 0 or not _ffprobe_valid(render_target):
            return {"ok": False, "status": "FAILED", "engine": "remotion", "reason": (proc.stderr or proc.stdout)[-400:]}
        if render_target != output_mp4:
            ff = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(render_target),
                    "-vf", f"scale={width}:{height}:flags=lanczos,fps={fps}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(output_mp4),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            render_target.unlink(missing_ok=True)
            if ff.returncode != 0 or not _ffprobe_valid(output_mp4):
                return {"ok": False, "status": "FAILED", "engine": "remotion", "reason": ff.stderr[-300:]}
        return {
            "ok": True,
            "status": "READY",
            "engine": "remotion",
            "output": str(output_mp4),
            "composition": composition,
            "cuts_count": len(cuts),
            "title": title,
        }
    except Exception as exc:
        return {"ok": False, "status": "FAILED", "engine": "remotion", "reason": str(exc)}
    finally:
        Path(props_path).unlink(missing_ok=True)
