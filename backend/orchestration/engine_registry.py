"""Capability-based multi-engine visual, audio, and rendering registry."""

from __future__ import annotations

from typing import Any

from backend.config import detect_hardware, get_configured_credentials
from backend.integrations.openmontage_adapter import openmontage_adapter


def get_engine_catalog() -> dict[str, Any]:
    hw = detect_hardware()
    creds = get_configured_credentials()
    has_ffmpeg = hw.binaries.get("ffmpeg", False)
    has_node = hw.binaries.get("node", False)
    has_remotion = has_node and openmontage_adapter.is_available()

    rendering_engines = [
        {
            "id": "ffmpeg",
            "name": "FFmpeg Media & Procedural Motion Engine",
            "type": "local",
            "available": has_ffmpeg,
            "capabilities": [
                "video_assembly", "transitions", "color_grading", "audio_mixing",
                "subtitle_burn", "animated_graphics", "chapter_muxing", "4k_export",
            ],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "Hardware-accelerated via Apple VideoToolbox on M1." if hw.gpu_backend == "apple_silicon_mps" else "CPU/GPU encoding.",
        },
        {
            "id": "remotion",
            "name": "Remotion React Composition Engine",
            "type": "local",
            "available": has_remotion,
            "capabilities": ["react_compositions", "data_charts", "kinetic_typography", "word_captions", "explainer_scenes"],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "OpenMontage remotion-composer integration.",
        },
        {
            "id": "hyperframes",
            "name": "HyperFrames HTML/CSS/GSAP Motion Engine",
            "type": "local",
            "available": has_node,
            "capabilities": ["html_gsap_animation", "svg_character_acting", "ink_theater", "kinetic_typography", "motion_graphics"],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "Runs via Node 22+ / npx hyperframes + OpenMontage ink-theater.",
        },
        {
            "id": "threejs",
            "name": "Three.js WebGL 3D Scene Engine",
            "type": "local",
            "available": has_node and has_ffmpeg,
            "capabilities": ["3d_environments", "camera_movement", "3d_animation", "procedural_3d"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "Browser/headless WebGL 3D rendering + 3D perspective projection.",
        },
        {
            "id": "blender",
            "name": "Blender 3D Cycles/EEVEE",
            "type": "local",
            "available": hw.binaries.get("blender", False),
            "capabilities": ["3d_scenes", "character_rigging", "lighting", "physics"],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "Available" if hw.binaries.get("blender") else "Not installed on host.",
        },
        {
            "id": "manim",
            "name": "ManimCE Mathematical Animation",
            "type": "local",
            "available": hw.binaries.get("manim", False),
            "capabilities": ["math_animations", "equations", "scientific_diagrams"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "Available" if hw.binaries.get("manim") else "Not installed on host.",
        },
    ]

    video_providers = [
        {"id": "local_procedural_svg", "provider": "OpenMontage / FFmpeg Procedural", "model": "procedural-vector-v1", "available": has_ffmpeg, "local": True, "cost_per_unit_usd": 0.0},
        {"id": "google_veo", "provider": "Google Veo", "model": "veo-3", "available": creds.get("GOOGLE_API_KEY", False), "local": False, "cost_per_unit_usd": 0.40},
        {"id": "kling", "provider": "Kling AI", "model": "kling-v2", "available": creds.get("KLING_API_KEY", False) or creds.get("FAL_KEY", False), "local": False, "cost_per_unit_usd": 0.35},
        {"id": "runway", "provider": "Runway", "model": "gen4_turbo", "available": creds.get("RUNWAY_API_KEY", False), "local": False, "cost_per_unit_usd": 0.50},
        {"id": "seedance", "provider": "ByteDance Seedance", "model": "seedance-2.0", "available": creds.get("ARK_API_KEY", False) or creds.get("FAL_KEY", False), "local": False, "cost_per_unit_usd": 0.30},
        {"id": "minimax", "provider": "MiniMax Hailuo", "model": "video-01", "available": creds.get("FAL_KEY", False), "local": False, "cost_per_unit_usd": 0.25},
        {"id": "local_wan_hunyuan_ltx", "provider": "Local Diffusion (Wan / Hunyuan / LTX)", "model": "wan2.2-ti2v-5b", "available": False, "local": True, "cost_per_unit_usd": 0.0, "unavailability_reason": f"Requires >=16GB RAM/VRAM; host has {hw.ram_gb}GB RAM."},
    ]

    tts_providers = [
        {"id": "macos_say", "provider": "macOS Speech (say)", "available": hw.binaries.get("say", False) and has_ffmpeg, "local": True, "cost_per_unit_usd": 0.0},
        {"id": "piper", "provider": "Piper Local Neural TTS", "available": hw.binaries.get("piper", False), "local": True, "cost_per_unit_usd": 0.0},
        {"id": "openai_tts", "provider": "OpenAI TTS", "available": creds.get("OPENAI_API_KEY", False), "local": False, "cost_per_unit_usd": 0.015},
        {"id": "elevenlabs", "provider": "ElevenLabs", "available": creds.get("ELEVENLABS_API_KEY", False), "local": False, "cost_per_unit_usd": 0.05},
        {"id": "azure_speech", "provider": "Azure Speech", "available": creds.get("AZURE_SPEECH_KEY", False), "local": False, "cost_per_unit_usd": 0.02},
    ]

    return {
        "hardware": hw.to_dict(),
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
        return "ffmpeg", f"Requested engine '{preferred}' is unavailable on this host; using 'ffmpeg' fallback."

    if "3d" in lower or "three.js" in lower or "blender" in lower:
        if avail.get("blender"):
            return "blender", None
        if avail.get("threejs"):
            return "threejs", None
        return "ffmpeg", "Blender is not installed; using Three.js/FFmpeg perspective 3D rendering path."

    if "math" in lower or "equation" in lower or "manim" in lower:
        if avail.get("manim"):
            return "manim", None
        return "hyperframes" if avail.get("hyperframes") else "ffmpeg", "Manim is not installed; using HyperFrames/FFmpeg motion graphics."

    if category in ("animation",) or "cartoon" in lower or "anime" in lower or "character" in lower:
        if avail.get("hyperframes"):
            return "hyperframes", None
        return "ffmpeg", None

    if category in ("educational", "commercial") and ("chart" in lower or "saas" in lower or "motion graphics" in lower or "captions" in lower):
        if avail.get("remotion"):
            return "remotion", None
        return "ffmpeg", None

    return "ffmpeg", None
