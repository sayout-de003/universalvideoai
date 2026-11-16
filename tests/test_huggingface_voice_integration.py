"""Comprehensive tests for Hugging Face Voice Models integration.

Tests:
1. Zyphra/ZONOS3-Mini (Sparse MoE, 100M active params, 43 languages)
2. k2-fsa/OmniVoice (Massively multilingual, 600+ languages, RTF ~0.025)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.orchestration.audio_studio import generate_tts
from backend.orchestration.engine_registry import get_engine_catalog
from backend.services.huggingface_voice_service import (
    HUGGINGFACE_VOICE_MODELS,
    generate_speech_with_huggingface_voice,
    get_voice_model_spec,
    list_all_huggingface_voice_models,
)


def test_voice_catalog_has_zonos_and_omnivoice():
    """Verify voice models exist in the catalog with correct architecture details."""
    assert "zonos3-mini" in HUGGINGFACE_VOICE_MODELS
    assert "omnivoice" in HUGGINGFACE_VOICE_MODELS
    assert "drama-3" in HUGGINGFACE_VOICE_MODELS

    zonos = get_voice_model_spec("Zyphra/ZONOS3-Mini")
    assert zonos is not None
    assert zonos["repo_id"] == "Zyphra/ZONOS3-Mini"
    assert zonos["active_params_m"] == 100
    assert zonos["supported_languages_count"] == 43
    assert zonos["license"] == "Apache-2.0"

    omni = get_voice_model_spec("k2-fsa/OmniVoice")
    assert omni is not None
    assert omni["repo_id"] == "k2-fsa/OmniVoice"
    assert omni["supported_languages_count"] >= 600
    assert omni["license"] == "Apache-2.0"

    drama = get_voice_model_spec("fishaudio/drama-3")
    assert drama is not None
    assert drama["repo_id"] == "fishaudio/drama-3"
    assert drama["active_params_m"] == 3000
    assert drama["total_params_m"] == 35000
    assert drama["sample_rate_hz"] == 44100


def test_list_all_huggingface_voice_models():
    """Verify listing voice models returns valid hardware eligibility and specs."""
    models = list_all_huggingface_voice_models(fetch_live_stats=False)
    assert len(models) >= 3
    repos = [m["repo_id"] for m in models]
    assert "Zyphra/ZONOS3-Mini" in repos
    assert "k2-fsa/OmniVoice" in repos
    assert "fishaudio/drama-3" in repos


def test_engine_registry_contains_voice_models():
    """Verify voice models appear in tts_providers catalog."""
    catalog = get_engine_catalog()
    tts = catalog.get("tts_providers", [])
    tts_ids = [t.get("id") for t in tts]
    assert "hf_zonos3_mini" in tts_ids
    assert "hf_omnivoice" in tts_ids
    assert "hf_drama_3" in tts_ids


def test_generate_drama3_speech_and_ffprobe(tmp_path: Path):
    """Test generating voice with Fish Audio Drama 3 with dramatic delivery and validate with ffprobe."""
    out_wav = tmp_path / "drama_speech.wav"
    res = generate_speech_with_huggingface_voice(
        model_key_or_repo="fishaudio/drama-3",
        text="The signal from deep space was confirmed. We are not alone.",
        output_wav=out_wav,
        voice_id="narrator_deep",
        emotion="dramatic",
    )
    assert res["success"] is True
    assert out_wav.is_file()
    assert out_wav.stat().st_size > 512

    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(out_wav)],
            text=True,
        )
    )
    a_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    assert len(a_streams) == 1
    assert int(a_streams[0]["sample_rate"]) == 44100
    assert float(probe["format"]["duration"]) >= 1.0


def test_generate_zonos_speech_with_emotion_and_ffprobe(tmp_path: Path):
    """Test generating voice with Zonos with emotion tuning and validate with ffprobe."""
    out_wav = tmp_path / "zonos_speech.wav"
    res = generate_speech_with_huggingface_voice(
        model_key_or_repo="Zyphra/ZONOS3-Mini",
        text="Welcome to the universal AI production studio. Voice generation is active.",
        output_wav=out_wav,
        voice_id="narrator_warm",
        emotion="warm",
    )
    assert res["success"] is True
    assert out_wav.is_file()
    assert out_wav.stat().st_size > 512

    # Verify audio stream with ffprobe
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(out_wav)],
            text=True,
        )
    )
    a_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    assert len(a_streams) == 1
    assert int(a_streams[0]["sample_rate"]) == 44100
    assert float(probe["format"]["duration"]) >= 1.0


def test_generate_omnivoice_speech_and_ffprobe(tmp_path: Path):
    """Test generating voice with OmniVoice and validate with ffprobe."""
    out_wav = tmp_path / "omni_speech.wav"
    res = generate_speech_with_huggingface_voice(
        model_key_or_repo="k2-fsa/OmniVoice",
        text="OmniVoice supports over six hundred languages with high inference speed.",
        output_wav=out_wav,
        voice_id="character_1",
        speed=1.05,
    )
    assert res["success"] is True
    assert out_wav.is_file()
    assert out_wav.stat().st_size > 512

    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(out_wav)],
            text=True,
        )
    )
    a_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    assert len(a_streams) == 1
    assert int(a_streams[0]["sample_rate"]) == 24000
    assert float(probe["format"]["duration"]) >= 1.0


def test_audio_studio_generate_tts_dispatch(tmp_path: Path):
    """Verify audio studio generate_tts dispatches to Hugging Face voice model."""
    out_wav = tmp_path / "dispatch_zonos.wav"
    res = generate_tts(
        text="Testing audio studio dispatch to Zonos voice generator.",
        output_wav=out_wav,
        voice_id="zonos:narrator_warm",
    )
    assert res["success"] is True
    assert out_wav.is_file()
    assert "zonos" in res.get("provider", "").lower()

    out_drama = tmp_path / "dispatch_drama.wav"
    res_drama = generate_tts(
        text="Testing audio studio dispatch to Fish Audio Drama 3 model.",
        output_wav=out_drama,
        voice_id="drama:narrator_deep",
    )
    assert res_drama["success"] is True
    assert out_drama.is_file()
    assert "drama" in res_drama.get("provider", "").lower()


def test_fastapi_voice_endpoints():
    """Verify FastAPI GET /api/models/huggingface/voice and generation endpoints."""
    client = TestClient(app)

    # 1. List voice models
    resp = client.get("/api/models/huggingface/voice")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["count"] >= 3
    repos = [m["repo_id"] for m in data["models"]]
    assert "Zyphra/ZONOS3-Mini" in repos
    assert "k2-fsa/OmniVoice" in repos
    assert "fishaudio/drama-3" in repos

    # 2. Get status for Drama 3
    resp_status = client.get("/api/models/huggingface/voice/fishaudio/drama-3/status")
    assert resp_status.status_code == 200
    m_info = resp_status.json()["model"]
    assert m_info["repo_id"] == "fishaudio/drama-3"
    assert m_info["active_params_m"] == 3000

    # 3. Direct voice generation endpoint with Drama 3
    gen_resp = client.post(
        "/api/models/huggingface/voice/generate",
        json={
            "model_key": "fishaudio/drama-3",
            "text": "The curtains rise on an automated cinematic production.",
            "emotion": "dramatic",
        },
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["success"] is True
    assert Path(gen_data["path"]).is_file()
