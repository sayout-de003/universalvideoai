"""Adapter for VoiceStudio (debpalash/voicestudio, AGPL-3.0): local-first TTS, voice cloning, dubbing, and SFX."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from backend.config import INTEGRATIONS_DIR

VOICESTUDIO_DIR = INTEGRATIONS_DIR / "voicestudio"


class VoiceStudioAdapter:
    def __init__(self) -> None:
        self.base_url = os.environ.get("VOICESTUDIO_URL", "http://127.0.0.1:8765").rstrip("/")

    def get_status(self) -> dict[str, Any]:
        repo_present = (VOICESTUDIO_DIR / "pyproject.toml").exists()
        online = False
        health_data: dict[str, Any] = {}
        try:
            r = requests.get(f"{self.base_url}/health", timeout=1.2)
            if r.status_code == 200:
                online = True
                health_data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        except Exception:
            online = False
        return {
            "repo_present": repo_present,
            "server_online": online,
            "base_url": self.base_url,
            "capabilities": ["voice_cloning", "voice_design", "video_dubbing", "tts_646_languages", "sfx_generation"],
            "health": health_data,
        }

    def synthesize_speech(
        self,
        text: str,
        output_wav: Path,
        voice: str = "alloy",
        model: str = "tts-1",
        speed: float = 1.0,
    ) -> dict[str, Any]:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        for endpoint in (f"{self.base_url}/v1/audio/speech", f"{self.base_url}/audio/speech"):
            try:
                r = requests.post(
                    endpoint,
                    json={"model": model, "input": text, "voice": voice, "response_format": "wav", "speed": speed},
                    timeout=45,
                )
                if r.status_code == 200 and len(r.content) > 256:
                    output_wav.write_bytes(r.content)
                    return {"success": True, "path": str(output_wav), "provider": "voicestudio", "license": "generated_voicestudio_local"}
            except Exception:
                continue
        return {"success": False, "error": "VoiceStudio server offline or unavailable"}

    def generate_sfx(self, prompt: str, output_wav: Path, duration_sec: float = 1.5) -> dict[str, Any]:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = requests.post(
                f"{self.base_url}/api/sfx/generate",
                json={"prompt": prompt, "duration": duration_sec},
                timeout=45,
            )
            if r.status_code == 200 and len(r.content) > 256:
                output_wav.write_bytes(r.content)
                return {"success": True, "path": str(output_wav), "provider": "voicestudio_sfx", "license": "generated_voicestudio_local"}
        except Exception:
            pass
        return {"success": False, "error": "VoiceStudio SFX endpoint unavailable"}


voicestudio_adapter = VoiceStudioAdapter()
