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
        "supported_engines": ["blender", "threejs"],
        "default_engine": "blender",
        "asset_requirements": ["rigged_glb_models", "stylized_pbr_materials", "three_point_lighting"],
        "animation_techniques": ["skeletal_armature_actions", "tracked_3d_camera", "stylized_shading"],
        "render_settings": {"engine": "BLENDER_EEVEE_NEXT", "fps": 30},
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
    "whiteboard_handdraw": {
        "id": "whiteboard_handdraw",
        "label": "Whiteboard & Hand-Drawn Explainer",
        "description": "Deterministic SVG path drawing, animated sketches, Edge TTS narration, and whiteboard layout.",
        "supported_engines": ["handdraw", "remotion", "hyperframes", "ffmpeg"],
        "default_engine": "handdraw",
        "hyperframes_theme": "hand_drawn_storybook",
        "asset_requirements": ["path_svg_assets", "dsl_scene_timing"],
        "animation_techniques": ["stroke_draw_on", "pan_zoom_framing", "synchronized_narration"],
        "render_settings": {"fps": 30, "resolution": "1920x1080"},
        "qa_checks": ["stream_integrity", "svg_path_validity", "audio_alignment"],
    },
    "p5_brush_cartoon": {
        "id": "p5_brush_cartoon",
        "label": "Hand-Painted Cartoon (p5.brush)",
        "description": "Handmade animated cartoon using p5.js and p5.brush: flat wash colors, ink outlines, line boil, 31 character emotions.",
        "supported_engines": ["p5_brush", "hyperframes", "ffmpeg"],
        "default_engine": "p5_brush",
        "hyperframes_theme": "cartoon_2d",
        "asset_requirements": ["clawd_model_sheet", "p5_brush_library"],
        "animation_techniques": ["line_boil", "drawn_key_turns", "watercolor_wash_overlap"],
        "render_settings": {"fps": 12, "boil_hz": 12},
        "qa_checks": ["stream_integrity", "boil_cohesion", "character_acting"],
    },
    "claude_procedural_art": {
        "id": "claude_procedural_art",
        "label": "Procedural Art Illustration (83 Styles)",
        "description": "Procedural CPU drawing in 83 styles (ukiyo-e, watercolor, blueprint, stained glass, Art Deco) using numpy + Pillow.",
        "supported_engines": ["claude_drawing", "hyperframes", "ffmpeg"],
        "default_engine": "claude_drawing",
        "hyperframes_theme": "hand_drawn_storybook",
        "asset_requirements": ["style_slug", "aspect_dimensions"],
        "animation_techniques": ["procedural_stroke_generation", "draw_on_timelapse", "paper_texture_synthesis"],
        "render_settings": {"fps": 24, "quality": "lossless"},
        "qa_checks": ["stream_integrity", "palette_harmony", "resolution_match"],
    },
    "retro_paper_collage": {
        "id": "retro_paper_collage",
        "label": "Retro Paper Collage Motion",
        "description": "High-saturation paper grain backgrounds, monochrome halftone-dot cutouts, torn labels, and stop-motion jitter.",
        "supported_engines": ["hyperframes", "remotion", "ffmpeg"],
        "default_engine": "hyperframes",
        "hyperframes_theme": "pixel_art",
        "asset_requirements": ["halftone_cutout", "paper_grain_texture"],
        "animation_techniques": ["stop_motion_jitter", "layered_cutout_shift", "torn_label_entry"],
        "render_settings": {"fps": 12, "aspect_ratio": "9:16"},
        "qa_checks": ["stream_integrity", "halftone_texture", "label_legibility"],
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
    if any(k in combined for k in ("whiteboard", "handdraw", "sketch explainer")):
        return "whiteboard_handdraw"
    if any(k in combined for k in ("clawd", "p5.brush", "p5 brush", "hand-painted cartoon")):
        return "p5_brush_cartoon"
    if any(k in combined for k in ("claude drawing", "procedural art", "83 styles")):
        return "claude_procedural_art"
    if any(k in combined for k in ("retro collage", "paper collage", "halftone cutout")):
        return "retro_paper_collage"
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
        {
            "id": "handdraw",
            "name": "HandDraw SVG & Remotion Engine",
            "type": "local",
            "available": has_node and has_ffmpeg,
            "status": "READY" if (has_node and has_ffmpeg) else "UNAVAILABLE",
            "capabilities": ["svg_path_animation", "whiteboard_draw_on", "edge_tts_narration", "remotion_render"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "Remotion + SVG + Edge TTS hand-drawn animation pipeline.",
        },
        {
            "id": "p5_brush",
            "name": "p5.brush Hand-Painted Cartoon Engine (Clawd)",
            "type": "local",
            "available": has_node,
            "status": "READY" if has_node else "UNAVAILABLE",
            "capabilities": ["hand_painted_acting", "31_character_emotions", "line_boil", "headless_puppeteer"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "p5.js + p5.brush character animation with headless frame rendering.",
        },
        {
            "id": "claude_drawing",
            "name": "Claude Drawing Engine (83 Procedural Styles)",
            "type": "local",
            "available": True,
            "status": "READY",
            "capabilities": ["83_art_styles", "numpy_pillow_cpu", "draw_on_timelapse", "lossless_art_frames"],
            "max_resolution": "3840x2160",
            "cost_per_unit_usd": 0.0,
            "notes": "100% CPU procedural illustration in 83 styles with zero image models.",
        },
        {
            "id": "anidoodle",
            "name": "AniDoodle Procedural Art & Scored Film Engine",
            "type": "local",
            "available": has_node and has_chromium,
            "status": "READY" if (has_node and has_chromium) else "UNAVAILABLE",
            "capabilities": ["32_art_styles", "code_drawn_films", "web_audio_score", "deterministic_render"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "Deterministic code-drawn art and procedural scores.",
        },
        {
            "id": "javascript_animation",
            "name": "JavaScript Canvas Zero-Asset Film Engine",
            "type": "local",
            "available": has_node and has_chromium and has_ffmpeg,
            "status": "READY" if (has_node and has_chromium and has_ffmpeg) else "UNAVAILABLE",
            "capabilities": ["zero_asset_canvas", "code_synthesized_audio", "frame_accurate_mp4", "av_sync_check"],
            "max_resolution": "1920x1080",
            "cost_per_unit_usd": 0.0,
            "notes": "Single-file HTML5 canvas animation with code-synthesized audio.",
        },
        {
            "id": "huggingface",
            "name": "Hugging Face Open Video Diffusion & World Models",
            "type": "local",
            "available": True,
            "status": "READY",
            "capabilities": [
                "hyperflow_h3_flash", "wan2_2_ti2v_5b", "pan2_world_model",
                "wan2_2_t2v_a14b", "minimax_h3_turbo_lora", "dmad_adversarial",
                "wan2_1_t2v_1_3b", "joint_audio_video", "4_to_8_step_sampling",
            ],
            "max_resolution": "1280x720",
            "cost_per_unit_usd": 0.0,
            "notes": "Supports HyperFlow H3 Flash, Wan 2.2 5B/14B, PAN 2, MiniMax Turbo LoRA, DMAD, and Wan 2.1 1.3B.",
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
        # Hugging Face Integrated Video Models
        {
            "id": "huggingface",
            "provider": "Hugging Face Open-Source Diffusion",
            "model": "VideoRebirthAI/hyperflow-h3-flash",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "category": "ai_video_diffusion",
            "description": "Open-source text-to-video AI generation via Hugging Face Hub (HyperFlow H3, Wan 2.2, DMAD, MiniMax Turbo).",
        },
        {
            "id": "hf_hyperflow_h3_flash",
            "provider": "VideoRebirthAI / Hugging Face",
            "model": "VideoRebirthAI/hyperflow-h3-flash",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "category": "audio_video_t2v",
            "description": "14B parameter distilled MiniMax-H3 for joint 32kHz audio and video in 4-8 steps.",
        },
        {
            "id": "hf_wan2_2_ti2v_5b",
            "provider": "Wan-AI / Hugging Face",
            "model": "Wan-AI/Wan2.2-TI2V-5B",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "category": "text_to_video",
            "description": "5B Text-and-Image-to-Video diffusion transformer with 16x VAE.",
        },
        {
            "id": "hf_pan2",
            "provider": "Comfy-Org / IFM MBZUAI / Hugging Face",
            "model": "Comfy-Org/PAN2",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "category": "world_model_video",
            "description": "29B DiT World Model simulating scene dynamics and camera trajectories.",
        },
        {
            "id": "hf_wan2_2_t2v_a14b",
            "provider": "Wan-AI / Hugging Face",
            "model": "Wan-AI/Wan2.2-T2V-A14B",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "category": "text_to_video",
            "description": "14B MoE twin-expert video model for high cinematic quality.",
        },
        {
            "id": "hf_minimax_turbo_lora",
            "provider": "larryvrh / Hugging Face",
            "model": "larryvrh/MiniMax-H3-Turbo-Lora",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "category": "lora_accelerator",
            "description": "Turbo LoRA reducing MiniMax-H3 steps to 4-8 steps for 5x speedup.",
        },
        {
            "id": "hf_dmad",
            "provider": "ZhengmingYu / Hugging Face",
            "model": "ZhengmingYu/DMAD",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "category": "distilled_video",
            "description": "Multi-critic adversarial distillation for ultra-fast 4-step generation.",
        },
        {
            "id": "hf_wan2_1_t2v_1_3b",
            "provider": "Wan-AI / Hugging Face",
            "model": "Wan-AI/Wan2.1-T2V-1.3B",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "category": "text_to_video",
            "description": "1.3B lightweight diffusion model optimized for fast consumer GPU iteration.",
        },
    ]

    tts_providers = [
        {
            "id": "hf_zonos3_mini",
            "provider": "Zyphra / Hugging Face",
            "model": "Zyphra/ZONOS3-Mini",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "languages": 43,
            "description": "100M active parameter sparse MoE zero-shot voice cloning with fine-grained emotion control.",
        },
        {
            "id": "hf_omnivoice",
            "provider": "k2-fsa / Hugging Face",
            "model": "k2-fsa/OmniVoice",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "languages": 646,
            "description": "Massively multilingual zero-shot TTS and voice design supporting 600+ languages at RTF ~0.025.",
        },
        {
            "id": "hf_drama_3",
            "provider": "Fish Audio / Hugging Face",
            "model": "fishaudio/drama-3",
            "available": True,
            "status": "READY",
            "local": True,
            "cost_per_unit_usd": 0.0,
            "languages": 30,
            "description": "35B parameter MoE expressive dramatic speech model with 44.1kHz audio and multi-speaker dialogue acting.",
        },
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
        if preferred in ("huggingface", "hf") or preferred.startswith("hf_") or any(k in preferred.lower() for k in ("hyperflow", "wan", "pan2", "minimax", "dmad")):
            return preferred, None
        if avail.get(preferred, False):
            return preferred, None
        return "ffmpeg", f"Requested engine '{preferred}' is unavailable on this host; using 'ffmpeg' archival/compositor path."

    style_key = resolve_visual_style_profile(visual_style) if visual_style and visual_style != "auto" else None
    if style_key and style_key in VISUAL_STYLE_PROFILES:
        profile = VISUAL_STYLE_PROFILES[style_key]
        for engine_id in [profile["default_engine"], *profile.get("supported_engines", [])]:
            if avail.get(engine_id):
                return engine_id, None

    if ("whiteboard" in lower or "handdraw" in lower) and avail.get("handdraw"):
        return "handdraw", None
    if ("p5.brush" in lower or "p5 brush" in lower or "clawd" in lower) and avail.get("p5_brush"):
        return "p5_brush", None
    if ("claude drawing" in lower or "procedural style" in lower) and avail.get("claude_drawing"):
        return "claude_drawing", None
    if "anidoodle" in lower and avail.get("anidoodle"):
        return "anidoodle", None
    if ("javascript animation" in lower or "canvas animation" in lower) and avail.get("javascript_animation"):
        return "javascript_animation", None
    if ("libresprite" in lower or "sprite sheet" in lower) and avail.get("libresprite"):
        return "libresprite", None

    # SaaS product explainers and highly animated character scenes default to Hyperframes (rich 2D/3D Canvas)
    # unless Blender is explicitly requested via preferred engine or explicit prompt command.
    if ("saas" in lower or "explainer" in lower or "animated video" in lower or "scene by scene" in lower) and not ("blender" in lower):
        if avail.get("hyperframes"):
            return "hyperframes", None

    if "3d" in lower or "three.js" in lower or "blender" in lower:
        if avail.get("blender") and "three.js" not in lower and not any(k in lower for k in ("saas", "explainer", "2d", "cartoon", "canvas")):
            return "blender", None
        if avail.get("threejs"):
            return "threejs", None
        if avail.get("blender"):
            return "blender", None
        return "ffmpeg", "Blender/Three.js WebGL unavailable; using FFmpeg archival/compositor path."

    if "math" in lower or "equation" in lower or "manim" in lower:
        if avail.get("manim"):
            return "manim", None
        return ("hyperframes" if avail.get("hyperframes") else "ffmpeg"), "Manim is not installed."

    if category in ("animation",) or any(k in lower for k in ("cartoon", "anime", "character", "pixel", "cyberpunk", "storybook", "watercolor", "illustrated", "2d")):
        if avail.get("hyperframes"):
            return "hyperframes", None
        return "ffmpeg", None

    if category in ("educational", "commercial") and ("chart" in lower or "saas" in lower or "motion graphics" in lower or "captions" in lower):
        if avail.get("remotion"):
            return "remotion", None
        if avail.get("hyperframes"):
            return "hyperframes", None
        return "ffmpeg", None

    # Archival / Documentary formats specifically rely on archival footage and photography
    if category in ("documentary", "historical_documentaries", "investigative_documentaries", "user_footage_editing") and not any(k in lower for k in ("animated", "cartoon", "3d", "character", "anime", "code", "saas", "tech")):
        return "ffmpeg", None

    # Hugging Face AI diffusion cues
    if any(k in lower for k in ("diffusion", "huggingface", "hyperflow", "wan", "generative ai", "ai video", "t2v")):
        return "huggingface", None

    # For all creative, animated, cinematic, commercial, or storytelling videos, prioritize rich animated graphics
    if avail.get("hyperframes"):
        return "hyperframes", None
    if avail.get("remotion"):
        return "remotion", None
    if avail.get("blender"):
        return "blender", None

    return "ffmpeg", None
