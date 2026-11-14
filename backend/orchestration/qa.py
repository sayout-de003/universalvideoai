"""Real FFprobe/FFmpeg Visual, Audio, and Subtitle Quality Assurance Verifier."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from backend.db import get_conn
from backend.models import QualityCheckItem, utc_now


def run_qa_verification(
    project_id: str, video_path: Path, expected_aspect_ratio: str = "16:9", expected_fps: int = 30,
    subtitle_paths: list[Path] | None = None, scene_count_expected: int = 0, scene_count_rendered: int = 0,
) -> dict[str, Any]:
    checks: list[QualityCheckItem] = []
    if not video_path.exists():
        checks.append(QualityCheckItem(name="render_file_exists", category="visual", passed=False, severity="error", details=f"Rendered file not found at {video_path}"))
        return _persist_qa(project_id, video_path, checks)

    try:
        raw = subprocess.check_output(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video_path)], text=True, timeout=30)
        probe_data = json.loads(raw)
    except Exception as exc:
        checks.append(QualityCheckItem(name="ffprobe_integrity", category="visual", passed=False, severity="error", details=f"ffprobe failed: {exc}"))
        return _persist_qa(project_id, video_path, checks)

    streams = probe_data.get("streams", [])
    v_streams = [s for s in streams if s.get("codec_type") == "video"]
    a_streams = [s for s in streams if s.get("codec_type") == "audio"]
    duration_sec = float(probe_data.get("format", {}).get("duration", 0.0) or 0.0)

    checks.append(QualityCheckItem(name="video_stream_present", category="visual", passed=len(v_streams) > 0 and duration_sec > 0.5, details=f"Found {len(v_streams)} video stream(s), duration={duration_sec:.2f}s"))
    checks.append(QualityCheckItem(name="audio_stream_present", category="audio", passed=len(a_streams) > 0, details=f"Found {len(a_streams)} audio stream(s)"))

    if v_streams:
        w, h = int(v_streams[0].get("width", 0)), int(v_streams[0].get("height", 0))
        actual_ratio = round(w / max(1, h), 2)
        ew, eh = (int(x) for x in expected_aspect_ratio.split(":"))
        target_ratio = round(ew / eh, 2)
        checks.append(QualityCheckItem(name="aspect_ratio_and_resolution", category="visual", passed=abs(actual_ratio - target_ratio) <= 0.08 and w > 0 and h > 0, details=f"Resolution {w}x{h} (ratio {actual_ratio} vs target {target_ratio})"))

    try:
        proc = subprocess.run(["ffmpeg", "-i", str(video_path), "-vf", "blackdetect=d=1.0:pic_th=0.99:pix_th=0.05", "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
        black_hits = re.findall(r"black_duration:([0-9.]+)", proc.stderr or "")
        total_black = sum(float(x) for x in black_hits)
        checks.append(QualityCheckItem(name="black_frame_check", category="visual", passed=total_black < max(2.0, duration_sec * 0.25), details=f"Detected {len(black_hits)} black segment(s), total={total_black:.2f}s"))
    except Exception as exc:
        checks.append(QualityCheckItem(name="black_frame_check", category="visual", passed=False, details=str(exc)))

    if a_streams:
        try:
            proc = subprocess.run(["ffmpeg", "-i", str(video_path), "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
            max_m = re.search(r"max_volume:\s*(-?[0-9.]+)\s*dB", proc.stderr or "")
            mean_m = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", proc.stderr or "")
            max_db = float(max_m.group(1)) if max_m else -99.0
            mean_db = float(mean_m.group(1)) if mean_m else -99.0
            checks.append(QualityCheckItem(name="audio_loudness_and_clipping", category="audio", passed=mean_db > -65.0 and max_db <= 0.0, details=f"mean_volume={mean_db:.1f} dB, max_volume={max_db:.1f} dB"))
        except Exception as exc:
            checks.append(QualityCheckItem(name="audio_loudness_and_clipping", category="audio", passed=False, details=str(exc)))

    if scene_count_expected > 0:
        checks.append(QualityCheckItem(name="scene_completeness", category="visual", passed=scene_count_rendered >= scene_count_expected, details=f"Rendered {scene_count_rendered}/{scene_count_expected} scenes"))

    if subtitle_paths:
        for sp in subtitle_paths:
            if not sp.exists():
                checks.append(QualityCheckItem(name=f"subtitle_{sp.name}", category="subtitle", passed=False, details="Missing subtitle file"))
            else:
                content = sp.read_text(encoding="utf-8", errors="ignore").strip()
                has_cues = "-->" in content
                checks.append(QualityCheckItem(name=f"subtitle_{sp.name}", category="subtitle", passed=has_cues and len(content) > 10, details=f"Subtitle file {sp.name} valid={has_cues}"))

    return _persist_qa(project_id, video_path, checks)


def _persist_qa(project_id: str, video_path: Path, checks: list[QualityCheckItem]) -> dict[str, Any]:
    all_passed = all(c.passed for c in checks)
    report_id = f"qa_{uuid.uuid4().hex[:10]}"
    summary = f"{sum(1 for c in checks if c.passed)}/{len(checks)} QA checks passed"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO quality_reports (id, project_id, target_path, passed, checks_json, summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (report_id, project_id, str(video_path), 1 if all_passed else 0, json.dumps([c.model_dump() for c in checks]), summary, utc_now()),
        )
    return {"report_id": report_id, "project_id": project_id, "target_path": str(video_path), "passed": all_passed, "summary": summary, "checks": [c.model_dump() for c in checks]}
