"""Screenplay-to-Shot Multi-Engine Orchestrator & Individual Shot Regeneration."""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from backend.config import PROJECTS_DIR
from backend.db import get_conn, init_db, row_to_dict, rows_to_dicts
from backend.integrations.blender_adapter import get_blender_status, render_blender_scene
from backend.models import utc_now
from backend.providers.video.registry import video_provider_readiness
from backend.services.remotion_renderer import get_remotion_status, render_remotion_scene
from backend.services.shot_generation_service import generate_shot_for_scene


def select_shot_engine(shot: dict[str, Any]) -> dict[str, Any]:
    """Determine the optimal production engine(s) for a single screenplay shot."""
    explicit = str(shot.get("engine") or "").strip().lower()
    if explicit in ("ai_video", "cloud_video", "blender", "remotion", "licensed_footage", "hybrid"):
        engines = list(shot.get("engines") or [])
        if explicit == "hybrid" and not engines:
            engines = ["blender", "remotion"]
        return {"primary_engine": explicit, "engines": engines or [explicit], "reason": "explicit_screenplay_engine"}

    text = " ".join([
        str(shot.get("description") or ""),
        str(shot.get("visual_description") or ""),
        str(shot.get("title") or ""),
        str(shot.get("shot_type") or ""),
    ]).lower()

    has_blender = get_blender_status().get("available", False)
    has_remotion = get_remotion_status().get("available", False)
    has_cloud = any(p.get("state") == "configured" for p in video_provider_readiness())

    wants_3d = any(k in text for k in ("3d", "blender", "character", "walk", "humanoid", "rig", "room", "corridor"))
    wants_gfx = any(k in text for k in ("chart", "graph", "kpi", "typography", "title card", "explainer", "caption", "remotion", "metric"))
    wants_archival = bool(shot.get("source_media")) or any(k in text for k in ("archival", "historical", "newsreel", "stock footage", "licensed"))
    wants_ai = any(k in text for k in ("cinematic", "aerial", "photoreal", "dreamlike", "ai video", "veo", "kling", "runway"))

    if wants_3d and wants_gfx and has_blender and has_remotion:
        return {"primary_engine": "hybrid", "engines": ["blender", "remotion"], "reason": "3d_character_plus_motion_graphics"}
    if wants_3d and has_blender:
        return {"primary_engine": "blender", "engines": ["blender"], "reason": "3d_character_or_environment"}
    if wants_gfx and has_remotion:
        return {"primary_engine": "remotion", "engines": ["remotion"], "reason": "motion_graphics_or_charts"}
    if wants_archival:
        return {"primary_engine": "licensed_footage", "engines": ["licensed_footage"], "reason": "licensed_or_archival_source"}
    if wants_ai and has_cloud:
        return {"primary_engine": "ai_video", "engines": ["ai_video"], "reason": "configured_cloud_video_provider"}
    if has_blender and "character" in text:
        return {"primary_engine": "blender", "engines": ["blender"], "reason": "character_continuity_3d"}
    if has_remotion:
        return {"primary_engine": "remotion", "engines": ["remotion"], "reason": "local_motion_graphics_fallback"}
    return {"primary_engine": "licensed_footage", "engines": ["licensed_footage"], "reason": "archival_ffmpeg_compositor"}


