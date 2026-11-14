"""Phase 2: Multimodal Reference Intelligence & Asset Intelligence Engine."""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from backend.db import get_conn, rows_to_dicts
from backend.integrations.openwhispr_adapter import openwhispr_adapter
from backend.models import utc_now

ALLOWED_ROLES = {
    "visual_inspiration",
    "character_appearance",
    "location_reference",
    "camera_movement",
    "editing_style",
    "color_palette",
    "brand_identity",
    "existing_footage",
    "product_accuracy",
    "audio_music",
}


def _analyze_image(path: Path) -> dict[str, Any]:
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        w, h = rgb.size
        small = rgb.resize((64, 64))
        stat = ImageStat.Stat(small)
        avg_rgb = [int(round(c)) for c in stat.mean[:3]]
        luminance = round((0.299 * avg_rgb[0] + 0.587 * avg_rgb[1] + 0.114 * avg_rgb[2]) / 255.0, 3)
        # Extract 4 dominant quantized palette colors
        quant = small.quantize(colors=4).convert("RGB")
        colors = sorted(quant.getcolors(maxcolors=64) or [], reverse=True)
        palette_hex = [f"#{c[1][0]:02x}{c[1][1]:02x}{c[1][2]:02x}" for c in colors[:4]]
        return {
            "width": w,
            "height": h,
            "aspect_ratio": f"{w}:{h}",
            "average_rgb": avg_rgb,
            "luminance": luminance,
            "lighting_profile": "high_key_bright" if luminance > 0.6 else ("low_key_moody" if luminance < 0.32 else "balanced_natural"),
            "palette_hex": palette_hex,
            "composition_hint": "landscape_wide" if w > h else ("vertical_portrait" if h > w else "square_centered"),
        }


def _analyze_video(path: Path, work_dir: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {"duration_sec": 0.0, "width": 0, "height": 0, "fps": 30.0, "has_audio": False}
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            text=True, timeout=15,
        )
        info = json.loads(out)
        meta["duration_sec"] = round(float(info.get("format", {}).get("duration", 0.0)), 2)
        for st in info.get("streams", []):
            if st.get("codec_type") == "video":
                meta["width"] = int(st.get("width", 0))
                meta["height"] = int(st.get("height", 0))
                r_fps = st.get("r_frame_rate", "30/1")
                if "/" in r_fps:
                    num, den = r_fps.split("/", 1)
                    meta["fps"] = round(float(num) / max(1.0, float(den)), 2)
            elif st.get("codec_type") == "audio":
                meta["has_audio"] = True
    except Exception:
        pass

    # Sample up to 3 representative frames for color & lighting analysis
    frames_dir = work_dir / f".ref_frames_{path.stem}"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_analyses: list[dict[str, Any]] = []
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-vf", "fps=0.5", "-vframes", "3", str(frames_dir / "rep_%02d.png")],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
        )
        for fp in sorted(frames_dir.glob("rep_*.png")):
            frame_analyses.append(_analyze_image(fp))
    except Exception:
        pass
    finally:
        for fp in frames_dir.glob("*"):
            fp.unlink(missing_ok=True)
        frames_dir.rmdir() if frames_dir.exists() else None

    dur = meta["duration_sec"]
    rhythm = "fast_cut_social" if dur > 0 and dur <= 20 else ("medium_narrative" if dur <= 120 else "deliberate_longform")
    return {
        **meta,
        "representative_frames": frame_analyses,
        "editing_rhythm": rhythm,
        "palette_hex": frame_analyses[0]["palette_hex"] if frame_analyses else [],
        "lighting_profile": frame_analyses[0]["lighting_profile"] if frame_analyses else "unknown",
    }


def _analyze_audio(path: Path) -> dict[str, Any]:
    dur = 0.0
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            text=True, timeout=10,
        ).strip()
        dur = round(float(out), 2)
    except Exception:
        pass
    transcript = openwhispr_adapter.transcribe_file(path)
    return {
        "duration_sec": dur,
        "transcript": transcript.get("text", "") if transcript.get("success") else "",
        "transcription_provider": transcript.get("provider", "none"),
    }


