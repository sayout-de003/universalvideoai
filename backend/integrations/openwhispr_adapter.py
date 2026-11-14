"""Adapter for OpenWhispr (MIT) cliBridge, local STT, and Voice-to-Action command parsing."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import requests

from backend.config import OPENWHISPR_DIR


class OpenWhisprAdapter:
    def __init__(self) -> None:
        raw_path = os.environ.get("OPENWHISPR_BRIDGE_JSON", "~/.openwhispr/cli-bridge.json")
        self.bridge_json_path = Path(raw_path).expanduser()

    def _read_bridge_config(self) -> dict[str, Any] | None:
        if not self.bridge_json_path.exists():
            return None
        try:
            data = json.loads(self.bridge_json_path.read_text(encoding="utf-8"))
            if "port" in data and "token" in data:
                return data
        except Exception:
            return None
        return None

    def get_status(self) -> dict[str, Any]:
        cfg = self._read_bridge_config()
        bridge_online = False
        models: list[Any] = []
        if cfg:
            base = f"http://127.0.0.1:{cfg['port']}"
            headers = {"Authorization": f"Bearer {cfg['token']}"}
            try:
                r = requests.get(f"{base}/v1/health", headers=headers, timeout=1.5)
                bridge_online = r.status_code == 200
                if bridge_online:
                    mr = requests.get(f"{base}/v1/transcribe/models", headers=headers, timeout=2.0)
                    if mr.status_code == 200:
                        models = mr.json().get("models", [])
            except Exception:
                bridge_online = False

        local_whisper = shutil.which("whisper-cpp") is not None or shutil.which("whisper") is not None
        return {
            "repo_present": (OPENWHISPR_DIR / "package.json").exists(),
            "bridge_config_found": cfg is not None,
            "bridge_online": bridge_online,
            "bridge_port": cfg.get("port") if cfg else None,
            "local_whisper_cli": local_whisper,
            "available_models": models,
            "privacy_mode": "local_first",
        }

    def transcribe_file(
        self,
        audio_path: str | Path,
        model: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        path = Path(audio_path).expanduser().resolve()
        if not path.exists():
            return {"success": False, "error": f"Audio file not found: {path}"}

        cfg = self._read_bridge_config()
        if cfg:
            base = f"http://127.0.0.1:{cfg['port']}"
            headers = {"Authorization": f"Bearer {cfg['token']}"}
            payload: dict[str, Any] = {"path": str(path)}
            if model:
                payload["model"] = model
            if language:
                payload["language"] = language
            try:
                resp = requests.post(f"{base}/v1/transcribe", headers=headers, json=payload, timeout=120)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "provider": "openwhispr_bridge",
                        "text": data.get("text", ""),
                        "segments": data.get("segments", []),
                        "language": data.get("language", language or "en"),
                    }
            except Exception:
                pass

        if shutil.which("whisper-cpp"):
            try:
                out = subprocess.check_output(
                    ["whisper-cpp", "-f", str(path), "-nt"],
                    stderr=subprocess.STDOUT, text=True, timeout=120,
                )
                return {"success": True, "provider": "whisper-cpp", "text": out.strip(), "segments": []}
            except Exception as exc:
                return {"success": False, "error": f"whisper-cpp failed: {exc}"}

        if shutil.which("whisper"):
            try:
                out = subprocess.check_output(
                    ["whisper", str(path), "--output_format", "txt"],
                    stderr=subprocess.STDOUT, text=True, timeout=120,
                )
                return {"success": True, "provider": "whisper-cli", "text": out.strip(), "segments": []}
            except Exception as exc:
                return {"success": False, "error": f"whisper failed: {exc}"}

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if api_key:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
                with open(path, "rb") as f:
                    res = client.audio.transcriptions.create(model="whisper-1", file=f)
                return {"success": True, "provider": "openai_whisper", "text": res.text, "segments": []}
            except Exception as exc:
                return {"success": False, "error": f"OpenAI STT failed: {exc}"}

        return {
            "success": False,
            "error": "No active OpenWhispr bridge, local whisper-cpp CLI, or OPENAI_API_KEY found.",
        }

    @staticmethod
    def parse_voice_command(transcript: str) -> dict[str, Any]:
        text = transcript.strip()
        lower = text.lower()
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }

        def _extract_number(pattern: str) -> int | None:
            m = re.search(pattern, lower)
            if not m:
                return None
            tok = m.group(1)
            return int(tok) if tok.isdigit() else word_to_num.get(tok)

        if "regenerate" in lower and "scene" in lower:
            num = _extract_number(r"scene\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)")
            return {
                "intent": "regenerate_scene",
                "params": {"scene_number": num or 1},
                "requires_confirmation": True,
                "destructive": True,
                "summary": f"Regenerate scene {num or 1} (preserving manual edits in other scenes)",
            }

        if "export" in lower or "render final" in lower:
            res = "3840x2160" if "4k" in lower else "1920x1080"
            fmt = "mov" if "mov" in lower or "prores" in lower else "mp4"
            return {
                "intent": "export_video",
                "params": {"resolution": res, "format": fmt},
                "requires_confirmation": False,
                "destructive": False,
                "summary": f"Export final film as {fmt.upper()} ({res})",
            }

        if "subtitle" in lower or "caption" in lower:
            langs = []
            for lang_name, code in [
                ("hindi", "hi"), ("english", "en"), ("spanish", "es"),
                ("french", "fr"), ("german", "de"), ("japanese", "ja"),
            ]:
                if lang_name in lower:
                    langs.append(code)
            return {
                "intent": "generate_subtitles",
                "params": {"languages": langs or ["en"]},
                "requires_confirmation": False,
                "destructive": False,
                "summary": f"Generate subtitles in {', '.join(langs or ['en'])}",
            }

        if "music" in lower and ("quieter" in lower or "louder" in lower or "volume" in lower):
            delta = -0.25 if ("quieter" in lower or "lower" in lower or "softer" in lower) else 0.2
            return {
                "intent": "adjust_music_volume",
                "params": {"volume_delta": delta},
                "requires_confirmation": False,
                "destructive": False,
                "summary": f"Adjust background music volume by {delta:+.2f}",
            }

        if "narrator" in lower or "voice" in lower:
            return {
                "intent": "change_narrator_voice",
                "params": {"instruction": text},
                "requires_confirmation": True,
                "destructive": False,
                "summary": f"Update narrator voice direction: '{text}'",
            }

        if "extend" in lower and "chapter" in lower:
            chap = _extract_number(r"chapter\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)")
            mins = _extract_number(r"by\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+minute")
            return {
                "intent": "extend_chapter",
                "params": {"chapter_number": chap or 1, "extra_seconds": (mins or 1) * 60},
                "requires_confirmation": False,
                "destructive": False,
                "summary": f"Extend chapter {chap or 1} by {(mins or 1) * 60}s",
            }

        if "sound effect" in lower or "sfx" in lower:
            return {
                "intent": "add_sfx",
                "params": {"description": text},
                "requires_confirmation": False,
                "destructive": False,
                "summary": f"Add sound effect cue: '{text}'",
            }

        if any(k in lower for k in ("create a ", "make a ", "new video", "new documentary", "new film")):
            return {
                "intent": "create_project",
                "params": {"prompt": text},
                "requires_confirmation": False,
                "destructive": False,
                "summary": f"Create new production from voice brief: '{text}'",
            }

        return {
            "intent": "director_chat",
            "params": {"message": text},
            "requires_confirmation": False,
            "destructive": False,
            "summary": f"Send instruction to AI Director: '{text}'",
        }


openwhispr_adapter = OpenWhisprAdapter()
