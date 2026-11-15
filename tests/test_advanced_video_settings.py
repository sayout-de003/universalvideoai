"""Verification for Advanced Video Settings: Blender 3D options, multi-skill orchestration, duration, pacing."""

from __future__ import annotations

import json
from pathlib import Path

from backend.db import get_conn, init_db
from backend.integrations.blender_adapter import get_blender_status, render_blender_scene
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project


def test_create_project_with_advanced_settings_and_skills():
    init_db()
    req = ProjectCreateRequest(
        title="Cyberpunk Odyssey",
        prompt="A high-tech cyberpunk explorer navigates a neon corridor with neural dialogue.",
        target_duration_sec=45.0,
        aspect_ratio="16:9",
        resolution="1920x1080",
        fps=30,
        skills=["blender", "remotion", "openmontage"],
        blender_settings={
            "engine": "EEVEE",
            "environment": "cyberpunk",
            "lighting": "neon",
            "camera_motion": "orbit",
            "animation": "walk",
            "samples": 32,
            "lip_sync": True,
        },
        video_type="fiction_short_films",
        pacing="fast",
        color_grade="teal_orange",
        quality_preset="master",
    )

    detail = create_project(req)
    proj = detail["project"]
    pid = proj["id"]

    try:
        assert proj["target_duration_sec"] == 45.0
        assert proj["render_engine"] == "blender"

        with get_conn() as conn:
            row = conn.execute("SELECT metadata_json FROM projects WHERE id=?", (pid,)).fetchone()
            assert row is not None
            meta = json.loads(row[0])
            assert "skills" in meta
            assert "blender" in meta["skills"]
            assert "remotion" in meta["skills"]
            assert meta["blender_settings"]["environment"] == "cyberpunk"
            assert meta["blender_settings"]["lighting"] == "neon"
            assert meta["blender_settings"]["camera_motion"] == "orbit"
            assert meta["pacing"] == "fast"
            assert meta["color_grade"] == "teal_orange"
            assert meta["quality_preset"] == "master"

            ai_dec = meta.get("ai_decisions", {})
            assert "skills_orchestration" in ai_dec
            assert "blender_3d_pipeline" in ai_dec
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM projects WHERE id=?", (pid,))


def test_blender_adapter_with_advanced_options(tmp_path: Path):
    st = get_blender_status()
    if not st["available"]:
        return

    out_mp4 = tmp_path / "blender_advanced.mp4"
    res = render_blender_scene(
        scene={
            "title": "Cyberpunk Neon Walk",
            "duration_sec": 2.0,
            "blender_settings": {
                "engine": "EEVEE",
                "environment": "cyberpunk",
                "lighting": "neon",
                "camera_motion": "orbit",
                "animation": "walk",
                "samples": 16,
            },
        },
        output_mp4=out_mp4,
        work_dir=tmp_path / "work_adv",
        width=640,
        height=360,
        fps=12,
    )
    assert res["ok"] is True, res
    assert res["environment_type"] == "cyberpunk"
    assert res["lighting_preset"] == "neon"
    assert res["camera_motion"] == "orbit"
    assert out_mp4.is_file() and out_mp4.stat().st_size > 2048
