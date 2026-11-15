"""Phase 3 Verification: Real Headless Blender Character, Environment, Animation & MCP Tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from backend.db import get_conn, init_db
from backend.integrations.blender_adapter import find_blender_binary, get_blender_status, render_blender_scene
from backend.mcp_server import TOOLS, handle_tool_call
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project
from backend.services.character_asset_service import (
    get_default_humanoid_asset,
    register_character_asset,
    validate_and_cleanup_mesh,
    verify_character_continuity,
)


def test_blender_binary_and_default_rigged_humanoid():
    st = get_blender_status()
    assert st["available"] is True, st
    assert st["status"] == "READY"
    assert find_blender_binary() is not None

    glb = get_default_humanoid_asset()
    assert glb is not None and glb.is_file()


def test_mesh_validation_and_character_asset_continuity(tmp_path: Path):
    init_db()
    glb = get_default_humanoid_asset()
    assert glb is not None

    stats = validate_and_cleanup_mesh(glb, cleanup=False)
    assert stats["ok"] is True, stats
    assert stats["armature_count"] >= 1
    assert stats["vertex_count"] > 100
    assert any("walk" in a.lower() for a in stats["animations"])

    # Rule 4: never create a character asset record without a real corresponding asset.
    with pytest.raises(ValueError):
        register_character_asset("proj_missing", "Ghost", tmp_path / "missing.glb")

    proj = create_project(ProjectCreateRequest(prompt="3D animated test", target_duration_sec=10))
    pid = proj["project"]["id"]
    try:
        rec = register_character_asset(
            project_id=pid,
            name="Scout",
            mesh_path=glb,
            wardrobe_spec={"jacket": "olive"},
            voice_id="character_1",
            license_name="MIT",
        )
        assert rec["has_armature"] == 1
        assert Path(rec["mesh_path"]).is_file()
        cont = verify_character_continuity(pid, rec["id"])
        assert cont["ok"] is True
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM projects WHERE id=?", (pid,))


def test_blender_vertical_slice_and_mcp_render(tmp_path: Path):
    glb = get_default_humanoid_asset()
    assert glb is not None

    out_mp4 = tmp_path / "blender_walk.mp4"
    res = render_blender_scene(
        scene={
            "title": "Character Walk in Studio Room",
            "character_mesh_path": str(glb),
            "animation_name": "walk",
            "environment_type": "room",
            "duration_sec": 2.0,
        },
        output_mp4=out_mp4,
        work_dir=tmp_path / "work",
        width=640,
        height=360,
        fps=12,
    )
    assert res["ok"] is True, res
    assert out_mp4.is_file() and out_mp4.stat().st_size > 2048

    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out_mp4)],
            text=True,
        )
    )
    v_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
    assert len(v_streams) == 1
    assert int(v_streams[0]["width"]) == 640
    assert int(v_streams[0]["height"]) == 360

    # Verify MCP exposes real Blender tools and executes one
    tool_names = {t["name"] for t in TOOLS}
    assert {"blender_validate_mesh", "blender_auto_rig_mesh", "blender_register_character_asset", "blender_apply_animation", "blender_render_character_shot"} <= tool_names

    mcp_out = tmp_path / "mcp_walk.mp4"
    mcp_res = handle_tool_call(
        "blender_render_character_shot",
        {
            "output_mp4": str(mcp_out),
            "work_dir": str(tmp_path / "mcp_work"),
            "environment_type": "outdoor",
            "animation_name": "walk",
            "duration_sec": 2.0,
            "width": 480,
            "height": 270,
            "fps": 12,
        },
    )
    assert mcp_res["ok"] is True, mcp_res
    assert mcp_out.is_file() and mcp_out.stat().st_size > 2048
