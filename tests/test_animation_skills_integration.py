"""Comprehensive tests for the 9 Claude Animation Skills integration."""

from __future__ import annotations

import os
from pathlib import Path
from fastapi.testclient import TestClient

from backend.integrations.animation_skills_adapter import animation_skills_adapter
from backend.main import app
from backend.mcp_server import handle_tool_call, TOOLS
from backend.orchestration.engine_registry import get_engine_catalog, resolve_visual_style_profile
from backend.services.format_catalog import FORMAT_CATALOG, resolve_format


def test_animation_skills_discovery() -> None:
    """Verify all 9 skills are discovered and reported as installed."""
    skills = animation_skills_adapter.list_skills()
    assert len(skills) == 9
    skill_ids = {s["id"] for s in skills}
    expected_ids = {
        "handdraw-skill",
        "claude-animation-base",
        "claude-drawing-skill",
        "anidoodle",
        "motion-skill",
        "motion-design",
        "manim-skill",
        "javascript-animation",
        "huashu-art-motion",
    }
    assert expected_ids.issubset(skill_ids)
    for s in skills:
        assert s["installed"] is True
        assert Path(s["path"]).exists()


def test_format_catalog_animation_entries() -> None:
    """Verify format catalog includes the specialized animation formats."""
    expected_formats = [
        "handdrawn_whiteboard",
        "character_p5_cartoon",
        "procedural_art_drawing",
        "anidoodle_code_film",
        "retro_collage_motion",
        "manim_math_explainer",
        "javascript_canvas_story",
        "huashu_art_motion",
    ]
    for fmt in expected_formats:
        assert fmt in FORMAT_CATALOG
        spec = FORMAT_CATALOG[fmt]
        assert "pipeline" in spec
        assert "rubric" in spec

    # Test keyword routing
    assert resolve_format("Whiteboard handdraw explainer") == "handdrawn_whiteboard"
    assert resolve_format("Animate Clawd in p5.brush") == "character_p5_cartoon"
    assert resolve_format("Mathematical 3Blue1Brown animation with Manim") == "manim_math_explainer"
    assert resolve_format("Retro collage motion video") == "retro_collage_motion"
    assert resolve_format("AniDoodle procedural code film") == "anidoodle_code_film"


def test_engine_registry_animation_engines() -> None:
    """Verify engine catalog exposes animation rendering engines."""
    catalog = get_engine_catalog()
    engine_ids = {e["id"] for e in catalog["rendering_engines"]}
    for expected in ["handdraw", "p5_brush", "claude_drawing", "anidoodle", "javascript_animation"]:
        assert expected in engine_ids

    # Test visual style resolution
    assert resolve_visual_style_profile("handdraw sketch explainer") == "whiteboard_handdraw"
    assert resolve_visual_style_profile("clawd cartoon") == "p5_brush_cartoon"
    assert resolve_visual_style_profile("retro collage cutout") == "retro_paper_collage"


def test_claude_drawing_styles_and_render(tmp_path: Path) -> None:
    """Verify claude drawing styles listing and procedural rendering."""
    styles = animation_skills_adapter.list_claude_drawing_styles()
    assert len(styles) >= 80
    assert "blueprint" in styles
    assert "artdeco" in styles
    assert "bauhaus" in styles

    out_file = tmp_path / "test_blueprint_unit.png"
    res = animation_skills_adapter.render_claude_drawing(
        style="blueprint",
        output_path=out_file,
        width=400,
        height=300,
        seed=101,
    )
    assert res["ok"] is True
    assert out_file.is_file()
    assert out_file.stat().st_size > 500


def test_motion_design_review() -> None:
    """Verify motion design principles audit."""
    spec_bad = {"timing_sec": 0.05, "easing": "linear", "active_elements": 9}
    audit = animation_skills_adapter.review_motion_design(spec_bad)
    assert audit["ok"] is True
    assert audit["motion_score"] < 0.70
    assert len(audit["findings"]) >= 3

    spec_good = {"timing_sec": 0.8, "easing": "easeInOut", "active_elements": 2}
    audit_good = animation_skills_adapter.review_motion_design(spec_good)
    assert audit_good["motion_score"] == 1.0
    assert len(audit_good["findings"]) == 0


def test_retro_collage_prompt_compiler() -> None:
    """Verify retro collage prompt compilation and copyright safety check."""
    clean = animation_skills_adapter.compile_retro_collage_prompt(
        reference_image="vintage_clock.png",
        subject="An antique brass clockwork owl",
        action="spins its gears and blinks its mechanical eyes",
    )
    assert clean["ok"] is True
    assert "Vintage collage" in clean["prompt"]
    assert len(clean["copyright_redlines_flagged"]) == 0

    flagged = animation_skills_adapter.compile_retro_collage_prompt(
        reference_image="disney.png",
        subject="Mickey Mouse",
        action="dancing",
    )
    assert flagged["ok"] is False
    assert "disney" in flagged["copyright_redlines_flagged"] or "mickey" in flagged["copyright_redlines_flagged"]


def test_mcp_server_animation_tools() -> None:
    """Verify MCP tools dispatch for animation skills."""
    tool_names = {t["name"] for t in TOOLS}
    for t_name in [
        "studio_list_animation_skills",
        "studio_list_claude_drawing_styles",
        "studio_render_claude_drawing",
        "studio_review_motion_design",
        "studio_compile_retro_collage_prompt",
    ]:
        assert t_name in tool_names

    res_skills = handle_tool_call("studio_list_animation_skills", {})
    assert len(res_skills["skills"]) == 9

    res_review = handle_tool_call("studio_review_motion_design", {"timing_sec": 0.5, "easing": "easeInOut"})
    assert res_review["ok"] is True


def test_rest_api_endpoints() -> None:
    """Verify FastAPI endpoints for animation skills."""
    client = TestClient(app)

    r_skills = client.get("/api/skills/animation")
    assert r_skills.status_code == 200
    assert len(r_skills.json()["skills"]) == 9

    r_styles = client.get("/api/skills/drawing/styles")
    assert r_styles.status_code == 200
    assert len(r_styles.json()["styles"]) >= 80
