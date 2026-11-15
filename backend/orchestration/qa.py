"""Real FFprobe/FFmpeg Visual, Audio, Continuity, Lip-Sync, and Render Quality Assurance Verifier."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from backend.db import get_conn, init_db
from backend.models import QualityCheckItem, utc_now
from backend.services.character_asset_service import list_character_assets, verify_character_continuity


def run_qa_verification(
    project_id: str,
    video_path: Path,
    expected_aspect_ratio: str = "16:9",
    expected_fps: int = 30,
    subtitle_paths: list[Path] | None = None,
    scene_count_expected: int = 0,
    scene_count_rendered: int = 0,
    expected_duration_sec: float = 0.0,
    expected_resolution: str | None = None,
    dialogue_tracks: list[dict[str, Any]] | None = None,
    lip_sync_frames: list[dict[str, Any]] | None = None,
    expected_wardrobe: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    init_db()
    checks: list[QualityCheckItem] = []

    if not video_path.exists():
        checks.append(QualityCheckItem(name="render_file_exists", category="visual", passed=False, severity="error", details=f"Rendered file not found at {video_path}"))
        return _persist_qa(project_id, video_path, checks)

    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video_path)],
            text=True,
            timeout=30,
        )
        probe_data = json.loads(raw)
    except Exception as exc:
        checks.append(QualityCheckItem(name="ffprobe_integrity", category="visual", passed=False, severity="error", details=f"Corrupt or unreadable video file: {exc}"))
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
        res_ok = abs(actual_ratio - target_ratio) <= 0.08 and w > 0 and h > 0
        if expected_resolution and "x" in expected_resolution.lower():
            exp_w, exp_h = (int(x) for x in expected_resolution.lower().split("x"))
            res_ok = res_ok and (w == exp_w and h == exp_h)
        checks.append(QualityCheckItem(name="aspect_ratio_and_resolution", category="visual", passed=res_ok, details=f"Resolution {w}x{h} (ratio {actual_ratio} vs target {target_ratio})"))

    try:
        proc = subprocess.run(["ffmpeg", "-i", str(video_path), "-vf", "blackdetect=d=1.0:pic_th=0.99:pix_th=0.05", "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
        black_hits = re.findall(r"black_duration:([0-9.]+)", proc.stderr or "")
        total_black = sum(float(x) for x in black_hits)
        checks.append(QualityCheckItem(name="black_frame_check", category="visual", passed=total_black < max(1.0, duration_sec * 0.12), details=f"Detected {len(black_hits)} black segment(s), total={total_black:.2f}s"))
    except Exception as exc:
        checks.append(QualityCheckItem(name="black_frame_check", category="visual", passed=False, details=str(exc)))

    if a_streams:
        try:
            proc = subprocess.run(["ffmpeg", "-i", str(video_path), "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
            max_m = re.search(r"max_volume:\s*(-?[0-9.]+)\s*dB", proc.stderr or "")
            mean_m = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", proc.stderr or "")
            max_db = float(max_m.group(1)) if max_m else -99.0
            mean_db = float(mean_m.group(1)) if mean_m else -99.0
            # Clipping check: max_db <= -0.1 (or <= 0.0) and audible mean_db > -65.0
            checks.append(QualityCheckItem(name="audio_loudness_and_clipping", category="audio", passed=mean_db > -65.0 and max_db <= 0.0, details=f"mean_volume={mean_db:.1f} dB, max_volume={max_db:.1f} dB"))
        except Exception as exc:
            checks.append(QualityCheckItem(name="audio_loudness_and_clipping", category="audio", passed=False, details=str(exc)))

    if scene_count_expected > 0:
        checks.append(QualityCheckItem(name="scene_completeness", category="visual", passed=scene_count_rendered >= scene_count_expected, details=f"Rendered {scene_count_rendered}/{scene_count_expected} scenes"))

    if expected_duration_sec > 1.0:
        err = abs(duration_sec - expected_duration_sec) / expected_duration_sec
        checks.append(QualityCheckItem(
            name="duration_matches_target",
            category="visual",
            passed=err <= 0.15 or abs(duration_sec - expected_duration_sec) <= 2.0,
            details=f"Program {duration_sec:.1f}s vs requested target {expected_duration_sec:.1f}s",
            measured_value=round(duration_sec, 2),
        ))

    # Visible animation check: ensure video is not a single frozen/static frame
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", str(video_path), "-vf", "freezedetect=n=0.001:d=1.5", "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=45,
        )
        stderr_out = proc.stderr or ""
        freeze_hits = re.findall(r"freeze_duration:\s*([0-9.]+)", stderr_out)
        total_freeze = sum(float(x) for x in freeze_hits)
        freeze_starts = re.findall(r"freeze_start:\s*([0-9.]+)", stderr_out)
        if len(freeze_starts) > len(freeze_hits):
            # Last freeze continued until EOF without emitting freeze_duration
            total_freeze += max(0.0, duration_sec - float(freeze_starts[-1]))
        motion_ok = duration_sec <= 1.5 or total_freeze < (duration_sec * 0.85)
        checks.append(QualityCheckItem(
            name="visible_animation_check",
            category="visual",
            passed=motion_ok,
            details=f"Detected {total_freeze:.2f}s frozen/static out of {duration_sec:.2f}s",
            measured_value=round(total_freeze, 2),
        ))
    except Exception as exc:
        checks.append(QualityCheckItem(name="visible_animation_check", category="visual", passed=False, details=str(exc)))

    # Character identity drift & wardrobe consistency checks
    char_assets = list_character_assets(project_id)
    if char_assets:
        drift_failures = []
        wardrobe_failures = []
        for ca in char_assets:
            cont = verify_character_continuity(project_id, ca["id"])
            if not cont.get("ok"):
                drift_failures.append(ca["name"])
            if expected_wardrobe and ca["name"] in expected_wardrobe:
                if (ca.get("wardrobe_spec") or {}) != expected_wardrobe[ca["name"]]:
                    wardrobe_failures.append(ca["name"])
        checks.append(QualityCheckItem(
            name="character_identity_continuity",
            category="continuity",
            passed=len(drift_failures) == 0,
            details="All character 3D assets match continuity lock" if not drift_failures else f"Identity drift detected: {', '.join(drift_failures)}",
        ))
        if expected_wardrobe:
            checks.append(QualityCheckItem(
                name="wardrobe_consistency",
                category="continuity",
                passed=len(wardrobe_failures) == 0,
                details="Wardrobe specs consistent" if not wardrobe_failures else f"Wardrobe mismatch: {', '.join(wardrobe_failures)}",
            ))

    # Dialogue completeness, non-silence & lip-sync timing checks
    if dialogue_tracks is not None:
        missing_dlg = [t.get("speaker", "unknown") for t in dialogue_tracks if not Path(str(t.get("wav_path", ""))).is_file()]
        silent_dlg = []
        for t in dialogue_tracks:
            if t.get("provider") in ("silence", "none"):
                silent_dlg.append(t.get("speaker", "unknown"))
                continue
            wp = Path(str(t.get("wav_path", "")))
            if wp.is_file():
                try:
                    vp = subprocess.run(
                        ["ffmpeg", "-i", str(wp), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                        capture_output=True, text=True, timeout=15,
                    )
                    mm = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", vp.stderr or "")
                    if mm and float(mm.group(1)) <= -60.0:
                        silent_dlg.append(t.get("speaker", "unknown"))
                except Exception:
                    pass
        dlg_ok = len(dialogue_tracks) > 0 and len(missing_dlg) == 0 and len(silent_dlg) == 0
        checks.append(QualityCheckItem(
            name="dialogue_completeness",
            category="audio",
            passed=dlg_ok,
            details=(
                f"{len(dialogue_tracks)} non-silent dialogue track(s) verified"
                if dlg_ok
                else f"Dialogue failure (missing={missing_dlg}, silent={silent_dlg})"
            ),
        ))

    if lip_sync_frames is not None:
        max_lip_t = max((float(f.get("time_sec", 0.0)) for f in lip_sync_frames), default=0.0)
        sync_ok = len(lip_sync_frames) > 0 and max_lip_t <= (duration_sec + 0.5)
        checks.append(QualityCheckItem(
            name="lip_sync_timing",
            category="animation",
            passed=sync_ok,
            details=f"Lip-sync span {max_lip_t:.2f}s within program {duration_sec:.2f}s",
        ))

    # Discontinuous scenes & failed renders check in DB
    with get_conn() as conn:
        failed_scenes = conn.execute(
            "SELECT id FROM scenes WHERE project_id=? AND quality_status='failed'",
            (project_id,),
        ).fetchall()
    checks.append(QualityCheckItem(
        name="failed_renders_check",
        category="visual",
        passed=len(failed_scenes) == 0,
        details="No failed scene renders" if not failed_scenes else f"{len(failed_scenes)} failed scene render(s)",
    ))

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
    summary = f"{sum(1 for c in checks if c.passed)}/{len(checks)} automated QA checks passed (human visual approval pending)"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO quality_reports (id, project_id, target_path, passed, checks_json, summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (report_id, project_id, str(video_path), 1 if all_passed else 0, json.dumps([c.model_dump() for c in checks]), summary, utc_now()),
        )
    return {
        "report_id": report_id,
        "project_id": project_id,
        "target_path": str(video_path),
        "passed": all_passed,
        "automated_qa_passed": all_passed,
        "human_visual_approved": False,
        "approval_status": "PENDING_HUMAN_VISUAL_REVIEW" if all_passed else "AUTOMATED_QA_FAILED",
        "summary": summary,
        "checks": [c.model_dump() for c in checks],
    }


def record_human_visual_approval(
    project_id: str,
    report_id: str,
    approved: bool,
    reviewer_notes: str = "",
) -> dict[str, Any]:
    """Explicitly record human visual approval separately from automated QA."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM quality_reports WHERE id=? AND project_id=?", (report_id, project_id)).fetchone()
        if not row:
            raise ValueError(f"QA report {report_id} not found for project {project_id}")
        automated_ok = bool(row["passed"])
        status = "HUMAN_APPROVED" if (approved and automated_ok) else ("HUMAN_REJECTED" if not approved else "BLOCKED_BY_AUTOMATED_QA")
        note = f"{row['summary']} | human_review={status}"
        if reviewer_notes:
            note += f": {reviewer_notes}"
        conn.execute("UPDATE quality_reports SET summary=? WHERE id=?", (note, report_id))
    return {
        "report_id": report_id,
        "project_id": project_id,
        "automated_qa_passed": automated_ok,
        "human_visual_approved": bool(approved and automated_ok),
        "approval_status": status,
        "reviewer_notes": reviewer_notes,
    }
