"""Cinematic Scene Renderer, Concatenator, and Deliverable Exporter (zero Pillow placeholders)."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from backend.services.shot_generation_service import generate_shot_for_scene

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _parse_res(resolution: str) -> tuple[int, int]:
    try:
        w, h = resolution.lower().split("x")
        return max(320, int(w)), max(240, int(h))
    except Exception:
        return 1920, 1080


def render_scene_clip(
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
    """Render a real scene clip via Antigravity/Cloud/3D/Motion/Archival Media."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    res = generate_shot_for_scene(
        scene=scene,
        output_mp4=output_mp4,
        category=category,
        resolution=resolution,
        fps=fps,
        render_engine=render_engine,
        project_topic=project_topic,
        scene_index=scene_index,
        excluded_sha256=excluded_sha256,
        source_media=source_media,
    )
    if not res.get("ok") or not output_mp4.is_file():
        raise RuntimeError(f"Real shot generation failed for scene '{scene.get('id', 'unknown')}': {res.get('reason')} | attempts={res.get('attempts')}")

    return {
        "success": True,
        "path": str(output_mp4),
        "engine_used": res.get("engine", render_engine),
        "source_type": res.get("source_type", "unknown"),
        "provider": res.get("provider"),
        "model": res.get("model"),
        "job_id": res.get("job_id"),
        "estimated_cost_usd": res.get("estimated_cost_usd"),
        "generation_state": res.get("generation_state"),
        "provenance": res.get("provenance"),
        "motion_preset": res.get("motion_preset"),
    }


def _probe_duration(path: Path) -> float:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            text=True, timeout=15,
        ).strip()
        return max(0.0, float(out))
    except Exception:
        return 0.0


_XFADE_TRANSITIONS = ("smoothleft", "dissolve", "circleopen", "smoothright", "wipeleft")


