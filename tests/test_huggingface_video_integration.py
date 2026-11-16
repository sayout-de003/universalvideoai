"""Comprehensive tests for Hugging Face Video Models integration.

Tests the 7 requested Hugging Face models:
1. VideoRebirthAI/hyperflow-h3-flash
2. Wan-AI/Wan2.2-TI2V-5B
3. Comfy-Org/PAN2
4. Wan-AI/Wan2.2-T2V-A14B
5. larryvrh/MiniMax-H3-Turbo-Lora
6. ZhengmingYu/DMAD
7. Wan-AI/Wan2.1-T2V-1.3B
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.orchestration.engine_registry import get_engine_catalog
from backend.providers.video.base import VideoRequest
from backend.providers.video.registry import list_video_providers, video_provider_readiness
from backend.services.huggingface_video_service import (
    HUGGINGFACE_VIDEO_MODELS,
    generate_video_with_huggingface_model,
    get_model_spec,
    list_all_huggingface_models,
)
from backend.services.shot_generation_service import generate_shot_for_scene


EXPECTED_MODELS = [
    "VideoRebirthAI/hyperflow-h3-flash",
    "Wan-AI/Wan2.2-TI2V-5B",
    "Comfy-Org/PAN2",
    "Wan-AI/Wan2.2-T2V-A14B",
    "larryvrh/MiniMax-H3-Turbo-Lora",
    "ZhengmingYu/DMAD",
    "Wan-AI/Wan2.1-T2V-1.3B",
]


def test_huggingface_catalog_has_all_seven_models():
    """Verify that all 7 requested Hugging Face models are defined in the catalog."""
    catalog_repos = [m["repo_id"] for m in HUGGINGFACE_VIDEO_MODELS.values()]
    for expected in EXPECTED_MODELS:
        assert expected in catalog_repos, f"Missing model {expected} in HUGGINGFACE_VIDEO_MODELS"

    assert len(HUGGINGFACE_VIDEO_MODELS) >= 7

    # Test key lookups
    assert get_model_spec("hyperflow-h3-flash")["repo_id"] == "VideoRebirthAI/hyperflow-h3-flash"
    assert get_model_spec("VideoRebirthAI/hyperflow-h3-flash")["name"] == "HyperFlow H3 Flash"
    assert get_model_spec("wan2.2-ti2v-5b")["repo_id"] == "Wan-AI/Wan2.2-TI2V-5B"
    assert get_model_spec("pan2")["repo_id"] == "Comfy-Org/PAN2"
    assert get_model_spec("wan2.2-t2v-a14b")["repo_id"] == "Wan-AI/Wan2.2-T2V-A14B"
    assert get_model_spec("minimax-h3-turbo-lora")["repo_id"] == "larryvrh/MiniMax-H3-Turbo-Lora"
    assert get_model_spec("dmad")["repo_id"] == "ZhengmingYu/DMAD"
    assert get_model_spec("wan2.1-t2v-1.3b")["repo_id"] == "Wan-AI/Wan2.1-T2V-1.3B"


def test_huggingface_models_list_and_readiness():
    """Verify listing models returns complete hardware eligibility and metadata."""
    models = list_all_huggingface_models(fetch_live_stats=False)
    assert len(models) >= 7
    for m in models:
        assert "repo_id" in m
        assert "params_b" in m
        assert "recommended_steps" in m
        assert "hardware_eligibility" in m
        assert "local_cached" in m


def test_huggingface_providers_registered_in_engine_registry():
    """Verify all 7 models appear in the engine catalog video providers."""
    catalog = get_engine_catalog()
    providers = catalog.get("video_providers", [])
    provider_models = [p.get("model") for p in providers]

    for expected in EXPECTED_MODELS:
        assert expected in provider_models, f"Model {expected} missing in engine catalog video_providers"

    # Verify rendering engine is present
    render_engines = [e["id"] for e in catalog.get("rendering_engines", [])]
    assert "huggingface" in render_engines


def test_huggingface_provider_registry_readiness():
    """Verify registry readiness includes the Hugging Face video providers."""
    providers = list_video_providers()
    provider_ids = [p.provider_id for p in providers]
    assert "hf_hyperflow_h3_flash" in provider_ids
    assert "hf_wan2_2_ti2v_5b" in provider_ids
    assert "hf_pan2" in provider_ids
    assert "hf_wan2_2_t2v_a14b" in provider_ids
    assert "hf_minimax_turbo_lora" in provider_ids
    assert "hf_dmad" in provider_ids
    assert "hf_wan2_1_t2v_1_3b" in provider_ids

    readiness = video_provider_readiness()
    r_map = {r["id"]: r for r in readiness}
    assert r_map["hf_hyperflow_h3_flash"]["state"] == "configured"
    assert r_map["hf_hyperflow_h3_flash"]["model"] == "VideoRebirthAI/hyperflow-h3-flash"


def test_generate_video_with_hyperflow_and_validate(tmp_path: Path):
    """Test generating a video clip using HyperFlow H3 Flash and validate with ffprobe."""
    out_mp4 = tmp_path / "hyperflow_test.mp4"
    res = generate_video_with_huggingface_model(
        model_key_or_repo="VideoRebirthAI/hyperflow-h3-flash",
        prompt="Cinematic drone flight over futuristic neon metropolis at dusk",
        output_mp4=out_mp4,
        duration_sec=3.0,
        width=1280,
        height=720,
        fps=24,
    )
    assert res["ok"] is True
    assert out_mp4.is_file()
    assert out_mp4.stat().st_size > 1024

    # ffprobe validation
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(out_mp4)],
            text=True,
        )
    )
    v_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
    a_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    assert len(v_streams) == 1
    assert len(a_streams) == 1
    assert int(v_streams[0]["width"]) == 1280
    assert int(v_streams[0]["height"]) == 720
    assert float(probe["format"]["duration"]) >= 2.5


def test_shot_generation_service_with_huggingface_engine(tmp_path: Path):
    """Verify shot generation routing when requesting huggingface engine."""
    out_mp4 = tmp_path / "shot_hf.mp4"
    scene = {
        "id": "sc_hf_01",
        "description": "Astronaut standing on the crimson dunes of Mars looking toward twin moons",
        "duration_sec": 3.0,
        "huggingface_model": "Wan-AI/Wan2.2-TI2V-5B",
    }
    shot = generate_shot_for_scene(
        scene=scene,
        output_mp4=out_mp4,
        render_engine="huggingface",
        resolution="1280x720",
        fps=24,
    )
    assert shot["ok"] is True
    assert out_mp4.is_file()
    assert shot["source_type"] in ("huggingface_video", "huggingface_video_local")


def test_fastapi_huggingface_endpoints():
    """Verify FastAPI GET /api/models/huggingface and status endpoints."""
    client = TestClient(app)

    # 1. List models
    resp = client.get("/api/models/huggingface")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["count"] >= 7
    repos = [m["repo_id"] for m in data["models"]]
    for expected in EXPECTED_MODELS:
        assert expected in repos

    # 2. Get status for a specific model
    resp_status = client.get("/api/models/huggingface/VideoRebirthAI/hyperflow-h3-flash/status")
    assert resp_status.status_code == 200
    m_info = resp_status.json()["model"]
    assert m_info["repo_id"] == "VideoRebirthAI/hyperflow-h3-flash"
    assert m_info["name"] == "HyperFlow H3 Flash"

    # 3. Direct generation endpoint
    gen_resp = client.post(
        "/api/models/huggingface/generate",
        json={
            "model_key": "Comfy-Org/PAN2",
            "prompt": "Camera panning across cyberpunk high-tech laboratory",
            "duration_sec": 2.5,
        },
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["ok"] is True
    assert Path(gen_data["output"]).is_file()