def register_and_analyze_reference(
    project_id: str,
    workspace_dir: Path,
    file_path: Path,
    intended_role: str = "visual_inspiration",
    permissions: str = "user_owned",
) -> dict[str, Any]:
    role = intended_role if intended_role in ALLOWED_ROLES else "visual_inspiration"
    ext = file_path.suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        asset_type = "image"
        analysis = _analyze_image(file_path)
    elif ext in (".mp4", ".mov", ".mkv", ".webm"):
        asset_type = "video"
        analysis = _analyze_video(file_path, workspace_dir / "references")
    elif ext in (".wav", ".mp3", ".m4a", ".aac", ".ogg"):
        asset_type = "audio"
        analysis = _analyze_audio(file_path)
    else:
        asset_type = "document"
        analysis = {"size_bytes": file_path.stat().st_size if file_path.exists() else 0}

    ref_id = f"ref_{uuid.uuid4().hex[:8]}"
    now = utc_now()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO reference_assets (id, project_id, filename, file_path, asset_type, intended_role, permissions, analysis_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ref_id, project_id, file_path.name, str(file_path), asset_type, role, permissions, json.dumps(analysis), now),
        )

    pkg_summary = build_reference_package(project_id, workspace_dir)
    return {"ok": True, "reference_id": ref_id, "asset_type": asset_type, "intended_role": role, "analysis": analysis, "package": pkg_summary}


def build_reference_package(project_id: str, workspace_dir: Path) -> dict[str, Any]:
    """Generate reference_analysis.json, reference_style_guide.md, reference_asset_index.json, reference_timeline.json, asset_registry.json."""
    pkg_dir = workspace_dir / "package"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        refs = rows_to_dicts(conn.execute("SELECT * FROM reference_assets WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall())

    palettes: list[str] = []
    lighting_profiles: list[str] = []
    for r in refs:
        a = r.get("analysis") or {}
        palettes.extend(a.get("palette_hex") or [])
        if a.get("lighting_profile"):
            lighting_profiles.append(a["lighting_profile"])

    style_guide_lines = [
        f"# Reference Style Guide ({project_id})",
        "",
        f"**Analyzed Assets:** {len(refs)}",
        f"**Dominant Palette:** {', '.join(dict.fromkeys(palettes)) or 'Project default palette'}",
        f"**Observed Lighting:** {', '.join(dict.fromkeys(lighting_profiles)) or 'Natural cinematic key'}",
        "",
        "## Asset Role Mapping (Copyright-Safe Original Direction)",
    ]
    for r in refs:
        style_guide_lines.append(f"- `{r['filename']}` -> Role: **{r['intended_role']}** ({r['asset_type']}, permissions: {r['permissions']})")

    style_guide_md = "\n".join(style_guide_lines) + "\n"
    ref_analysis = {"project_id": project_id, "asset_count": len(refs), "dominant_palette": list(dict.fromkeys(palettes)), "lighting_profiles": list(dict.fromkeys(lighting_profiles)), "assets": refs}
    asset_index = {"project_id": project_id, "assets": [{"id": r["id"], "filename": r["filename"], "type": r["asset_type"], "role": r["intended_role"], "path": r["file_path"]} for r in refs]}
    ref_timeline = {"project_id": project_id, "entries": [{"asset_id": r["id"], "role": r["intended_role"], "duration_sec": (r.get("analysis") or {}).get("duration_sec", 0.0)} for r in refs]}

    (pkg_dir / "reference_analysis.json").write_text(json.dumps(ref_analysis, indent=2), encoding="utf-8")
    (pkg_dir / "reference_style_guide.md").write_text(style_guide_md, encoding="utf-8")
    (pkg_dir / "reference_asset_index.json").write_text(json.dumps(asset_index, indent=2), encoding="utf-8")
    (pkg_dir / "reference_timeline.json").write_text(json.dumps(ref_timeline, indent=2), encoding="utf-8")
    (pkg_dir / "asset_registry.json").write_text(json.dumps(asset_index, indent=2), encoding="utf-8")

    return {"asset_count": len(refs), "dominant_palette": ref_analysis["dominant_palette"], "style_guide_md": style_guide_md}
