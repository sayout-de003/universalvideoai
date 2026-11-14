"""Capability-based multi-engine visual, audio, and rendering registry."""

from __future__ import annotations

from typing import Any

from backend.config import OPENMONTAGE_DIR, detect_hardware, get_configured_credentials
from backend.integrations.antigravity_adapter import AntigravityAdapter
from backend.integrations.openmontage_adapter import openmontage_adapter


def _remotion_installed() -> bool:
    rc_dir = OPENMONTAGE_DIR / "remotion-composer"
    return (rc_dir / "node_modules" / ".bin" / "remotion").is_file() or (rc_dir / "node_modules" / "@remotion").is_dir()


def get_engine_catalog() -> dict[str, Any]:
    hw = detect_hardware()
    creds = get_configured_credentials()
    ag_caps = AntigravityAdapter().discover_capabilities()

    has_ffmpeg = hw.binaries.get("ffmpeg", False)
    has_node = hw.binaries.get("node", False)
    has_chromium = bool(hw.chromium_path)
    has_remotion = has_node and openmontage_adapter.is_available() and _remotion_installed()
    has_blender = hw.binaries.get("blender", False)
    has_manim = hw.binaries.get("manim", False)

    rendering_engines = [
        {
            "id": "ffmpeg",
            "name": "FFmpeg Media & Cinema Compositor",
            "type": "local",
            "available": has_ffmpeg,
            "status": "READY" if has_ffmpeg else "UNAVAILABLE",
            "capabilities": [
                "video_assembly", "transitions", "color_grading", "audio_mixing",
                "ken_burns_motion", "film_grain", "chapter_muxing", "4k_export",
            ],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "Hardware-accelerated via Apple VideoToolbox on M1." if hw.gpu_backend == "apple_silicon_mps" else "CPU/GPU encoding.",
        },
        {
            "id": "threejs",
            "name": "Three.js Headless WebGL 3D Engine",
            "type": "local",
            "available": has_chromium and has_ffmpeg,
            "status": "READY" if (has_chromium and has_ffmpeg) else "UNAVAILABLE",
            "capabilities": ["3d_environments", "camera_movement", "3d_animation", "webgl_lighting"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": f"Uses headless Chromium WebGL ({hw.chromium_path})." if has_chromium else "Requires Chromium/Chrome for real WebGL rendering.",
        },
        {
            "id": "remotion",
            "name": "Remotion React Composition Engine",
            "type": "local",
            "available": has_remotion,
            "status": "READY" if has_remotion else "UNAVAILABLE",
            "capabilities": ["react_compositions", "data_charts", "kinetic_typography", "word_captions", "explainer_scenes"],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "OpenMontage remotion-composer ready." if has_remotion else "remotion-composer node_modules not installed.",
        },
        {
            "id": "hyperframes",
            "name": "HyperFrames HTML/CSS/GSAP Motion Engine",
            "type": "local",
            "available": has_node and has_chromium and has_ffmpeg,
            "status": "READY" if (has_node and has_chromium and has_ffmpeg) else "UNAVAILABLE",
            "capabilities": ["html_gsap_animation", "svg_character_acting", "kinetic_typography", "motion_graphics"],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "HTML/CSS/GSAP headless capture via Chromium + FFmpeg." if has_chromium else "Requires Node.js + Chromium + FFmpeg.",
        },
        {
            "id": "blender",
            "name": "Blender 3D Cycles/EEVEE",
            "type": "local",
            "available": has_blender,
            "status": "READY" if has_blender else "UNAVAILABLE",
            "capabilities": ["3d_scenes", "character_rigging", "lighting", "physics"],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "Available" if has_blender else "Blender binary not installed on host.",
        },
        {
            "id": "manim",
            "name": "ManimCE Mathematical Animation",
            "type": "local",
            "available": has_manim,
            "status": "READY" if has_manim else "UNAVAILABLE",
            "capabilities": ["math_animations", "equations", "scientific_diagrams"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "Available" if has_manim else "Not installed on host.",
        },
    ]

    def _cloud_status(ready: bool) -> str:
        return "READY" if ready else "NOT_CONFIGURED"

    video_providers = [
        {
            "id": "archival_media",
            "provider": "Zero-Key Archival & Public Domain (Wikimedia / NASA / Openverse / LoC)",
            "model": "archival-kenburns-v1",
            "available": has_ffmpeg,
            "status": "READY" if has_ffmpeg else "UNAVAILABLE",
            "local": True,
            "cost_per_unit_usd": 0.0,
        },
        {
            "id": "google_veo",
            "provider": "Google Veo",
            "model": "veo-3",
            "available": creds.get("GOOGLE_API_KEY", False),
            "status": _cloud_status(creds.get("GOOGLE_API_KEY", False)),
            "local": False,
            "cost_per_unit_usd": 0.40,
        },
        {
            "id": "kling",
            "provider": "Kling AI",
            "model": "kling-v2",
            "available": creds.get("KLING_API_KEY", False) or creds.get("FAL_KEY", False),
            "status": _cloud_status(creds.get("KLING_API_KEY", False) or creds.get("FAL_KEY", False)),
            "local": False,
            "cost_per_unit_usd": 0.35,
        },
        {
            "id": "runway",
            "provider": "Runway",
            "model": "gen4_turbo",
            "available": creds.get("RUNWAY_API_KEY", False),
            "status": _cloud_status(creds.get("RUNWAY_API_KEY", False)),
            "local": False,
            "cost_per_unit_usd": 0.50,
        },
        {
            "id": "seedance",
            "provider": "ByteDance Seedance",
            "model": "seedance-2.0",
            "available": creds.get("ARK_API_KEY", False) or creds.get("FAL_KEY", False),
            "status": _cloud_status(creds.get("ARK_API_KEY", False) or creds.get("FAL_KEY", False)),
            "local": False,
            "cost_per_unit_usd": 0.30,
        },
        {
            "id": "minimax",
            "provider": "MiniMax Hailuo",
            "model": "video-01",
            "available": creds.get("FAL_KEY", False),
            "status": _cloud_status(creds.get("FAL_KEY", False)),
            "local": False,
            "cost_per_unit_usd": 0.25,
        },
        {
            "id": "local_wan_hunyuan_ltx",
            "provider": "Local Diffusion (Wan / Hunyuan / LTX)",
            "model": "wan2.2-ti2v-5b",
            "available": hw.local_diffusion_eligible,
            "status": "READY" if hw.local_diffusion_eligible else "CAPABILITY_UNSUPPORTED",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "unavailability_reason": None if hw.local_diffusion_eligible else f"Requires >=24GB RAM/VRAM & 40GB disk; host has {hw.ram_gb}GB RAM ({hw.execution_profile} profile).",
        },
    ]

    tts_providers = [
        {"id": "openai_tts", "provider": "OpenAI TTS", "available": creds.get("OPENAI_API_KEY", False), "status": _cloud_status(creds.get("OPENAI_API_KEY", False)), "local": False, "cost_per_unit_usd": 0.015},
        {"id": "elevenlabs", "provider": "ElevenLabs", "available": creds.get("ELEVENLABS_API_KEY", False), "status": _cloud_status(creds.get("ELEVENLABS_API_KEY", False)), "local": False, "cost_per_unit_usd": 0.05},
        {"id": "azure_speech", "provider": "Azure Speech", "available": creds.get("AZURE_SPEECH_KEY", False), "status": _cloud_status(creds.get("AZURE_SPEECH_KEY", False)), "local": False, "cost_per_unit_usd": 0.02},
        {"id": "piper", "provider": "Piper Local Neural TTS", "available": hw.binaries.get("piper", False), "status": "READY" if hw.binaries.get("piper", False) else "UNAVAILABLE", "local": True, "cost_per_unit_usd": 0.0},
        {"id": "macos_say", "provider": "macOS Speech (say) [Legacy Fallback]", "available": hw.binaries.get("say", False) and has_ffmpeg, "status": "READY" if (hw.binaries.get("say", False) and has_ffmpeg) else "UNAVAILABLE", "local": True, "cost_per_unit_usd": 0.0},
    ]

    return {
        "hardware": hw.to_dict(),
        "execution_profile": hw.execution_profile,
        "antigravity": ag_caps,
        "credentials_configured": creds,
        "rendering_engines": rendering_engines,
        "video_providers": video_providers,
        "tts_providers": tts_providers,
    }


def select_render_engine(category: str, prompt: str, preferred: str | None = None) -> tuple[str, str | None]:
    catalog = get_engine_catalog()
    avail = {e["id"]: e["available"] for e in catalog["rendering_engines"]}
    lower = prompt.lower()

    if preferred:
        if avail.get(preferred, False):
            return preferred, None
        return "ffmpeg", f"Requested engine '{preferred}' is unavailable on this host; using 'ffmpeg' archival/compositor path."

    if "3d" in lower or "three.js" in lower or "blender" in lower:
        if avail.get("blender"):
            return "blender", None
        if avail.get("threejs"):
            return "threejs", None
        return "ffmpeg", "Blender/Three.js WebGL unavailable; using FFmpeg archival/compositor path."

    if "math" in lower or "equation" in lower or "manim" in lower:
        if avail.get("manim"):
            return "manim", None
        return ("hyperframes" if avail.get("hyperframes") else "ffmpeg"), "Manim is not installed."

    if category in ("animation",) or "cartoon" in lower or "anime" in lower or "character" in lower:
        if avail.get("hyperframes"):
            return "hyperframes", None
        return "ffmpeg", None

    if category in ("educational", "commercial") and ("chart" in lower or "saas" in lower or "motion graphics" in lower or "captions" in lower):
        if avail.get("remotion"):
            return "remotion", None
        if avail.get("hyperframes"):
            return "hyperframes", None
        return "ffmpeg", None

    return "ffmpeg", None
