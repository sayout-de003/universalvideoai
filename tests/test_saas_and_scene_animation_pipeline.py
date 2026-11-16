"""Tests for SaaS product explainer, dynamic 3D/2D characters, and scene-by-scene animation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from backend.models import ProjectCreateRequest
from backend.orchestration.audio_studio import sanitize_spoken_voiceover, generate_tts, probe_duration
from backend.orchestration.director import create_project, run_production
from backend.orchestration.qa import run_qa_verification
from backend.services.blender_character_builder import (
    TECH_OFFICE_BLEND,
    derive_character_spec,
    ensure_character_blend,
    ensure_scene_environment,
    get_character_blend_path,
)
from backend.services.document_parser import parse_structured_screenplay

SAAS_ANIMATION_PROMPT = """3D stylized cartoon tech explainer (15 seconds).
Two tech founders, Sarah (CTO, wearing a navy blazer and glasses) and Mark (Lead Engineer, wearing a charcoal hoodie), discuss their AI video platform in their modern tech office.

Scene 1 (0–8 seconds): Wide shot of Sarah and Mark in front of a giant holographic dashboard showing real-time metrics. Sarah says, "Our new video engine renders thirty frames per second in the cloud." Mark replies, "And our voiceover sync is sub-millisecond."
Scene 2 (8–15 seconds): Medium close-up on Mark gesturing at the live metrics. Mark says, "That means instant automated production for every SaaS team."
"""


def test_derive_and_build_dynamic_saas_characters():
    """Verify dynamic character specs and Blender .blend generation for non-office characters."""
    spec_sarah = derive_character_spec("Sarah", role="CTO", visual_desc="wearing navy blazer and glasses")
    assert spec_sarah["name"] == "Sarah"
    assert "glasses" in spec_sarah["props"]
    assert spec_sarah["slug"] == "sarah"

    spec_mark = derive_character_spec("Mark", role="Lead Engineer", visual_desc="wearing charcoal hoodie")
    assert spec_mark["name"] == "Mark"
    assert "id_card" in spec_mark["props"] or spec_mark["slug"] == "mark"

    p_sarah = ensure_character_blend("Sarah", role="CTO", visual_desc="navy blazer and glasses")
    assert p_sarah.is_file() and p_sarah.stat().st_size > 4096

    p_mark = ensure_character_blend("Mark", role="Lead Engineer", visual_desc="charcoal hoodie")
    assert p_mark.is_file() and p_mark.stat().st_size > 4096

    env_path = ensure_scene_environment("tech_saas")
    assert env_path.is_file() and env_path.stat().st_size > 4096


def test_saas_screenplay_parsing_and_voiceover_purity():
    """Ensure screenplay correctly extracts scenes, dialogue turns, character bible, and clean voiceover."""
    parsed = parse_structured_screenplay(SAAS_ANIMATION_PROMPT)
    assert parsed["is_structured"] is True
    assert len(parsed["scenes"]) == 2

    s1_turns = parsed["scenes"][0]["dialogue_turns"]
    assert len(s1_turns) == 2
    assert s1_turns[0]["speaker"] == "Sarah"
    assert "video engine" in s1_turns[0]["line"]
    assert s1_turns[1]["speaker"] == "Mark"
    assert "sub-millisecond" in s1_turns[1]["line"]

    for turn in s1_turns:
        clean = sanitize_spoken_voiceover(turn["line"])
        assert clean == turn["line"]
        assert "[" not in clean and "]" not in clean
        assert "#" not in clean


def test_qa_duration_tolerance_for_natural_dialogue(tmp_path: Path):
    """Verify that natural dialogue pacing with slight duration variance passes QA."""
    mp4_path = tmp_path / "test_18s.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=24:d=18",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=18",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(mp4_path),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Target 15.0s, actual 18.0s (3.0s diff <= 5.0s tolerance)
    proj = create_project(ProjectCreateRequest(prompt="Duration test", target_duration_sec=15.0))
    pid = proj["project"]["id"]
    qa = run_qa_verification(
        project_id=pid,
        video_path=mp4_path,
        expected_aspect_ratio="16:9",
        expected_fps=24,
        expected_duration_sec=15.0,
        expected_resolution="1280x720",
    )
    duration_check = next(c for c in qa["checks"] if c["name"] == "duration_matches_target")
    assert duration_check["passed"] is True, duration_check


def test_end_to_end_saas_animated_production():
    """End-to-end milestone: generate 15-second SaaS animated dialogue video and pass QA."""
    created = create_project(
        ProjectCreateRequest(
            title="SaaS AI Video Platform Explainer",
            prompt=SAAS_ANIMATION_PROMPT,
            target_duration_sec=15.0,
            visual_style="3d_stylized",
            preferred_render_engine="hyperframes",
            resolution="1280x720",
            fps=24,
            aspect_ratio="16:9",
        )
    )
    pid = created["project"]["id"]
    assert len(created["scenes"]) == 2

    detail = run_production(pid)
    assert detail["project"]["status"] == "completed", detail["project"]

    ws = Path(detail["project"]["workspace_dir"])
    final_mp4 = ws / "exports" / "final_production.mp4"
    assert final_mp4.is_file()

    # Validate output with ffprobe
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(final_mp4)],
            text=True,
        )
    )
    v_stream = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
    a_stream = [s for s in probe["streams"] if s["codec_type"] == "audio"][0]
    assert int(v_stream["width"]) == 1280
    assert int(v_stream["height"]) == 720
    assert float(probe["format"]["duration"]) >= 10.0

    # Validate QA report passes
    qa_report = json.loads((ws / "deliverables" / "final_qa_report.json").read_text(encoding="utf-8"))
    assert qa_report["passed"] is True, qa_report
    assert qa_report["automated_qa_passed"] is True