def concat_video_clips(
    clip_paths: list[Path],
    output_mp4: Path,
    soften: bool = True,
    transitions: list[str] | None = None,
) -> Path:
    """Join shots with true FFmpeg xfade transitions while keeping exact cumulative duration via tpad."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    if not clip_paths:
        raise ValueError("No video clips provided for concatenation.")
    if len(clip_paths) == 1:
        shutil.copy2(clip_paths[0], output_mp4)
        return output_mp4

    durations = [_probe_duration(p) for p in clip_paths]
    trans_dur = 0.35
    can_xfade = soften and len(clip_paths) <= 18 and all(d > trans_dur * 2 + 0.3 for d in durations)
    if can_xfade:
        parts: list[str] = []
        n = len(clip_paths)
        for i in range(n):
            if i < n - 1:
                parts.append(
                    f"[{i}:v]fps=30,format=yuv420p,tpad=stop_mode=clone:stop_duration={trans_dur:.2f},setpts=PTS-STARTPTS[v{i}]"
                )
            else:
                parts.append(f"[{i}:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[v{i}]")

        cum_offset = 0.0
        prev_label = "[v0]"
        for i in range(1, n):
            cum_offset += durations[i - 1]
            t_name = (
                transitions[i]
                if transitions and i < len(transitions) and transitions[i] in _XFADE_TRANSITIONS
                else _XFADE_TRANSITIONS[(i - 1) % len(_XFADE_TRANSITIONS)]
            )
            out_label = "[v]" if i == n - 1 else f"[xf{i}]"
            parts.append(
                f"{prev_label}[v{i}]xfade=transition={t_name}:duration={trans_dur:.2f}:offset={cum_offset:.3f}{out_label}"
            )
            prev_label = out_label

        cmd = ["ffmpeg", "-y"]
        for p in clip_paths:
            cmd.extend(["-i", str(p)])
        cmd.extend([
            "-filter_complex", ";".join(parts),
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            str(output_mp4),
        ])
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and output_mp4.is_file():
            return output_mp4

    list_file = output_mp4.with_suffix(".concat.txt")
    list_file.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in clip_paths) + "\n", encoding="utf-8")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            str(output_mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    list_file.unlink(missing_ok=True)
    return output_mp4


def _parse_srt(srt_path: Path) -> list[tuple[float, float, str]]:
    text = srt_path.read_text(encoding="utf-8", errors="ignore")
    cues: list[tuple[float, float, str]] = []

    def _sec(stamp: str) -> float:
        h, m, rest = stamp.strip().split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2 or "-->" not in block:
            continue
        timing = next(ln for ln in lines if "-->" in ln)
        start_s, end_s = [p.strip() for p in timing.split("-->")]
        body = " ".join(ln for ln in lines if "-->" not in ln and not ln.isdigit())
        if body:
            cues.append((_sec(start_s), _sec(end_s.split()[0]), body))
    return cues


def _find_font() -> str | None:
    for cand in _FONT_CANDIDATES:
        if Path(cand).is_file():
            return cand
    return None


def burn_captions(video_mp4: Path, srt_path: Path, width: int, height: int) -> bool:
    """Burn the sidecar SRT into the picture. This ffmpeg build has no drawtext or libass."""
    cues = _parse_srt(srt_path)
    if not cues:
        return False
    font_path = _find_font()
    try:
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.truetype(font_path, max(28, height // 28)) if font_path else ImageFont.load_default()
    except Exception:
        return False

    duration = _probe_duration(video_mp4)
    if duration <= 0.2:
        return False
    spans: list[tuple[float, float, str]] = []
    cursor = 0.0
    for start, end, body in cues:
        start = max(cursor, start)
        end = max(start + 0.2, min(duration, end))
        if start > cursor + 0.05:
            spans.append((cursor, start, ""))
        spans.append((start, end, body))
        cursor = end
    if cursor < duration:
        spans.append((cursor, duration, ""))

    with tempfile.TemporaryDirectory(prefix="studio_caps_") as tmp:
        tmp_dir = Path(tmp)
        list_lines: list[str] = ["ffconcat version 1.0"]
        last_png: Path | None = None
        for i, (start, end, body) in enumerate(spans):
            png = tmp_dir / f"cap_{i:04d}.png"
            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            if body:
                draw = ImageDraw.Draw(img)
                wrapped = textwrap.fill(body, width=42)
                bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                x = max(24, (width - tw) / 2)
                y = height - th - max(36, height // 12)
                pad = 16
                draw.rounded_rectangle((x - pad, y - pad, x + tw + pad, y + th + pad), radius=12, fill=(8, 10, 16, 170))
                draw.multiline_text((x, y), wrapped, font=font, fill=(248, 250, 252, 255), align="center")
            img.save(png)
            list_lines.append(f"file '{png.as_posix()}'")
            list_lines.append(f"duration {max(0.05, end - start):.3f}")
            last_png = png
        if last_png is not None:
            list_lines.append(f"file '{last_png.as_posix()}'")
        list_file = tmp_dir / "caps.txt"
        list_file.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
        cap_mov = tmp_dir / "caps.mov"
        built = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c:v", "qtrle", str(cap_mov)],
            capture_output=True, text=True,
        )
        if built.returncode != 0 or not cap_mov.is_file():
            return False
        burned = video_mp4.with_name(video_mp4.stem + ".burned.mp4")
        over = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video_mp4), "-i", str(cap_mov),
                "-filter_complex", "[1:v]format=rgba[c];[0:v][c]overlay=0:0:eof_action=pass[v]",
                "-map", "[v]", "-map", "0:a?",
                "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                str(burned),
            ],
            capture_output=True, text=True,
        )
        if over.returncode != 0 or not burned.is_file():
            burned.unlink(missing_ok=True)
            return False
        burned.replace(video_mp4)
        return True


def export_final_deliverable(
    video_mp4: Path,
    audio_wav: Path,
    output_path: Path,
    chapters: list[dict[str, Any]] | None = None,
    subtitle_srt: Path | None = None,
    fmt: str = "mp4",
    codec: str = "h264",
    resolution: str = "1920x1080",
    fps: int = 30,
    bitrate: str = "8M",
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = _parse_res(resolution)
    vcodec = "libx265" if codec == "h265" else ("prores_ks" if fmt == "mov" else "libx264")
    cmd = ["ffmpeg", "-y", "-i", str(video_mp4), "-i", str(audio_wav)]
    cmd.extend([
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},format=yuv420p",
        "-c:v", vcodec, "-b:v", bitrate,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ])
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    captions_burned = False
    if subtitle_srt and Path(subtitle_srt).is_file():
        captions_burned = burn_captions(output_path, Path(subtitle_srt), width, height)
    return {
        "success": True,
        "path": str(output_path),
        "output_path": str(output_path),
        "format": fmt,
        "codec": codec,
        "resolution": resolution,
        "captions_burned": captions_burned,
    }
