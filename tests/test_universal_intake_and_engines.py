"""Acceptance tests for Universal Creative Intake, Reference Intelligence, 4 Visual Styles, Free Mode Enforcement, v1 API & Antigravity MCP Parity."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.mcp_server import TOOLS, handle_tool_call
from backend.orchestration.engine_registry import (
    VISUAL_STYLE_PROFILES,
    is_free_open_source_mode,
    resolve_visual_style_profile,
)
from backend.services.reference_service import ReferenceResolver, ReferenceType, validate_external_url

client = TestClient(app)


def _make_sample_image(path: Path, color: str = "blue") -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=320x180:d=0.1", "-vframes", "1", str(path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return path


def _make_sample_video(path: Path, duration: float = 2.0) -> Path:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x180:rate=12",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return path


def test_ssrf_protection_and_reference_resolver() -> None:
    """Verify SSRF protection blocks loopback/private/link-local addresses and ReferenceResolver classifies URLs accurately."""
    for blocked in (
        "http://127.0.0.1:8080/admin",
        "http://localhost/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.1/config",
        "file:///etc/passwd",
    ):
        chk = validate_external_url(blocked)
        assert chk["safe"] is False, f"Expected SSRF block for {blocked}"

    resolver = ReferenceResolver()
    assert resolver.detect_source("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == ReferenceType.YOUTUBE_VIDEO
    assert resolver.detect_source("https://www.youtube.com/@BlenderFoundation") == ReferenceType.YOUTUBE_CHANNEL
    assert resolver.detect_source("https://www.instagram.com/reel/C123456789/") == ReferenceType.INSTAGRAM_REEL
    assert resolver.detect_source("https://www.instagram.com/p/C987654321/") == ReferenceType.INSTAGRAM_POST
    assert resolver.detect_source("https://www.instagram.com/studioghibli/") == ReferenceType.INSTAGRAM_PROFILE
    assert resolver.detect_source("https://cdn.example.com/sample.mp4") == ReferenceType.DIRECT_MEDIA
    assert resolver.detect_source("https://en.wikipedia.org/wiki/Indus_Valley_Civilisation") == ReferenceType.WEBSITE

    # Instagram profile must honestly report login/platform limitations and never claim full scraping
    ig_prof = resolver.resolve_sync(
        "https://www.instagram.com/studioghibli/",
        roles=["visual_style"],
        user_notes="Use warm hand-painted storybook aesthetic",
    )
    assert ig_prof["source_type"] == ReferenceType.INSTAGRAM_PROFILE
    assert ig_prof["access_status"] in ("metadata_only", "restricted_auth_required")
    assert any("Instagram profile" in lim for lim in ig_prof["limitations"])


def test_prompt_with_five_urls_and_uploaded_media(tmp_path: Path) -> None:
    """Test prompt + 5 URLs + 3 images + 1 video + 1 document through /api/v1/productions."""
    img1 = _make_sample_image(tmp_path / "ref1.png", "navy")
    img2 = _make_sample_image(tmp_path / "ref2.png", "darkred")
    img3 = _make_sample_image(tmp_path / "ref3.png", "darkgreen")
    vid1 = _make_sample_video(tmp_path / "ref_clip.mp4", duration=2.0)
    doc1 = tmp_path / "notes.txt"
    doc1.write_text("Indus Valley Harappa and Mohenjo-daro urban planning notes and brick ratios.", encoding="utf-8")

    five_urls = [
        {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "roles": ["visual_style", "story_reference"], "user_notes": "Pacing ref"},
        {"url": "https://www.youtube.com/@FallofCivilizations", "roles": ["story_reference"], "user_notes": "Documentary tone"},
        {"url": "https://www.instagram.com/reel/C123456789/", "roles": ["camera_reference"], "user_notes": "Transitions"},
        {"url": "https://www.instagram.com/natgeo/", "roles": ["visual_style"], "user_notes": "Color palette"},
        {"url": "https://example.com/indus-history", "roles": ["factual_source"], "user_notes": "Historical timeline"},
    ]

    resp = client.post(
        "/api/v1/productions",
        json={
            "prompt": "Create a 12-second animated documentary about the Indus Valley Civilization in hand-drawn storybook style.",
            "target_duration_sec": 12,
            "visual_style": "hand_drawn_storybook",
            "production_mode": "free_open_source",
            "references": five_urls,
            "uploads": [
                {"file_path": str(img1), "roles": ["visual_style", "environment_reference"], "user_notes": "Night palette"},
                {"file_path": str(img2), "roles": ["character_reference"], "user_notes": "Robes"},
                {"file_path": str(img3), "roles": ["environment_reference"], "user_notes": "Foliage"},
                {"file_path": str(vid1), "roles": ["camera_reference", "animation_reference"], "user_notes": "Motion cadence"},
                {"file_path": str(doc1), "roles": ["factual_source"], "user_notes": "Primary notes"},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    prod_id = data["production_id"]
    assert data["project"]["visual_style"] == "hand_drawn_storybook"
    assert data["project"]["production_mode_policy"] == "free_open_source"
    assert len(data["reference_assets"]) == 10

    # Verify video analysis extracted keyframes and scene boundaries
    vid_refs = [r for r in data["reference_assets"] if r["asset_type"] == "video"]
    assert len(vid_refs) >= 1
    assert "scene_boundaries_sec" in vid_refs[0]["analysis"]
    assert "keyframes" in vid_refs[0]["analysis"]

    # Verify Production Bible artifact and 28-artifact package invariant
    pkg_resp = client.get(f"/api/projects/{prod_id}/package")
    assert pkg_resp.status_code == 200
    pkg = pkg_resp.json()
    assert len(pkg["artifacts"]) == 28
    bible_art = next(a for a in pkg["artifacts"] if a["artifact_name"] == "continuity_bible.json")
    bible_data = json.loads(bible_art["content_text"])
    for key in (
        "visual_style",
        "color_palette",
        "lighting",
        "camera_language",
        "world_rules",
        "animation_principles",
        "voice_characteristics",
        "continuity_constraints",
    ):
        assert key in bible_data, f"Missing {key} in ProductionBible"


def test_frontend_and_mcp_parity_and_tools() -> None:
    """Verify Frontend REST API and Antigravity MCP tools share the exact same pipeline and expose all 33 tools."""
    tool_names = {t["name"] for t in TOOLS}
    required_mcp = {
        "create_production",
        "add_production_reference",
        "upload_production_asset",
        "analyze_references",
        "get_production_brief",
        "approve_production_brief",
        "generate_research",
        "generate_script",
        "generate_storyboard",
        "get_production_status",
        "approve_scene",
        "regenerate_scene",
        "render_production",
        "export_production",
    }
    assert required_mcp.issubset(tool_names)
    assert len(TOOLS) >= 33

    prompt = "Create a 10-second educational explainer on solar eclipses in 2D illustrated style."
    fe_res = client.post(
        "/api/v1/productions",
        json={"prompt": prompt, "target_duration_sec": 10, "visual_style": "2d_illustrated", "production_mode": "free_open_source"},
    ).json()
    mcp_res = handle_tool_call(
        "create_production",
        {"prompt": prompt, "target_duration_sec": 10, "visual_style": "2d_illustrated", "production_mode": "free_open_source"},
    )

    assert fe_res["project"]["category"] == mcp_res["project"]["category"]
    assert fe_res["project"]["visual_style"] == mcp_res["project"]["visual_style"] == "2d_illustrated"
    assert len(fe_res["scenes"]) == len(mcp_res["scenes"])

    mcp_pid = mcp_res["production_id"]
    brief_res = handle_tool_call("get_production_brief", {"production_id": mcp_pid})
    assert brief_res["ok"] is True

    app_res = handle_tool_call("approve_production_brief", {"production_id": mcp_pid, "edits": {"visual_style": "pixel_art"}})
    assert app_res["ok"] is True
    assert app_res["project"]["project"]["visual_style"] == "pixel_art"


def test_four_visual_styles_scene_regeneration_pause_resume_and_free_mode(monkeypatch, tmp_path: Path) -> None:
    """Verify all 4 visual styles, Free & Open-Source Mode blocking paid APIs, single-scene regeneration, pause/resume, and real MP4 export."""
    from backend.orchestration.renderer import render_scene_clip

    # Even if OPENAI_API_KEY and RUNWAYML_API_SECRET are set in env, free_open_source mode must block them
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-should-never-be-called")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "rw-dummy-should-never-be-called")
    assert is_free_open_source_mode("free_open_source") is True

    for style_key, expected_engine in (
        ("pixel_art", "libresprite"),
        ("2d_illustrated", "hyperframes"),
        ("3d_stylized", "threejs"),
        ("hand_drawn_storybook", "opentoonz"),
    ):
        assert style_key in VISUAL_STYLE_PROFILES
        assert resolve_visual_style_profile(style_key) == style_key
        out_clip = tmp_path / f"style_{style_key}.mp4"
        res = render_scene_clip(
            {
                "id": f"sc_{style_key}",
                "title": f"Scene {style_key}",
                "narration_segment": f"Testing {style_key} visual style rendering.",
                "visual_description": f"Rich {style_key} scene composition.",
                "generation_prompt": f"Rich {style_key} scene composition.",
                "visual_style": style_key,
                "duration_sec": 1.5,
            },
            out_clip,
            category="animation",
            resolution="640x360",
            fps=12,
            render_engine=expected_engine,
            project_topic=f"Style {style_key}",
            production_mode="free_open_source",
        )
        assert out_clip.is_file() and out_clip.stat().st_size > 1000
        assert res.get("provider") not in ("openai", "runway", "sora", "veo", "kling", "luma")

    # Create a concise 2-scene project in pixel_art style and free_open_source mode
    created = handle_tool_call(
        "create_production",
        {
            "prompt": "A 4-second retro pixel art adventure about a brave robot exploring an ancient temple.",
            "target_duration_sec": 4,
            "visual_style": "pixel_art",
            "production_mode": "free_open_source",
            "resolution": "640x360",
            "fps": 12,
        },
    )
    pid = created["production_id"]
    scenes = created["scenes"]
    assert len(scenes) >= 2
    assert scenes[0]["visual_style"] == "pixel_art"

    # Approve scene 1 via MCP
    sc0_id = scenes[0]["id"]
    sc1_id = scenes[1]["id"]
    app_sc = handle_tool_call("approve_scene", {"production_id": pid, "scene_id": sc0_id, "approved": True, "notes": "Looks great"})
    assert app_sc["ok"] is True

    # Test pause and resume
    pause_res = client.post(f"/api/projects/{pid}/pause").json()
    assert pause_res["status"] == "paused"

    # Render full production synchronously via MCP
    rendered = handle_tool_call("render_production", {"production_id": pid, "resume": True, "enforce_approval": False})
    assert rendered["project"]["status"] == "completed"

    ws = Path(rendered["project"]["workspace_dir"])
    final_mp4 = ws / "exports" / "final_production.mp4"
    assert final_mp4.is_file() and final_mp4.stat().st_size > 10_000

    # Verify zero paid cloud providers were used in assets
    for ast in rendered["assets"]:
        assert ast["provider"] not in ("openai_tts", "runway", "sora", "veo", "kling", "luma"), f"Paid provider {ast['provider']} used in free_open_source mode!"

    # Record mtime of scene 2 before regenerating scene 1 in hand_drawn_storybook style
    sc1_mp4 = ws / "renders" / f"{sc1_id}.mp4"
    sc1_mtime_before = sc1_mp4.stat().st_mtime

    regen = handle_tool_call(
        "regenerate_scene",
        {
            "production_id": pid,
            "scene_id": sc0_id,
            "visual_style": "hand_drawn_storybook",
            "visual_prompt": "Warm watercolor storybook illustration of the robot at the temple gate",
        },
    )
    assert regen["ok"] is True
    assert regen["visual_style"] == "hand_drawn_storybook"
    # Unrelated scene 2 clip file was NOT rebuilt
    assert sc1_mp4.stat().st_mtime == sc1_mtime_before

    # Export custom deliverable via MCP export_production
    exp = handle_tool_call("export_production", {"production_id": pid, "format": "mp4", "codec": "h264", "resolution": "640x360", "fps": 12})
    assert exp["ok"] is True
    assert Path(exp["output_path"]).is_file()
