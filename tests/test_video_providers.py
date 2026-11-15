"""Cloud providers must stay silent unless a real file comes back."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import detect_hardware
from backend.db import init_db
from backend.main import app
from backend.providers.video.openmontage_video import cloud_duration
from backend.providers.video.router import generate_cloud_shot

_KEYS = (
    "GOOGLE_API_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "FAL_KEY",
    "FAL_AI_API_KEY",
    "KLING_API_KEY",
    "RUNWAY_API_KEY",
    "ARK_API_KEY",
    "MINIMAX_API_KEY",
    "OPENAI_API_KEY",
)


def _clear_keys(monkeypatch) -> None:
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)


def test_health_reports_provider_states_without_claiming_ready():
    init_db()
    with TestClient(app) as client:
        health = client.get("/api/health").json()
    assert health["ok"] is True
    states = {row["id"]: row for row in health["video_providers"]}
    assert set(states) == {"veo", "kling", "runway", "seedance", "minimax", "wan"}
    for row in health["video_providers"] + health["image_providers"]:
        assert row["state"] in {"not_configured", "configured", "not_installed", "capability_unsupported"}
        assert row["authenticated"] is False
        assert row["production_ready"] is False
    if not (os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY") or detect_hardware().local_diffusion_eligible):
        assert states["wan"]["state"] == "capability_unsupported"


def test_unconfigured_provider_writes_no_file(tmp_path: Path, monkeypatch):
    _clear_keys(monkeypatch)
    output = tmp_path / "shot.mp4"
    result = generate_cloud_shot("a detective in Kolkata", output, 6, "16:9")
    assert result["ok"] is False
    assert result["status"] == "NOT_CONFIGURED"
    assert result["provider"] is None
    assert output.exists() is False


def test_configured_provider_is_called_once_and_keeps_a_real_file(tmp_path: Path, monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("RUNWAY_API_KEY", "test-key")
    monkeypatch.setenv("ARK_API_KEY", "other-key")
    calls: list[str] = []

    def fake_execute(tool_name: str, params: dict):
        calls.append(tool_name)
        Path(params["output_path"]).write_bytes(b"v" * 2048)
        return {"success": True, "artifacts": {}, "metadata": {}}

    monkeypatch.setattr(
        "backend.providers.video.openmontage_video.openmontage_adapter.execute_tool",
        fake_execute,
    )
    output = tmp_path / "shot.mp4"
    result = generate_cloud_shot("a detective in Kolkata", output, 8, "16:9")
    assert calls == ["runway_video"]
    assert result["ok"] is True
    assert result["engine"] == "runway"
    assert result["source_type"] == "cloud_ai_video"
    assert result["generation_state"] == "ready"
    assert output.stat().st_size > 1024


def test_failed_provider_deletes_the_placeholder_and_does_not_try_the_next(tmp_path: Path, monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("RUNWAY_API_KEY", "test-key")
    monkeypatch.setenv("ARK_API_KEY", "other-key")
    calls: list[str] = []

    def fake_execute(tool_name: str, params: dict):
        calls.append(tool_name)
        Path(params["output_path"]).write_bytes(b"nope")
        return {"success": False, "error": "quota"}

    monkeypatch.setattr(
        "backend.providers.video.openmontage_video.openmontage_adapter.execute_tool",
        fake_execute,
    )
    output = tmp_path / "shot.mp4"
    result = generate_cloud_shot("a detective in Kolkata", output, 5, "16:9")
    assert calls == ["runway_video"]
    assert result["ok"] is False
    assert result["generation_state"] == "failed"
    assert output.exists() is False


def test_duration_matches_the_provider_contract():
    assert cloud_duration("veo_video", 8) == "8s"
    assert cloud_duration("veo_video", 4) == "4s"
    assert cloud_duration("kling_video", 8) == "10"
    assert cloud_duration("kling_official_video", 5) == "5"
    assert cloud_duration("runway_video", 6) == 6
