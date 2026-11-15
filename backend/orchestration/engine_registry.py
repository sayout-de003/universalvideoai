"""Capability-based multi-engine visual, audio, style profile, and rendering registry."""

from __future__ import annotations

import os
from typing import Any

from backend.config import OPENMONTAGE_DIR, detect_hardware, get_configured_credentials
from backend.integrations.antigravity_adapter import AntigravityAdapter
from backend.integrations.openmontage_adapter import openmontage_adapter

VISUAL_STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "pixel_art": {
        "id": "pixel_art",
        "label": "Pixel Art",
        "description": "Sprite sheets, tile maps, character animation states, pixel-perfect scaling, and layered parallax.",
        "supported_engines": ["hyperframes", "libresprite", "remotion", "ffmpeg"],
        "default_engine": "hyperframes",
        "hyperframes_theme": "pixel_art",
        "asset_requirements": ["sprite_sheets", "tile_maps", "quantized_pixel_palette"],
        "animation_techniques": ["sprite_state_cycles", "pixel_perfect_integer_scaling", "layered_tilemap_parallax"],
        "render_settings": {"scaling_filter": "neighbor", "logical_resolution": "320x180", "fps": 24},
        "qa_checks": ["stream_integrity", "pixel_grid_sharpness", "palette_consistency"],
    },
    "2d_illustrated": {
        "id": "2d_illustrated",
        "label": "2D Illustrated",
        "description": "Layered illustrations, articulated character rigs, facial expression & lip-sync support, and camera pans/parallax.",
        "supported_engines": ["hyperframes", "remotion", "opentoonz", "ffmpeg"],
        "default_engine": "hyperframes",
        "hyperframes_theme": "2d_illustrated",
        "asset_requirements": ["layered_illustrations", "character_rig_joints", "viseme_mouth_shapes"],
        "animation_techniques": ["articulated_2d_rigging", "phoneme_lip_sync", "multi_layer_camera_pan"],
        "render_settings": {"fps": 24, "motion_blur": False},
        "qa_checks": ["stream_integrity", "lip_sync_alignment", "character_continuity"],
    },
    "3d_stylized": {
        "id": "3d_stylized",
        "label": "3D Stylized",
        "description": "Blender 3D scenes and reusable rigged models, stylized materials/lighting, and tracked camera animation.",
        "supported_engines": ["blender", "threejs", "hyperframes", "ffmpeg"],
        "default_engine": "blender",
        "hyperframes_theme": "pixar_character_world",
        "asset_requirements": ["rigged_glb_models", "stylized_pbr_materials", "three_point_lighting"],
        "animation_techniques": ["skeletal_armature_actions", "tracked_3d_camera", "stylized_shading"],
        "render_settings": {"engine": "BLENDER_EEVEE_NEXT", "fps": 24},
        "qa_checks": ["stream_integrity", "mesh_continuity_hash", "lighting_exposure"],
    },
    "hand_drawn_storybook": {
        "id": "hand_drawn_storybook",
        "label": "Hand-Drawn Storybook",
        "description": "Watercolor and pencil-style layers, multiplane camera movement, hand-drawn character motion, and storybook transitions.",
        "supported_engines": ["hyperframes", "lemo_opuscar", "remotion", "ffmpeg"],
        "default_engine": "hyperframes",
        "hyperframes_theme": "hand_drawn_storybook",
        "asset_requirements": ["watercolor_wash_layers", "pencil_ink_outlines", "paper_grain_overlay"],
        "animation_techniques": ["multiplane_camera_movement", "organic_line_boil", "watercolor_dissolve_transitions"],
        "render_settings": {"fps": 24, "color_grade": "warm_cinema", "vignette": True},
        "qa_checks": ["stream_integrity", "warm_storybook_palette", "transition_smoothness"],
    },
    "anime": {
        "id": "anime",
        "label": "Anime / Manga",
        "description": "Japanese animation style: cel-shaded characters, expressive anime eyes and hair, dynamic speed lines, and cinematic lighting.",
        "supported_engines": ["hyperframes", "remotion", "opentoonz", "ffmpeg"],
        "default_engine": "hyperframes",
        "hyperframes_theme": "anime",
        "asset_requirements": ["anime_character_sheet", "cel_shaded_layers", "speed_line_overlays"],
        "animation_techniques": ["cel_shading", "dynamic_camera_pan", "anime_blink_and_hair_flow", "speed_line_bursts"],
        "render_settings": {"fps": 24, "motion_blur": False, "palette": "vibrant_anime"},
        "qa_checks": ["stream_integrity", "character_continuity", "cel_shading_contrast"],
    },
    "cartoon_2d": {
        "id": "cartoon_2d",
        "label": "Classic 2D Cartoon",
        "description": "Classic 2D cartoon / western animation: bold ink contours, expressive cartoon features, squash & stretch character motion, and pop palettes.",
        "supported_engines": ["hyperframes", "remotion", "opentoonz", "ffmpeg"],
        "default_engine": "hyperframes",
        "hyperframes_theme": "cartoon_2d",
        "asset_requirements": ["cartoon_model_sheet", "ink_outline_layers", "comic_burst_accents"],
        "animation_techniques": ["squash_and_stretch", "bold_outline_character_motion", "comic_action_lines"],
        "render_settings": {"fps": 24, "motion_blur": False, "palette": "bold_cartoon"},
        "qa_checks": ["stream_integrity", "character_continuity", "ink_line_sharpness"],
    },
}


