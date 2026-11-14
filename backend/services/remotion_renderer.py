"""Real Remotion CLI Renderer via OpenMontage remotion-composer."""

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
    visual = str(scene.get("picture_prompt") or scene.get("visual_description") or scene.get("generation_prompt") or "")[:180]
    narration = str(scene.get("narration_segment") or scene.get("narration") or "")
    words = narration.split()
    captions = []
    if len(words) > 1:
        step = duration / max(1, len(words))
        for i, word in enumerate(words[:24]):
            captions.append({"text": word, "start": round(i * step, 3), "end": round(min(duration, (i + 1) * step), 3)})
    # Explainer reads cuts/overlays/captions. A title/subtitle bag renders an empty 60s composition.
    props = {
        "cuts": [
            {
                "type": "hero_title",
                "text": title,
                "heroSubtitle": visual,
                "in_seconds": 0,
                "out_seconds": round(duration, 3),
            }
        ],
        "overlays": [],
        "captions": captions,
        "audio": {},
        "theme": "documentary" if "documentary" in str(scene.get("lighting") or "").lower() else "flat-motion-graphics",
    }
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(props, tf)
        props_path = tf.name

    try:
        proc = subprocess.run(
            [
                "npx", "remotion", "render", "src/index.tsx", "Explainer",
                str(output_mp4), f"--props={props_path}",
            ],
            cwd=str(rc_dir),
            capture_output=True,
            text=True,
            timeout=240,
        )
        if proc.returncode != 0 or not output_mp4.is_file():
            return {"ok": False, "status": "UNAVAILABLE", "engine": "remotion", "reason": (proc.stderr or proc.stdout)[-400:]}
        return {"ok": True, "status": "READY", "engine": "remotion", "output": str(output_mp4)}
    except Exception as exc:
        return {"ok": False, "status": "UNAVAILABLE", "engine": "remotion", "reason": str(exc)}
    finally:
        Path(props_path).unlink(missing_ok=True)