def plan_screenplay_shots(project_id: str, screenplay: dict[str, Any]) -> list[dict[str, Any]]:
    """Persist screenplay shots and their engine assignments for a project."""
    init_db()
    shots_in = screenplay.get("shots") or []
    planned: list[dict[str, Any]] = []

    with get_conn() as conn:
        proj = conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
        if not proj:
            raise ValueError(f"Project not found: {project_id}")

        chap_id = f"chap_{uuid.uuid4().hex[:8]}"
        seq_id = f"seq_{uuid.uuid4().hex[:8]}"
        scene_id = f"scene_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO chapters (id, project_id, order_index, title, summary) VALUES (?, ?, 0, ?, ?)",
            (chap_id, project_id, screenplay.get("title", "Screenplay"), screenplay.get("logline", "")),
        )
        conn.execute(
            "INSERT INTO sequences (id, project_id, chapter_id, order_index, title) VALUES (?, ?, ?, 0, ?)",
            (seq_id, project_id, chap_id, "Main Sequence"),
        )
        conn.execute(
            "INSERT INTO scenes (id, project_id, chapter_id, sequence_id, order_index, title, visual_description) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (scene_id, project_id, chap_id, seq_id, screenplay.get("title", "Main Scene"), screenplay.get("logline", "")),
        )

        for idx, sh in enumerate(shots_in):
            shot_id = str(sh.get("id") or f"shot_{uuid.uuid4().hex[:10]}")
            routing = select_shot_engine(sh)
            comp_payload = json.dumps({
                "primary_engine": routing["primary_engine"],
                "engines": routing["engines"],
                "reason": routing["reason"],
                "spec": sh,
            })
            conn.execute(
                """INSERT INTO shots
                   (id, project_id, scene_id, order_index, shot_type, camera_angle, camera_movement, lighting, composition, description, duration_sec)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    shot_id,
                    project_id,
                    scene_id,
                    idx,
                    str(sh.get("shot_type") or "medium"),
                    str(sh.get("camera_angle") or "eye_level"),
                    str(sh.get("camera_movement") or "static"),
                    str(sh.get("lighting") or "natural"),
                    comp_payload,
                    str(sh.get("description") or sh.get("visual_description") or sh.get("title") or f"Shot {idx + 1}"),
                    float(sh.get("duration_sec") or 2.0),
                ),
            )
            planned.append({
                "shot_id": shot_id,
                "scene_id": scene_id,
                "order_index": idx,
                **routing,
                "duration_sec": float(sh.get("duration_sec") or 2.0),
            })
    return planned


def _composite_hybrid_clips(base_mp4: Path, overlay_mp4: Path, output_mp4: Path) -> bool:
    """Blend base shot and Remotion graphics clip side-by-side/PIP or crossfade."""
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(base_mp4),
            "-i", str(overlay_mp4),
            "-filter_complex",
            "[1:v]scale=iw*0.38:-1,format=rgba,colorchannelmixer=aa=0.92[ov];[0:v][ov]overlay=W-w-24:24:shortest=1[v]",
            "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(output_mp4),
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    return proc.returncode == 0 and output_mp4.is_file()


def render_single_shot(
    project_id: str,
    shot_id: str,
    width: int = 640,
    height: int = 360,
    fps: int = 24,
) -> dict[str, Any]:
    """Render one shot using its assigned engine(s) and persist shot-level asset provenance."""
    init_db()
    with get_conn() as conn:
        srow = conn.execute("SELECT * FROM shots WHERE id=? AND project_id=?", (shot_id, project_id)).fetchone()
        prow = conn.execute("SELECT workspace_dir, category FROM projects WHERE id=?", (project_id,)).fetchone()
    if not srow or not prow:
        raise ValueError(f"Shot {shot_id} or project {project_id} not found")

    shot = row_to_dict(srow) or {}
    meta = json.loads(shot.get("composition") or "{}")
    spec = meta.get("spec") or {}
    engines = meta.get("engines") or [meta.get("primary_engine") or "licensed_footage"]
    primary = meta.get("primary_engine") or engines[0]

    ws = Path(prow["workspace_dir"]) if prow["workspace_dir"] else (PROJECTS_DIR / project_id)
    shots_dir = ws / "renders" / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = shots_dir / f"{shot_id}.mp4"
    scene_payload = {
        "id": shot_id,
        "title": spec.get("title") or shot.get("description", "Shot")[:60],
        "visual_description": shot.get("description", ""),
        "duration_sec": float(shot.get("duration_sec") or 2.0),
        **spec,
    }

    render_res: dict[str, Any]
    if primary == "hybrid" and len(engines) >= 2:
        base_mp4 = shots_dir / f"{shot_id}_base.mp4"
        ov_mp4 = shots_dir / f"{shot_id}_overlay.mp4"
        base_res = render_blender_scene(scene_payload, base_mp4, shots_dir / f"work_{shot_id}", width=width, height=height, fps=fps) if engines[0] == "blender" else generate_shot_for_scene(scene_payload, base_mp4, resolution=f"{width}x{height}", fps=fps, render_engine=engines[0])
        ov_res = render_remotion_scene(scene_payload, ov_mp4, width=width, height=height, fps=fps)
        if base_res.get("ok") and ov_res.get("ok") and _composite_hybrid_clips(base_mp4, ov_mp4, out_mp4):
            render_res = {"ok": True, "engine": "hybrid(blender+remotion)", "output": str(out_mp4)}
        else:
            return {"ok": False, "shot_id": shot_id, "reason": f"Hybrid render failed: base={base_res.get('reason')} ov={ov_res.get('reason')}"}
    elif primary == "blender":
        render_res = render_blender_scene(scene_payload, out_mp4, shots_dir / f"work_{shot_id}", width=width, height=height, fps=fps)
    elif primary == "remotion":
        render_res = render_remotion_scene(scene_payload, out_mp4, width=width, height=height, fps=fps)
    elif primary == "ai_video":
        render_res = generate_shot_for_scene(scene_payload, out_mp4, category=prow["category"], resolution=f"{width}x{height}", fps=fps, render_engine="cloud_video")
    else:
        render_res = generate_shot_for_scene(
            scene_payload,
            out_mp4,
            category=prow["category"],
            resolution=f"{width}x{height}",
            fps=fps,
            render_engine="ffmpeg",
            source_media=spec.get("source_media"),
        )

    if not render_res.get("ok") or not out_mp4.is_file():
        return {"ok": False, "shot_id": shot_id, "engine": primary, "reason": render_res.get("reason")}

    asset_id = f"asset_{uuid.uuid4().hex[:10]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO assets (id, project_id, scene_id, asset_type, provider, file_path, duration_sec, license, metadata_json, created_at)
               VALUES (?, ?, ?, 'shot_video', ?, ?, ?, 'generated_local', ?, ?)""",
            (
                asset_id,
                project_id,
                shot["scene_id"],
                str(render_res.get("engine") or primary),
                str(out_mp4),
                float(shot.get("duration_sec") or 2.0),
                json.dumps({"shot_id": shot_id, "engines": engines, "render": render_res}),
                utc_now(),
            ),
        )
        conn.execute("UPDATE shots SET asset_id=? WHERE id=?", (asset_id, shot_id))

    return {"ok": True, "shot_id": shot_id, "asset_id": asset_id, "engine": primary, "output": str(out_mp4)}


def regenerate_shot(
    project_id: str,
    shot_id: str,
    engine_override: str | None = None,
    description_override: str | None = None,
    width: int = 640,
    height: int = 360,
    fps: int = 24,
) -> dict[str, Any]:
    """Regenerate a single shot without modifying or invalidating other shots."""
    init_db()
    with get_conn() as conn:
        srow = conn.execute("SELECT * FROM shots WHERE id=? AND project_id=?", (shot_id, project_id)).fetchone()
        if not srow:
            raise ValueError(f"Shot {shot_id} not found in project {project_id}")
        meta = json.loads(srow["composition"] or "{}")
        if engine_override:
            meta["primary_engine"] = engine_override
            meta["engines"] = [engine_override] if engine_override != "hybrid" else ["blender", "remotion"]
        desc = description_override if description_override is not None else srow["description"]
        conn.execute(
            "UPDATE shots SET description=?, composition=? WHERE id=?",
            (desc, json.dumps(meta), shot_id),
        )
    return render_single_shot(project_id, shot_id, width=width, height=height, fps=fps)