def resolve_visual_style_profile(style_or_prompt: str | None = None, fallback_prompt: str = "") -> str:
    """Resolve explicit visual style key or infer from natural-language prompt."""
    raw = (style_or_prompt or "").strip().lower()
    if raw in VISUAL_STYLE_PROFILES:
        return raw
    combined = f"{raw} {(fallback_prompt or '').strip().lower()}".strip()
    if not combined or combined == "auto":
        return "2d_illustrated"
    if any(k in combined for k in ("anime", "manga", "ghibli", "shonen", "shojo", "otaku", "japanese animation", "makoto shinkai", "kyoto animation")):
        return "anime"
    if any(k in combined for k in ("cartoon", "comic", "classic cartoon", "toon", "looney", "disney 2d", "western animation", "comic book")):
        return "cartoon_2d"
    if any(k in combined for k in ("pixel", "8-bit", "8bit", "16-bit", "16bit", "sprite", "retro game", "libresprite")):
        return "pixel_art"
    if any(k in combined for k in ("storybook", "watercolor", "hand-drawn", "hand_drawn", "hand drawn", "pencil", "sketch", "children's book", "illustrated book")):
        return "hand_drawn_storybook"
    if any(k in combined for k in ("3d", "blender", "stylized 3d", "3d_stylized", "cgi", "threejs", "rigged")):
        return "3d_stylized"
    if any(k in combined for k in ("2d", "illustrated", "2d_illustrated", "vector", "cutout", "opentoonz")):
        return "2d_illustrated"
    return "2d_illustrated"


