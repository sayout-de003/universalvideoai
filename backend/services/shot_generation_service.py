"""Multi-Tier Shot Generation & Cinema Compositor (Antigravity -> Cloud -> Local 3D/Motion -> Zero-Key Archival)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.config import get_configured_credentials
from backend.integrations.antigravity_adapter import AntigravityAdapter
from backend.integrations.blender_adapter import render_blender_scene
from backend.integrations.openmontage_adapter import openmontage_adapter
from backend.services.archival_media_service import fetch_archival_media_for_scene
from backend.services.hyperframes_renderer import render_hyperframes_scene
from backend.services.remotion_renderer import render_remotion_scene
from backend.services.threejs_renderer import render_threejs_scene

_MOTION_PRESETS = ("slow_push_in", "pan_left_to_right", "slow_pull_out", "pan_right_to_left")
_MOTION_ALIASES = (
    ("pull_out", "slow_pull_out"),
    ("pull back", "slow_pull_out"),
    ("crane", "slow_pull_out"),
    ("push", "slow_push_in"),
    ("dolly", "slow_push_in"),
    ("pan_right", "pan_right_to_left"),
    ("right_to_left", "pan_right_to_left"),
    ("pan", "pan_left_to_right"),
    ("track", "pan_left_to_right"),
    ("whip", "pan_left_to_right"),
    ("glide", "pan_left_to_right"),
)


def scene_picture_prompt(scene: dict[str, Any], project_topic: str = "") -> str:
    """The picture direction. Prefer the written shot over the scene title."""
    visual = (
        scene.get("generation_prompt")
        or scene.get("visual_description")
        or scene.get("visual_prompt")
        or ""
    ).strip()
    if visual.lower().startswith("scene ") and scene.get("visual_description"):
        visual = str(scene["visual_description"]).strip()
    body = visual or str(scene.get("title") or "Cinematic scene")
    topic = (project_topic or "").strip()
    if topic and topic.lower() not in body.lower():
        return f"{topic}. {body}"
    return body


def motion_for_scene(scene: dict[str, Any], scene_index: int) -> str:
    raw = f"{scene.get('camera_movement') or ''} {scene.get('visual_description') or ''}".lower()
    for needle, preset in _MOTION_ALIASES:
        if needle in raw:
            return preset
    return _MOTION_PRESETS[scene_index % len(_MOTION_PRESETS)]


def _aspect_from_size(width: int, height: int) -> str:
    if height > width * 1.2:
        return "9:16"
    if abs(width - height) <= max(width, height) * 0.08:
        return "1:1"
    return "16:9"


def _cloud_duration(tool_name: str, duration_sec: float) -> str | int:
    d = max(4, min(10, int(round(duration_sec))))
    if tool_name == "veo_video":
        return "8s" if d >= 6 else "4s"
    if tool_name == "kling_video":
        return "10" if d >= 8 else "5"
    if tool_name == "runway_video":
        return d
    return d


def _claim_tool_output(res: dict[str, Any], output_mp4: Path) -> bool:
    if output_mp4.is_file() and output_mp4.stat().st_size > 1024:
        return True
    candidates: list[str] = []
    artifacts = res.get("artifacts") or []
    if isinstance(artifacts, dict):
        candidates.extend(str(v) for v in artifacts.values())
    elif isinstance(artifacts, list):
        candidates.extend(str(v) for v in artifacts)
    meta = res.get("metadata") or {}
    if isinstance(meta, dict):
        for key in ("output", "output_path", "path"):
            if meta.get(key):
                candidates.append(str(meta[key]))
    for raw in candidates:
        src = Path(raw)
        if src.is_file() and src.stat().st_size > 1024:
            if src.resolve() != output_mp4.resolve():
                shutil.copy2(src, output_mp4)
            return output_mp4.is_file() and output_mp4.stat().st_size > 1024
    return False


def get_format_visual_policy(category: str) -> dict[str, Any]:
    cat = (category or "documentary").lower()
    if cat in ("documentary", "historical", "film", "cinema", "brand_film", "narrative"):
        return {
            "overlay_badge": False,
            "progress_bar": False,
            "narration_box": False,
            "film_grain": True,
            "vignette": True,
            "color_grade": "warm_cinema",
        }
    if cat in ("commercial", "product_demo", "advertisement"):
        return {
            "overlay_badge": False,
            "progress_bar": False,
            "narration_box": False,
            "film_grain": False,
            "vignette": False,
            "color_grade": "crisp_commercial",
        }
    return {
        "overlay_badge": False,
        "progress_bar": False,
        "narration_box": False,
        "film_grain": False,
        "vignette": False,
        "color_grade": "neutral_clean",
    }


def _build_ken_burns_filter(
    width: int,
    height: int,
    fps: int,
    total_frames: int,
    motion_preset: str,
    color_grade: str,
    film_grain: bool,
    vignette: bool,
) -> str:
    # Upscale first with Lanczos so zoompan subpixel interpolation is smooth
    up_w = max(width * 2, 2560)
    if motion_preset == "slow_pull_out":
        zp = f"zoompan=z='max(1.0,1.16-0.16*(on/{total_frames}))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
    elif motion_preset == "pan_left_to_right":
        zp = f"zoompan=z='1.12':x='(iw-iw/zoom)*(on/{total_frames})':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
    elif motion_preset == "pan_right_to_left":
        zp = f"zoompan=z='1.12':x='(iw-iw/zoom)*(1-on/{total_frames})':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
    else:  # slow_push_in
        zp = f"zoompan=z='min(1.16,1.0+0.16*(on/{total_frames}))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"

    chain = [
        f"scale={up_w}:-2:flags=lanczos",
        f"crop='min(iw,ih*{width}/{height})':'min(ih,iw*{height}/{width})'",
        zp,
        "setsar=1",
    ]
    if color_grade == "warm_cinema":
        chain.append("eq=contrast=1.06:saturation=0.92:brightness=-0.01")
    elif color_grade == "crisp_commercial":
        chain.append("eq=contrast=1.08:saturation=1.08")
    if vignette:
        chain.append("vignette=PI/5")
    if film_grain:
        chain.append("noise=alls=4:allf=t+u")
    chain.append("format=yuv420p")
    return ",".join(chain)


def ken_burns_image_to_mp4(
    image_path: Path,
    output_mp4: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    motion_preset: str = "slow_push_in",
    color_grade: str = "warm_cinema",
    film_grain: bool = True,
    vignette: bool = True,
) -> dict[str, Any]:
    total_frames = max(24, int(round(duration_sec * fps)))
    vf = _build_ken_burns_filter(width, height, fps, total_frames, motion_preset, color_grade, film_grain, vignette)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-f", "image2", "-i", str(image_path),
            "-vf", vf,
            "-t", f"{duration_sec:.3f}",
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-movflags", "+faststart",
            str(output_mp4),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0 or not output_mp4.is_file():
        # zoompan rejects some stills. A locked-off scale still uses the real photograph.
        plain = subprocess.run(
            [
                "ffmpeg", "-y", "-loop", "1", "-f", "image2", "-i", str(image_path),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,format=yuv420p",
                "-t", f"{duration_sec:.3f}", "-r", str(fps),
                "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                str(output_mp4),
            ],
            capture_output=True, text=True, timeout=120,
        )
        if plain.returncode != 0 or not output_mp4.is_file():
            return {"ok": False, "status": "UNAVAILABLE", "reason": (plain.stderr or proc.stderr)[-400:]}
    return {"ok": True, "status": "READY", "output": str(output_mp4)}


def _grade_filters(policy: dict[str, Any]) -> list[str]:
    chain: list[str] = []
    if policy.get("color_grade") == "warm_cinema":
        chain.append("eq=contrast=1.06:saturation=0.92:brightness=-0.01")
    elif policy.get("color_grade") == "crisp_commercial":
        chain.append("eq=contrast=1.08:saturation=1.08")
    if policy.get("vignette"):
        chain.append("vignette=PI/5")
    if policy.get("film_grain"):
        chain.append("noise=alls=4:allf=t+u")
    return chain


def _fit_user_or_archival_video(
    source: Path,
    output_mp4: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    grade = _grade_filters(policy)
    vf = ",".join([
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        "setsar=1",
        *grade,
        "format=yuv420p",
    ])
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(source),
            "-t", f"{duration_sec:.3f}",
            "-vf", vf,
            "-r", str(fps), "-an",
            "-c:v", "libx264", "-crf", "19",
            str(output_mp4),
        ],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0 or not output_mp4.is_file():
        return {"ok": False, "status": "UNAVAILABLE", "reason": (proc.stderr or "")[-300:]}
    return {"ok": True, "status": "READY", "output": str(output_mp4)}


def _try_cloud_video(
    scene: dict[str, Any],
    output_mp4: Path,
    duration_sec: float,
    prompt: str,
    aspect: str,
) -> dict[str, Any] | None:
    creds = get_configured_credentials()
    tool_candidates: list[tuple[str, str]] = []
    if creds.get("GOOGLE_API_KEY"):
        tool_candidates.append(("veo_video", "google_veo"))
    if creds.get("RUNWAY_API_KEY"):
        tool_candidates.append(("runway_video", "runway"))
    if creds.get("KLING_API_KEY") or creds.get("FAL_KEY"):
        tool_candidates.append(("kling_video", "kling"))
    if creds.get("ARK_API_KEY") or creds.get("FAL_KEY"):
        tool_candidates.append(("seedance_video", "seedance"))
    if not tool_candidates or not openmontage_adapter.is_available():
        return None

    errors: list[str] = []
    for tool_name, provider_id in tool_candidates:
        try:
            res = openmontage_adapter.execute_tool(
                tool_name,
                {
                    "prompt": prompt,
                    "duration": _cloud_duration(tool_name, duration_sec),
                    "aspect_ratio": aspect,
                    "output_path": str(output_mp4),
                    "operation": "text_to_video",
                },
            )
            if res.get("success") and _claim_tool_output(res, output_mp4):
                return {"ok": True, "status": "READY", "engine": provider_id, "source_type": "cloud_ai_video", "output": str(output_mp4)}
            errors.append(f"{provider_id}: {res.get('error') or 'no output'}")
        except Exception as exc:
            errors.append(f"{provider_id}: {exc}")
    return {"ok": False, "status": "UNAVAILABLE", "reason": "; ".join(errors)}


def _try_cloud_image_kenburns(
    scene: dict[str, Any],
    output_mp4: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    policy: dict[str, Any],
    motion_preset: str,
    prompt: str,
) -> dict[str, Any] | None:
    creds = get_configured_credentials()
    tool_candidates: list[str] = []
    if creds.get("GOOGLE_API_KEY"):
        tool_candidates.append("google_imagen")
    if creds.get("OPENAI_API_KEY"):
        tool_candidates.append("openai_image")
    if creds.get("FAL_KEY") or creds.get("FAL_AI_API_KEY"):
        tool_candidates.append("flux_image")
    if not tool_candidates or not openmontage_adapter.is_available():
        return None

    img_out = output_mp4.with_suffix(".png")
    for tool_name in tool_candidates:
        try:
            res = openmontage_adapter.execute_tool(tool_name, {"prompt": prompt, "output_path": str(img_out)})
            if res.get("success") and _claim_tool_output(res, img_out):
                kb = ken_burns_image_to_mp4(
                    img_out, output_mp4, duration_sec, width, height, fps,
                    motion_preset=motion_preset,
                    color_grade=policy["color_grade"],
                    film_grain=policy["film_grain"],
                    vignette=policy["vignette"],
                )
                if kb.get("ok"):
                    kb["engine"] = tool_name
                    kb["source_type"] = "cloud_ai_image_kenburns"
                    return kb
        except Exception:
            continue
    return None


def generate_shot_for_scene(
    scene: dict[str, Any],
    output_mp4: Path,
    category: str = "documentary",
    resolution: str = "1920x1080",
    fps: int = 30,
    render_engine: str = "ffmpeg",
    project_topic: str = "",
    scene_index: int = 0,
    excluded_sha256: set[str] | None = None,
    source_media: str | None = None,
) -> dict[str, Any]:
    """Generate a real cinematic shot using priority routing; never falls back to Pillow shapes."""
    width, height = (int(x) for x in resolution.split("x"))
    duration = max(2.0, float(scene.get("duration_sec", 4.0) or 4.0))
    policy = get_format_visual_policy(category)
    motion_preset = motion_for_scene(scene, scene_index)
    picture = scene_picture_prompt(scene, project_topic=project_topic)
    aspect = _aspect_from_size(width, height)
    scene = {**scene, "picture_prompt": picture, "camera_movement": scene.get("camera_movement") or motion_preset}
    ag = AntigravityAdapter()
    strategy = ag.route_shot_strategy(category, requested_engine=render_engine)
    attempts: list[dict[str, Any]] = []

    user_path = Path(source_media) if source_media else None
    if user_path and user_path.is_file():
        fitted = _fit_user_or_archival_video(user_path, output_mp4, duration, width, height, fps, policy)
        attempts.append({"tier": "user_footage", "status": fitted.get("status"), "reason": fitted.get("reason")})
        if fitted.get("ok"):
            fitted["engine"] = "ffmpeg_user_footage"
            fitted["source_type"] = "user_footage"
            fitted["picture_prompt"] = picture
            return fitted

    for tier in strategy:
        if tier == "cloud_video":
            res = _try_cloud_video(scene, output_mp4, duration, picture, aspect)
            if res:
                attempts.append({"tier": tier, "status": res.get("status"), "reason": res.get("reason")})
                if res.get("ok"):
                    return res

        elif tier == "blender":
            res = render_blender_scene(scene, output_mp4, output_mp4.parent / f"work_{scene.get('id', 'sc')}", width=width, height=height, fps=fps)
            attempts.append({"tier": tier, "status": res.get("status"), "reason": res.get("reason")})
            if res.get("ok"):
                res["source_type"] = "blender_3d"
                return res

        elif tier == "threejs":
            res = render_threejs_scene(scene, output_mp4, width=width, height=height, fps=min(fps, 24))
            attempts.append({"tier": tier, "status": res.get("status"), "reason": res.get("reason")})
            if res.get("ok"):
                res["source_type"] = "threejs_webgl"
                return res

        elif tier == "remotion":
            res = render_remotion_scene(scene, output_mp4, width=width, height=height, fps=fps)
            attempts.append({"tier": tier, "status": res.get("status"), "reason": res.get("reason")})
            if res.get("ok"):
                res["source_type"] = "remotion_react"
                return res

        elif tier == "hyperframes":
            res = render_hyperframes_scene(scene, output_mp4, category=category, width=width, height=height, fps=min(fps, 24))
            attempts.append({"tier": tier, "status": res.get("status"), "reason": res.get("reason")})
            if res.get("ok"):
                res["source_type"] = "hyperframes_html_css"
                return res

        elif tier == "cloud_image_kenburns":
            res = _try_cloud_image_kenburns(scene, output_mp4, duration, width, height, fps, policy, motion_preset, picture)
            if res:
                attempts.append({"tier": tier, "status": res.get("status"), "reason": res.get("reason")})
                if res.get("ok"):
                    return res

        elif tier == "archival_media":
            query = f"{project_topic} {picture}".strip()
            fallback_q = (project_topic or picture).strip()
            arch_dir = output_mp4.parent / "archival_assets"
            media = fetch_archival_media_for_scene(
                query=query,
                fallback_query=fallback_q,
                dest_dir=arch_dir,
                excluded_sha256=excluded_sha256,
            )
            attempts.append({"tier": tier, "status": media.get("status"), "reason": media.get("reason")})
            if media.get("ok"):
                local_media = Path(media["local_path"])
                if excluded_sha256 is not None and media.get("sha256"):
                    excluded_sha256.add(media["sha256"])
                if media.get("media_type") == "video":
                    fitted = _fit_user_or_archival_video(local_media, output_mp4, duration, width, height, fps, policy)
                    if fitted.get("ok"):
                        return {
                            "ok": True,
                            "status": "READY",
                            "engine": "ffmpeg_archival_video",
                            "source_type": "archival_video",
                            "picture_prompt": picture,
                            "provenance": media,
                            "output": str(output_mp4),
                        }
                else:
                    kb = ken_burns_image_to_mp4(
                        local_media, output_mp4, duration, width, height, fps,
                        motion_preset=motion_preset,
                        color_grade=policy["color_grade"],
                        film_grain=policy["film_grain"],
                        vignette=policy["vignette"],
                    )
                    if kb.get("ok"):
                        kb["engine"] = "ffmpeg_archival_kenburns"
                        kb["source_type"] = "archival_photography"
                        kb["motion_preset"] = motion_preset
                        kb["picture_prompt"] = picture
                        kb["provenance"] = media
                        return kb
                    attempts[-1]["reason"] = kb.get("reason")
                if media.get("media_type") == "video":
                    attempts[-1]["reason"] = fitted.get("reason")

    return {
        "ok": False,
        "status": "FAILED",
        "reason": "All real media/engine tiers failed (Pillow placeholder fallback is disabled).",
        "attempts": attempts,
    }
