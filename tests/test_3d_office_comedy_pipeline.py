"""Tests for 3D office break-room comedy pipeline: parser, 3-char rigs, 3 voices, strict 3D routing, QA, and Milestone 1 render."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from backend.integrations.antigravity_adapter import AntigravityAdapter
from backend.integrations.blender_adapter import render_blender_scene
from backend.orchestration.audio_studio import generate_tts, generate_viseme_timeline, probe_duration
from backend.orchestration.qa import run_qa_verification
from backend.services.blender_character_builder import (
    BREAKROOM_BLEND,
    ensure_office_cast_and_set,
    get_character_blend_path,
)
from backend.services.document_parser import parse_structured_screenplay
from backend.services.screenwriting_service import develop_and_write_screenplay, validate_screenplay_completeness

OFFICE_PROMPT = """3D stylized cartoon comedy (30 seconds).
Three purple characters sit around a table in an office break room: Boss (wearing a black tie, serious, nervous gestures), Employee (wearing a blue ID card, holding a coffee cup, shocked expression), and Friend (wearing headphones, sarcastic smirk).

Scene 1 (0–8 seconds): Wide establishing shot of the office break room. Boss says, "We need to talk about the Q4 budget." Employee replies, "Wait, did something happen?"
Scene 2 (8–15 seconds): Medium close-up on Boss nervously fidgeting. Boss says, "I accidentally ordered four hundred espresso machines instead of four."
Scene 3 (15–22 seconds): Reaction shot on Employee who spits out his coffee in shock. Employee shouts, "Four hundred?!"
Scene 4 (22–30 seconds): Group shot as Friend smirks and raises his hand. Friend says, "I mean, at least we won't fall asleep during meetings."
"""


def test_parser_extracts_four_scenes_time_ranges_and_five_dialogue_turns():
    parsed = parse_structured_screenplay(OFFICE_PROMPT)
    assert parsed["is_structured"] is True
    assert parsed["animation_style"] == "3d_stylized"
    assert len(parsed["scenes"]) == 4

    expected_ranges = [(0.0, 8.0, 8.0), (8.0, 15.0, 7.0), (15.0, 22.0, 7.0), (22.0, 30.0, 8.0)]
    for sc, (st, en, dur) in zip(parsed["scenes"], expected_ranges):
        assert sc["start_sec"] == st
        assert sc["end_sec"] == en
        assert sc["duration_sec"] == dur

    all_turns = [t for sc in parsed["scenes"] for t in sc["dialogue_turns"]]
    assert len(all_turns) == 5
    assert [(t["speaker"], t["line"]) for t in all_turns] == [
        ("Boss", "We need to talk about the Q4 budget."),
        ("Employee", "Wait, did something happen?"),
        ("Boss", "I accidentally ordered four hundred espresso machines instead of four."),
        ("Employee", "Four hundred?!"),
        ("Friend", "I mean, at least we won't fall asleep during meetings."),
    ]

    bible_names = {c["name"] for c in parsed["character_bible"]}
    assert bible_names == {"Boss", "Employee", "Friend"}
    val = validate_screenplay_completeness(parsed["scenes"], OFFICE_PROMPT)
    assert val["passed"] is True, val


def test_screenplay_service_preserves_turns_and_casts_three_voices():
    pkg = develop_and_write_screenplay(
        prompt=OFFICE_PROMPT,
        format_key="animation_3d",
        brief={"target_duration_sec": 30.0},
        visual_style="3d_stylized",
    )
    assert pkg["script_validation"]["passed"] is True
    assert len(pkg["scenes"]) == 4
    s1_turns = pkg["scenes"][0]["dialogue_turns"]
    assert len(s1_turns) == 2
    assert s1_turns[0]["voice_id"] != s1_turns[1]["voice_id"]
    s4_turns = pkg["scenes"][3]["dialogue_turns"]
    assert s4_turns[0]["speaker"] == "Friend"
    assert s4_turns[0]["voice_id"] == "character_3"
    assert len({s1_turns[0]["voice_id"], s1_turns[1]["voice_id"], s4_turns[0]["voice_id"]}) == 3


def test_strict_3d_routing_and_no_capsule_fallback(tmp_path: Path):
    ag = AntigravityAdapter()
    assert ag.route_shot_strategy("animation", requested_engine="blender") == ["blender"]

    res = render_blender_scene(
        scene={
            "title": "Missing Rig Test",
            "duration_sec": 2.0,
            "character_mesh_path": str(tmp_path / "does_not_exist.blend"),
        },
        output_mp4=tmp_path / "out.mp4",
        work_dir=tmp_path / "work",
    )
    assert res["ok"] is False
    assert res["status"] == "FAILED"


def test_tts_rejects_silence_and_qa_catches_duration_mismatch(tmp_path: Path):
    sil = generate_tts("Silence.", tmp_path / "sil.wav")
    assert sil["success"] is False

    # Build a 4-second static video and verify QA catches both duration mismatch (vs 30s) and static frames
    static_mp4 = tmp_path / "static_4s.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=purple:s=1920x1080:r=30:d=4",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(static_mp4),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    from backend.models import ProjectCreateRequest
    from backend.orchestration.director import create_project

    proj = create_project(ProjectCreateRequest(prompt="QA mismatch test", target_duration_sec=30.0))
    pid = proj["project"]["id"]
    qa = run_qa_verification(
        project_id=pid,
        video_path=static_mp4,
        expected_aspect_ratio="16:9",
        expected_fps=30,
        expected_duration_sec=30.0,
        expected_resolution="1920x1080",
    )
    assert qa["passed"] is False
    assert qa["human_visual_approved"] is False
    failed_names = {c["name"] for c in qa["checks"] if not c["passed"]}
    assert "duration_matches_target" in failed_names
    assert "visible_animation_check" in failed_names


def test_milestone_1_8sec_three_character_blender_scene(tmp_path: Path):
    """Milestone 1: Render 8-second 1920x1080@30fps Blender scene with 3 purple characters, 2 voices, and lip-sync."""
    assets = ensure_office_cast_and_set()
    assert assets["ok"] is True

    # Synthesize Scene 1's two dialogue turns with distinct voices
    t1_wav = tmp_path / "boss_t1.wav"
    t2_wav = tmp_path / "emp_t2.wav"
    r1 = generate_tts("We need to talk about the Q4 budget.", t1_wav, voice_id="character_1")
    r2 = generate_tts("Wait, did something happen?", t2_wav, voice_id="character_2")
    assert r1["success"] and r1["provider"] not in ("silence", "none")
    assert r2["success"] and r2["provider"] not in ("silence", "none")
    assert r1["voice_used"] != r2["voice_used"]

    d1 = probe_duration(t1_wav)
    lip1 = generate_viseme_timeline(t1_wav, "We need to talk about the Q4 budget.", speaker="Boss", offset_sec=0.3, fps=30)
    lip2 = generate_viseme_timeline(t2_wav, "Wait, did something happen?", speaker="Employee", offset_sec=0.3 + d1 + 0.4, fps=30)

    out_mp4 = tmp_path / "milestone1_scene1.mp4"
    render_res = render_blender_scene(
        scene={
            "title": "Office Break Room Scene 1",
            "duration_sec": 8.0,
            "shot_type": "wide_establishing",
            "blender_engine": "BLENDER_EEVEE_NEXT",
            "environment_blend_path": str(BREAKROOM_BLEND),
            "lip_sync_frames": lip1 + lip2,
            "characters": [
                {
                    "name": "Boss",
                    "mesh_path": str(get_character_blend_path("boss")),
                    "location": [-1.25, 0.0, 0.0],
                    "rotation_z": -75.0,
                    "seated": True,
                    "expression": "serious",
                    "gesture": "nervous_gesture",
                },
                {
                    "name": "Employee",
                    "mesh_path": str(get_character_blend_path("employee")),
                    "location": [0.0, 0.85, 0.0],
                    "rotation_z": 0.0,
                    "seated": True,
                    "expression": "serious",
                    "gesture": "idle_sit",
                },
                {
                    "name": "Friend",
                    "mesh_path": str(get_character_blend_path("friend")),
                    "location": [1.25, 0.0, 0.0],
                    "rotation_z": 75.0,
                    "seated": True,
                    "expression": "smirk",
                    "gesture": "idle_sit",
                },
            ],
        },
        output_mp4=out_mp4,
        work_dir=tmp_path / "blender_work",
        width=1920,
        height=1080,
        fps=30,
    )
    assert render_res["ok"] is True, render_res
    assert out_mp4.is_file()

    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(out_mp4)],
            text=True,
        )
    )
    v_stream = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
    assert int(v_stream["width"]) == 1920
    assert int(v_stream["height"]) == 1080
    dur = float(probe["format"]["duration"])
    assert 7.5 <= dur <= 8.5


def test_milestone_2_full_30sec_four_scene_production():
    """Milestone 2: Full end-to-end 30-second, 4-scene, 3-character 3D Blender production + QA gate."""
    from backend.models import ProjectCreateRequest
    from backend.orchestration.director import create_project, run_production

    created = create_project(
        ProjectCreateRequest(
            title="Office Break Room Espresso Incident",
            prompt=OFFICE_PROMPT,
            target_duration_sec=30.0,
            visual_style="3d_stylized",
            preferred_render_engine="blender",
            resolution="1920x1080",
            fps=30,
            aspect_ratio="16:9",
        )
    )
    pid = created["project"]["id"]
    assert len(created["scenes"]) == 4
    char_names = {c["name"] for c in created["characters"]}
    assert char_names == {"Boss", "Employee", "Friend"}

    detail = run_production(pid)
    assert detail["project"]["status"] == "completed", detail["project"]

    ws = Path(detail["project"]["workspace_dir"])
    final_mp4 = ws / "exports" / "final_production.mp4"
    assert final_mp4.is_file()

    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(final_mp4)],
            text=True,
        )
    )
    v_stream = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
    a_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    assert int(v_stream["width"]) == 1920
    assert int(v_stream["height"]) == 1080
    assert len(a_streams) >= 1
    dur = float(probe["format"]["duration"])
    assert 26.0 <= dur <= 34.0, f"Expected ~30s, got {dur}s"

    qa_report = json.loads((ws / "deliverables" / "final_qa_report.json").read_text(encoding="utf-8"))
    assert qa_report["passed"] is True, qa_report
    assert qa_report["human_visual_approved"] is False
    assert qa_report["approval_status"] == "PENDING_HUMAN_VISUAL_REVIEW"

    srt_path = ws / "subtitles" / "subtitles_en.srt"
    assert srt_path.is_file() and "-->" in srt_path.read_text(encoding="utf-8")