def is_free_open_source_mode(mode: str | None = None) -> bool:
    """Return True when Zero Paid-Provider Execution Policy is active."""
    val = (mode or os.environ.get("STUDIO_MODE", "")).strip().lower()
    return val in ("free_open_source", "free", "open_source", "zero_paid", "foss")


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
    has_libresprite = hw.binaries.get("libresprite", False) or hw.binaries.get("aseprite", False)
    has_opentoonz = hw.binaries.get("opentoonz", False) or hw.binaries.get("tcomposer", False)

    rendering_engines = [
        {
            "id": "ffmpeg",
            "name": "FFmpeg Media & Cinema Compositor",
            "type": "local",
            "available": has_ffmpeg,
            "status": "READY" if has_ffmpeg else "UNAVAILABLE",
            "capabilities": [
                "video_assembly", "transitions", "color_grading", "audio_mixing",
                "ken_burns_motion", "film_grain", "chapter_muxing", "4k_export", "pixel_neighbor_scaling",
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
            "capabilities": ["react_compositions", "data_charts", "kinetic_typography", "word_captions", "explainer_scenes", "illustrated_parallax"],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "OpenMontage remotion-composer ready." if has_remotion else "remotion-composer node_modules not installed.",
        },
        {
            "id": "hyperframes",
            "name": "HyperFrames Multi-Style Animation Engine (Pixel / 2D / Storybook / Pixar)",
            "type": "local",
            "available": has_node and has_chromium and has_ffmpeg,
            "status": "READY" if (has_node and has_chromium and has_ffmpeg) else "UNAVAILABLE",
            "capabilities": [
                "html_gsap_animation", "svg_character_acting", "kinetic_typography",
                "motion_graphics", "pixel_art_sprites", "2d_illustrated_rig", "hand_drawn_storybook_multiplane",
            ],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "HTML5 Canvas/SVG headless capture via Chromium + FFmpeg." if has_chromium else "Requires Node.js + Chromium + FFmpeg.",
        },
        {
            "id": "blender",
            "name": "Blender 3D Cycles/EEVEE",
            "type": "local",
            "available": has_blender,
            "status": "READY" if has_blender else "UNAVAILABLE",
            "capabilities": ["3d_scenes", "character_rigging", "lighting", "physics", "3d_stylized", "procedural_environments"],
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
        {
            "id": "libresprite",
            "name": "LibreSprite / Sprite Pixel Renderer",
            "type": "local",
            "available": has_libresprite or (has_node and has_chromium and has_ffmpeg),
            "status": "READY" if (has_libresprite or (has_node and has_chromium and has_ffmpeg)) else "UNAVAILABLE",
            "capabilities": ["pixel_art", "sprite_sheets", "tile_maps", "integer_scaling"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "Native LibreSprite binary detected." if has_libresprite else "Uses deterministic Pixel-Art Canvas & FFmpeg nearest-neighbor sprite pipeline.",
        },
        {
            "id": "opentoonz",
            "name": "OpenToonz / 2D Rigged Animation Pipeline",
            "type": "local",
            "available": has_opentoonz or (has_node and has_chromium and has_ffmpeg),
            "status": "READY" if (has_opentoonz or (has_node and has_chromium and has_ffmpeg)) else "UNAVAILABLE",
            "capabilities": ["2d_character_animation", "xsh_scene_compositing", "lip_sync_rigs", "multiplane_2d"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "Native OpenToonz tcomposer detected." if has_opentoonz else "Uses deterministic 2D Illustrated Rig & Lip-Sync Canvas pipeline.",
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
        "visual_style_profiles": list(VISUAL_STYLE_PROFILES.values()),
        "video_providers": video_providers,
        "tts_providers": tts_providers,
    }


def select_render_engine(
    category: str,
    prompt: str,
    preferred: str | None = None,
    visual_style: str | None = None,
) -> tuple[str, str | None]:
    catalog = get_engine_catalog()
    avail = {e["id"]: e["available"] for e in catalog["rendering_engines"]}
    lower = f"{prompt} {visual_style or ''}".lower()

    if preferred:
        if avail.get(preferred, False):
            return preferred, None
        return "ffmpeg", f"Requested engine '{preferred}' is unavailable on this host; using 'ffmpeg' archival/compositor path."

    style_key = resolve_visual_style_profile(visual_style) if visual_style and visual_style != "auto" else None
    if style_key == "3d_stylized":
        if avail.get("blender"):
            return "blender", None
        if avail.get("threejs"):
            return "threejs", None
    if style_key in ("pixel_art", "2d_illustrated", "hand_drawn_storybook"):
        if avail.get("hyperframes"):
            return "hyperframes", None

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

    if category in ("animation",) or any(k in lower for k in ("cartoon", "anime", "character", "pixel", "storybook", "watercolor", "illustrated", "2d")):
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
