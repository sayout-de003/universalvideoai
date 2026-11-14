"""Integration and End-to-End Production Tests for Universal AI Video Production Studio."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.integrations.openwhispr_adapter import openwhispr_adapter
from backend.main import app


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_integration_openmontage_and_registry(client: TestClient):
    h = client.get("/api/health").json()
    assert h["ok"] is True
    assert h["openmontage_available"] is True

    eng = client.get("/api/engines").json()
    assert eng["openmontage_tools_count"] >= 160
    assert len(eng["openmontage_pipelines"]) == 13
    assert any(r["id"] == "ffmpeg" and r["available"] for r in eng["rendering_engines"])


def test_integration_openwhispr_and_voice_parser():
    status = openwhispr_adapter.get_status()
    assert status["repo_present"] is True

    cmd1 = openwhispr_adapter.parse_voice_command("Regenerate scene four")
    assert cmd1["intent"] == "regenerate_scene"
    assert cmd1["params"]["scene_number"] == 4
    assert cmd1["requires_confirmation"] is True

    cmd2 = openwhispr_adapter.parse_voice_command("Generate subtitles in Hindi and English")
    assert cmd2["intent"] == "generate_subtitles"
    assert set(cmd2["params"]["languages"]) == {"hi", "en"}


def test_e2e_1_animated_cartoon_with_dialogue_music_sfx(client: TestClient):
    res = client.post(
        "/api/projects",
        json={"prompt": "Create a 30-second funny 2D animated cartoon about a cat that accidentally becomes president with sound effects.", "target_duration_sec": 12},
    ).json()
    pid = res["project"]["id"]
    try:
        assert res["project"]["category"] == "animation"
        assert res["project"]["render_engine"] == "hyperframes"
        run_res = client.post(f"/api/projects/{pid}/run?sync=true").json()
        assert run_res["project"]["status"] == "completed"
        assert run_res["qa_reports"][0]["passed"] == 1
        assert (Path(run_res["project"]["workspace_dir"]) / "stems" / "music.wav").exists()
        assert (Path(run_res["project"]["workspace_dir"]) / "stems" / "sfx.wav").exists()
    finally:
        client.delete(f"/api/projects/{pid}")


def test_e2e_2_faceless_educational_short_word_captions(client: TestClient):
    res = client.post(
        "/api/projects",
        json={"prompt": "Create a 60-second faceless YouTube Short explaining how black holes bend time with word-by-word captions.", "target_duration_sec": 12},
    ).json()
    pid = res["project"]["id"]
    try:
        assert res["project"]["aspect_ratio"] == "9:16"
        assert res["project"]["resolution"] == "1080x1920"
        run_res = client.post(f"/api/projects/{pid}/run?sync=true").json()
        assert run_res["project"]["status"] == "completed"
        assert (Path(run_res["project"]["workspace_dir"]) / "subtitles" / "subtitles_en.srt").exists()
    finally:
        client.delete(f"/api/projects/{pid}")


def test_e2e_3_and_4_documentary_and_educational_chapters(client: TestClient):
    doc = client.post(
        "/api/projects",
        json={"prompt": "Create a 5-minute historical documentary about ancient Rome with chapters.", "target_duration_sec": 15},
    ).json()
    pid_doc = doc["project"]["id"]
    try:
        assert doc["project"]["category"] == "documentary"
        run_doc = client.post(f"/api/projects/{pid_doc}/run?sync=true").json()
        assert run_doc["project"]["status"] == "completed"
        assert run_doc["qa_reports"][0]["passed"] == 1
    finally:
        client.delete(f"/api/projects/{pid_doc}")

    edu = client.post(
        "/api/projects",
        json={"prompt": "Create a 15-minute educational course about machine learning with chapters."},
    ).json()
    pid_edu = edu["project"]["id"]
    try:
        assert edu["project"]["category"] == "educational"
        assert edu["project"]["target_duration_sec"] == 900.0
        assert len(edu["chapters"]) == 4
        assert len(edu["scenes"]) >= 36
        assert max(float(s["duration_sec"]) for s in edu["scenes"]) < 40
    finally:
        client.delete(f"/api/projects/{pid_edu}")


def test_e2e_5_resumable_and_single_scene_regeneration_preserves_edits(client: TestClient):
    res = client.post(
        "/api/projects",
        json={"prompt": "Create a multi-chapter documentary about space exploration.", "target_duration_sec": 12},
    ).json()
    pid = res["project"]["id"]
    try:
        run_res = client.post(f"/api/projects/{pid}/run?sync=true").json()
        assert run_res["project"]["status"] == "completed"
        main_clips = [c for c in run_res["timeline"] if c["track"] == "main_video"]
        target_clip = main_clips[1]
        op_res = client.post(f"/api/projects/{pid}/timeline/op", json={"operation": "update_props", "clip_id": target_clip["id"], "properties": {"zoom": 1.25}}).json()
        assert op_res["ok"] is True

        scene1_id = run_res["scenes"][0]["id"]
        regen = client.post(f"/api/projects/{pid}/scenes/regenerate", json={"scene_id": scene1_id, "narration_text": "Updated opening narration for scene one."}).json()
        assert regen["ok"] is True
        updated_clip2 = next(c for c in regen["project"]["timeline"] if c["id"] == target_clip["id"])
        assert updated_clip2["manual_edited"] == 1
        assert updated_clip2["properties"]["zoom"] == 1.25

        assert client.post(f"/api/projects/{pid}/pause").json()["status"] == "paused"
        assert client.post(f"/api/projects/{pid}/resume?sync=true").json()["project"]["status"] == "completed"
    finally:
        client.delete(f"/api/projects/{pid}")


def test_e2e_6_3d_animated_scene_non_remotion_path(client: TestClient):
    res = client.post(
        "/api/projects",
        json={"prompt": "Create a 3D animated scene of a rotating geometric artifact in space.", "target_duration_sec": 9, "preferred_render_engine": "threejs"},
    ).json()
    pid = res["project"]["id"]
    try:
        assert res["project"]["render_engine"] == "threejs"
        run_res = client.post(f"/api/projects/{pid}/run?sync=true").json()
        assert run_res["project"]["status"] == "completed"
        assert any(Path(run_res["project"]["workspace_dir"]).glob("renders/*.threejs.html"))
        assert run_res["qa_reports"][0]["passed"] == 1
    finally:
        client.delete(f"/api/projects/{pid}")


def test_e2e_7_and_8_voice_editing_and_multilingual_export(client: TestClient):
    res = client.post(
        "/api/projects",
        json={"prompt": "Create a short documentary about ancient Egypt.", "target_duration_sec": 10, "subtitle_languages": ["en", "hi"]},
    ).json()
    pid = res["project"]["id"]
    try:
        run_res = client.post(f"/api/projects/{pid}/run?sync=true").json()
        ws = Path(run_res["project"]["workspace_dir"])
        assert (ws / "subtitles" / "subtitles_en.srt").exists()
        assert (ws / "subtitles" / "subtitles_hi.srt").exists()

        v1 = client.post("/api/voice/command", json={"transcript": "Regenerate scene 2", "project_id": pid, "confirmed": False}).json()
        assert v1["requires_confirmation"] is True
        v2 = client.post("/api/voice/command", json={"transcript": "Regenerate scene 2", "project_id": pid, "confirmed": True}).json()
        assert v2["requires_confirmation"] is False
        assert v2["result"]["ok"] is True

        exp = client.post(f"/api/projects/{pid}/export", json={"format": "mp4", "codec": "h264", "resolution": "1280x720", "fps": 30, "bitrate": "4M"}).json()
        assert exp["success"] is True
        assert Path(exp["output_path"]).exists()
    finally:
        client.delete(f"/api/projects/{pid}")
