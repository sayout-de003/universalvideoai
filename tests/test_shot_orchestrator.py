"""Phase 6 Verification: Screenplay Multi-Engine Orchestration & Individual Shot Regeneration."""

from __future__ import annotations

from pathlib import Path

from backend.db import get_conn, init_db
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project
from backend.orchestration.shot_orchestrator import (
    plan_screenplay_shots,
    regenerate_shot,
    render_single_shot,
    select_shot_engine,
)


def test_screenplay_engine_routing():
    assert select_shot_engine({"description": "3D humanoid character walking down a room corridor"})["primary_engine"] == "blender"
    assert select_shot_engine({"description": "Animated bar chart showing Q4 KPI metrics"})["primary_engine"] == "remotion"
    assert select_shot_engine({"description": "3D character walking next to an animated KPI chart"})["primary_engine"] == "hybrid"
    assert select_shot_engine({"description": "Historical archival newsreel footage"})["primary_engine"] == "licensed_footage"


def test_shot_level_asset_preservation_and_regeneration():
    init_db()
    proj = create_project(ProjectCreateRequest(prompt="Hybrid screenplay test", target_duration_sec=6))
    pid = proj["project"]["id"]
    try:
        planned = plan_screenplay_shots(
            pid,
            {
                "title": "Hybrid Film",
                "shots": [
                    {"title": "KPI Chart", "description": "Animated bar chart showing studio growth", "engine": "remotion", "duration_sec": 2.0},
                    {"title": "Title Card", "description": "Kinetic typography callout for chapter one", "engine": "remotion", "duration_sec": 2.0},
                ],
            },
        )
        assert len(planned) == 2

        r1 = render_single_shot(pid, planned[0]["shot_id"], width=640, height=360, fps=24)
        r2 = render_single_shot(pid, planned[1]["shot_id"], width=640, height=360, fps=24)
        assert r1["ok"] is True and Path(r1["output"]).is_file()
        assert r2["ok"] is True and Path(r2["output"]).is_file()

        with get_conn() as conn:
            shot1_before = conn.execute("SELECT asset_id FROM shots WHERE id=?", (planned[0]["shot_id"],)).fetchone()["asset_id"]
            shot2_before = conn.execute("SELECT asset_id FROM shots WHERE id=?", (planned[1]["shot_id"],)).fetchone()["asset_id"]

        # Regenerate ONLY shot 2 and verify shot 1's asset_id is preserved untouched
        regen = regenerate_shot(pid, planned[1]["shot_id"], description_override="Updated callout typography", width=640, height=360, fps=24)
        assert regen["ok"] is True

        with get_conn() as conn:
            shot1_after = conn.execute("SELECT asset_id FROM shots WHERE id=?", (planned[0]["shot_id"],)).fetchone()["asset_id"]
            shot2_after = conn.execute("SELECT asset_id FROM shots WHERE id=?", (planned[1]["shot_id"],)).fetchone()["asset_id"]

        assert shot1_after == shot1_before
        assert shot2_after != shot2_before
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM projects WHERE id=?", (pid,))
