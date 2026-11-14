"""Scenario tests for Universal AI Video Studio (Phases 1-8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from backend.services.format_catalog import FORMAT_CATALOG
from backend.services.package_service import REQUIRED_28_ARTIFACTS
from backend.services.script_evaluator import evaluate_screenplay


def test_scenario_guided_intake_asks_type_and_duration_first():
    with TestClient(app) as client:
        r1 = client.post("/api/intake/start", json={"prompt": "I want to create a cinematic documentary about the rise of electric vehicles in India."})
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["intake_stage"] == "awaiting_type_and_duration"
        assert len(d1["pending_questions"]) == 2
        assert "type of video" in d1["pending_questions"][0]["question"].lower()
        assert "how long" in d1["pending_questions"][1]["question"].lower()

        pid = d1["project_id"]
        r2 = client.post(f"/api/intake/{pid}/answer", json={"video_format": "documentaries", "target_duration_sec": 60, "confirm_brief": True})
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["intake_stage"] == "brief_confirmed"
        assert d2["confirmed"]["video_format"] == "documentaries"
        assert d2["confirmed"]["target_duration_sec"] == 60.0
        assert "platform" in d2["assumed"]


def test_scenario_25_formats_and_research_and_reference_upload(tmp_path: Path):
    assert len(FORMAT_CATALOG) == 25
    with TestClient(app) as client:
        r = client.get("/api/formats")
        assert r.status_code == 200
        assert len(r.json()["formats"]) == 25

        proj = client.post("/api/projects", json={"prompt": "Create a 30-second documentary about solar energy.", "target_duration_sec": 30}).json()
        pid = proj["project"]["id"]
        ws = Path(proj["project"]["workspace_dir"])

        # Offline-safe research check
        res_r = client.post(f"/api/projects/{pid}/research?allow_web=false")
        assert res_r.status_code == 200
        for fname in ("research_dossier.md", "source_registry.json", "fact_check_ledger.json", "research_timeline.json"):
            assert (ws / "package" / fname).exists()

        # Reference image upload with explicit role
        img_path = tmp_path / "ref_palette.png"
        Image.new("RGB", (320, 180), (24, 64, 128)).save(img_path)
        with open(img_path, "rb") as fh:
            up = client.post(f"/api/projects/{pid}/references/upload?intended_role=color_palette", files={"file": ("ref_palette.png", fh, "image/png")})
        assert up.status_code == 200
        up_json = up.json()
        assert up_json["intended_role"] == "color_palette"
        assert len(up_json["analysis"]["palette_hex"]) >= 1
        for fname in ("reference_analysis.json", "reference_style_guide.md", "reference_asset_index.json", "reference_timeline.json", "asset_registry.json"):
            assert (ws / "package" / fname).exists()


def test_scenario_28_package_versioning_evaluator_and_approval_gate():
    with TestClient(app) as client:
        proj = client.post("/api/projects", json={"prompt": "Make a 30-second Instagram Reel about a new camera launch.", "target_duration_sec": 30}).json()
        pid = proj["project"]["id"]
        ws = Path(proj["project"]["workspace_dir"])

        # All 28 artifacts exist
        for fname in REQUIRED_28_ARTIFACTS:
            assert (ws / "package" / fname).exists(), f"Missing {fname}"

        pkg = client.get(f"/api/projects/{pid}/package").json()
        assert len(pkg["artifacts"]) == 28
        assert pkg["approval_status"]["approved"] is False

        # Mandatory approval gate blocks production when enforce_approval=true
        blocked = client.post(f"/api/projects/{pid}/run?sync=true&enforce_approval=true")
        assert blocked.status_code == 409

        # Edit screenplay -> creates immutable v2
        upd = client.put(f"/api/projects/{pid}/package/screenplay.md", json={"content": "# Edited Screenplay\n\nScene 1..."})
        assert upd.status_code == 200
        assert upd.json()["version"] == 2

        # Approve all gates -> unlocks
        app_res = client.post(f"/api/projects/{pid}/gates/approve", json={"gate_name": "all"})
        assert app_res.status_code == 200
        pkg2 = client.get(f"/api/projects/{pid}/package").json()
        assert pkg2["approval_status"]["approved"] is True

    # Evaluator rejects generic boilerplate
    bad_eval = evaluate_screenplay(
        "documentaries",
        {"target_duration_sec": 60},
        [{"title": "S1", "narration_segment": "Chapter 1, part 2: advancing the narrative with clear visual storytelling.", "visual_description": "short"}],
    )
    assert bad_eval["passed"] is False
    assert len(bad_eval["hard_rejections"]) >= 1


def test_scenario_antigravity_plugin_and_mcp_server():
    plugin_root = Path("plugins/universal-video-studio")
    assert (plugin_root / "plugin.json").exists()
    assert (plugin_root / "mcp_config.json").exists()
    assert (plugin_root / "hooks.json").exists()
    assert len(list((plugin_root / "skills").glob("*/SKILL.md"))) == 19
    assert len(list((plugin_root / "agents").glob("*.md"))) == 22

    # Smoke test stdio MCP server
    reqs = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "studio_list_formats", "arguments": {}}}),
    ]) + "\n"
    proc = subprocess.run(
        [".venv/bin/python", "-m", "backend.mcp_server"],
        input=reqs, text=True, capture_output=True, timeout=15, check=True,
    )
    lines = [json.loads(ln) for ln in proc.stdout.strip().splitlines()]
    assert len(lines) == 3
    assert lines[0]["result"]["serverInfo"]["name"] == "universal-video-studio"
    assert len(lines[1]["result"]["tools"]) == 7
    assert len(json.loads(lines[2]["result"]["content"][0]["text"])["formats"]) == 25
