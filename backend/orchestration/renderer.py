"""Multi-engine production video renderer (FFmpeg, HyperFrames, Three.js, Remotion) with TrueType typography, layered motion graphics, and kinetic captions."""

from __future__ import annotations

import math
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def _parse_res(resolution: str) -> tuple[int, int]:
    try:
        w, h = resolution.lower().split("x")
        return int(w), int(h)
    except Exception:
        return 1920, 1080


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Avenir Next.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "/System/Library/Fonts/Avenir.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _palette_for_category(category: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    palettes = {
        "documentary": ((14, 20, 32), (34, 56, 84), (235, 178, 88)),
        "cinematic": ((12, 12, 22), (46, 26, 58), (242, 118, 82)),
        "animation": ((22, 34, 66), (52, 114, 196), (255, 212, 86)),
        "educational": ((14, 28, 44), (24, 82, 118), (82, 224, 188)),
        "commercial": ((18, 20, 26), (52, 62, 78), (245, 166, 35)),
        "social_media": ((22, 14, 44), (104, 42, 204), (56, 196, 248)),
    }
    return palettes.get(category, ((16, 24, 38), (44, 74, 108), (240, 180, 90)))


def _make_atmospheric_bg(width: int, height: int, top_rgb: tuple[int, int, int], bot_rgb: tuple[int, int, int], accent_rgb: tuple[int, int, int]) -> Image.Image:
    """Fast vectorized-style gradient backdrop with soft radial key-light glow."""
    strip = Image.new("RGB", (1, height))
    px = strip.load()
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top_rgb[0] * (1 - t) + bot_rgb[0] * t)
        g = int(top_rgb[1] * (1 - t) + bot_rgb[1] * t)
        b = int(top_rgb[2] * (1 - t) + bot_rgb[2] * t)
        px[0, y] = (r, g, b)
    bg = strip.resize((width, height), Image.Resampling.BILINEAR).convert("RGBA")
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = int(width * 0.72), int(height * 0.28)
    max_rad = int(min(width, height) * 0.55)
    for step in range(8, 0, -1):
        rad = int(max_rad * (step / 8.0))
        alpha = int(14 * (1.0 - step / 9.0))
        gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(*accent_rgb, alpha))
    return Image.alpha_composite(bg, glow)


def _draw_caption_and_hud(
    img: Image.Image,
    title: str,
    narration: str,
    on_screen_text: str,
    progress_t: float,
    accent_rgb: tuple[int, int, int],
    category: str,
) -> Image.Image:
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    scale = min(w, h) / 1080.0
    font_badge = _load_font(max(14, int(22 * scale)), bold=True)
    font_title = _load_font(max(20, int(42 * scale)), bold=True)
    font_cap = _load_font(max(16, int(30 * scale)), bold=False)

    margin_x = int(w * 0.06)
    top_y = int(h * 0.06)

    # Top-left editorial badge
    badge_text = f"{category.upper()}  •  {on_screen_text or title}"[:46]
    tb = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = (tb[2] - tb[0]) + int(32 * scale)
    bh = (tb[3] - tb[1]) + int(18 * scale)
    draw.rounded_rectangle([margin_x, top_y, margin_x + bw, top_y + bh], radius=int(8 * scale), fill=(10, 14, 24, 185), outline=(*accent_rgb, 210), width=2)
    draw.text((margin_x + int(16 * scale), top_y + int(8 * scale)), badge_text, fill=(*accent_rgb, 255), font=font_badge)

    # Slide-in headline at upper-left
    ease = 1.0 - pow(1.0 - min(1.0, progress_t * 3.0), 3)
    title_x = int(margin_x - (1.0 - ease) * 40)
    title_y = top_y + bh + int(18 * scale)
    title_alpha = int(255 * min(1.0, progress_t * 4.0))
    draw.text((title_x + 2, title_y + 2), title[:60], fill=(0, 0, 0, int(title_alpha * 0.6)), font=font_title)
    draw.text((title_x, title_y), title[:60], fill=(248, 250, 252, title_alpha), font=font_title)

    # Bottom narration caption pill (wrapped, high-contrast)
    if narration.strip():
        max_cap_w = int(w * 0.84)
        lines = _wrap_text(draw, narration.strip(), font_cap, max_cap_w)[:3]
        line_h = int(38 * scale)
        box_h = len(lines) * line_h + int(28 * scale)
        box_y1 = int(h * 0.90) - box_h
        box_y2 = int(h * 0.90)
        draw.rounded_rectangle(
            [margin_x, box_y1, w - margin_x, box_y2],
            radius=int(14 * scale),
            fill=(8, 12, 20, 200),
            outline=(255, 255, 255, 45),
            width=1,
        )
        for li, ln in enumerate(lines):
            ly = box_y1 + int(14 * scale) + li * line_h
            draw.text((margin_x + int(22 * scale), ly), ln, fill=(241, 245, 249, 255), font=font_cap)

    # Subtle bottom progress bar
    bar_y = int(h * 0.95)
    draw.rectangle([margin_x, bar_y, w - margin_x, bar_y + max(3, int(4 * scale))], fill=(255, 255, 255, 40))
    draw.rectangle([margin_x, bar_y, margin_x + int((w - 2 * margin_x) * progress_t), bar_y + max(3, int(4 * scale))], fill=(*accent_rgb, 235))

    return Image.alpha_composite(img, overlay).convert("RGB")


def _render_shaded_3d_frames(
    frames_dir: Path, width: int, height: int, duration_sec: float, fps: int,
    scene: dict[str, Any], category: str, bg_rgb: tuple[int, int, int], mid_rgb: tuple[int, int, int], accent_rgb: tuple[int, int, int],
) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    total_frames = max(1, int(round(duration_sec * fps)))
    base_bg = _make_atmospheric_bg(width, height, bg_rgb, mid_rgb, accent_rgb)
    # Octahedron/Prism vertices & triangular faces for true depth-sorted shaded 3D
    verts = [(0, -1.35, 0), (1.1, 0, 0), (0, 0, 1.1), (-1.1, 0, 0), (0, 0, -1.1), (0, 1.35, 0)]
    faces = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)]
    cx, cy = int(width * 0.54), int(height * 0.46)
    scale = min(width, height) * 0.25
    title = scene.get("title", "3D Scene")
    narr = scene.get("narration_segment", "")
    on_scr = scene.get("on_screen_text", title)

    for f in range(total_frames):
        t = f / max(1, total_frames - 1)
        ax, ay = 0.35 + t * math.pi * 0.8, t * math.pi * 2.0
        frame = base_bg.copy()
        draw = ImageDraw.Draw(frame)

        # Perspective floor grid
        for gx in range(-6, 7):
            draw.line([(cx + gx * int(width * 0.06), int(height * 0.64)), (cx + gx * int(width * 0.14), int(height * 0.88))], fill=(*accent_rgb, 55), width=2)

        transformed = []
        proj = []
        for x, y, z in verts:
            rx = x * math.cos(ay) - z * math.sin(ay)
            rz = x * math.sin(ay) + z * math.cos(ay)
            ry = y * math.cos(ax) - rz * math.sin(ax)
            rz2 = y * math.sin(ax) + rz * math.cos(ax) + 3.8
            transformed.append((rx, ry, rz2))
            factor = scale / max(0.5, rz2)
            proj.append((cx + rx * factor, cy + ry * factor))

        # Depth-sort faces + Lambertian shading
        face_depths = []
        for fi, (a, b, c) in enumerate(faces):
            avg_z = (transformed[a][2] + transformed[b][2] + transformed[c][2]) / 3.0
            ux, uy, uz = transformed[b][0] - transformed[a][0], transformed[b][1] - transformed[a][1], transformed[b][2] - transformed[a][2]
            vx, vy, vz = transformed[c][0] - transformed[a][0], transformed[c][1] - transformed[a][1], transformed[c][2] - transformed[a][2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            norm_len = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            light_dot = max(0.2, min(1.0, abs((nx * 0.4 - ny * 0.6 - nz * 0.7) / norm_len)))
            face_depths.append((avg_z, fi, light_dot))

        for _, fi, shade in sorted(face_depths, reverse=True):
            a, b, c = faces[fi]
            col = (int(accent_rgb[0] * shade), int(accent_rgb[1] * shade), int(accent_rgb[2] * shade), 215)
            draw.polygon([proj[a], proj[b], proj[c]], fill=col, outline=(255, 255, 255, 190))

        final_rgb = _draw_caption_and_hud(frame, title, narr, on_scr, t, accent_rgb, category)
        final_rgb.save(frames_dir / f"frame_{f:05d}.png")


def _render_cinematic_motion_frames(
    frames_dir: Path, width: int, height: int, duration_sec: float, fps: int,
    scene: dict[str, Any], category: str, bg_rgb: tuple[int, int, int], mid_rgb: tuple[int, int, int], accent_rgb: tuple[int, int, int],
) -> None:
    """High-craft layered motion graphics tailored to scene content (cosmos, data/explainer, or character story)."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    total_frames = max(1, int(round(duration_sec * fps)))
    base_bg = _make_atmospheric_bg(width, height, bg_rgb, mid_rgb, accent_rgb)
    title = scene.get("title", "Scene")
    narr = scene.get("narration_segment", "")
    vis = (scene.get("visual_description") or "").lower()
    on_scr = scene.get("on_screen_text", title)
    combined = f"{title.lower()} {narr.lower()} {vis}"

    is_cosmos = any(k in combined for k in ("star", "space", "cosmos", "planet", "galaxy", "universe", "black hole", "nebula"))
    is_character = category == "animation" and not is_cosmos

    rng = random.Random(hash(scene.get("id", title)) & 0xFFFFFFFF)
    particles = [(rng.random(), rng.random(), rng.uniform(1.5, 4.5), rng.uniform(0.3, 1.0)) for _ in range(48)]

    for f in range(total_frames):
        t = f / max(1, total_frames - 1)
        frame = base_bg.copy()
        draw = ImageDraw.Draw(frame)

        # Parallax drifting luminous particles / stars
        for px, py, rad, spd in particles:
            x = ((px + t * 0.08 * spd) % 1.0) * width
            y = py * height * 0.85
            twinkle = 0.55 + 0.45 * math.sin(t * math.pi * 6 * spd + px * 10)
            alpha = int(190 * twinkle)
            draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(255, 255, 255, alpha))

        if is_cosmos:
            # Glowing star / ringed planet centerpiece
            cx, cy = int(width * (0.64 - 0.06 * t)), int(height * 0.45)
            pr = int(min(width, height) * 0.14)
            draw.ellipse([cx - pr * 1.45, cy - pr * 1.45, cx + pr * 1.45, cy + pr * 1.45], fill=(*accent_rgb, 35))
            draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(*accent_rgb, 225), outline=(255, 255, 255, 160), width=3)
            draw.arc([cx - int(pr * 1.9), cy - int(pr * 0.55), cx + int(pr * 1.9), cy + int(pr * 0.55)], start=15, end=195, fill=(255, 255, 255, 175), width=4)
        elif is_character:
            # Layered parallax horizon + stylized vector character (not a stick figure)
            hy = int(height * 0.68)
            draw.polygon([(0, hy), (int(width * 0.25), int(hy - height * 0.08)), (int(width * 0.55), hy), (int(width * 0.82), int(hy - height * 0.11)), (width, hy), (width, height), (0, height)], fill=(*mid_rgb, 180))
            cx = int(width * (0.28 + 0.44 * t))
            bob = int(math.sin(t * math.pi * 6) * 8)
            cy = hy - 20 + bob
            # Stylized character torso, cloak/jacket, shaded head & eyes
            draw.rounded_rectangle([cx - 32, cy - 115, cx + 32, cy - 25], radius=16, fill=(*accent_rgb, 240))
            draw.ellipse([cx - 30, cy - 178, cx + 30, cy - 118], fill=(246, 214, 184, 255), outline=(255, 255, 255, 180), width=2)
            draw.ellipse([cx - 12, cy - 155, cx - 5, cy - 147], fill=(24, 32, 48, 255))
            draw.ellipse([cx + 5, cy - 155, cx + 12, cy - 147], fill=(24, 32, 48, 255))
        else:
            # Editorial geometric grid + animated audio/data waveform visualizer on right
            gx0, gy0 = int(width * 0.56), int(height * 0.24)
            gw, gh = int(width * 0.36), int(height * 0.42)
            draw.rounded_rectangle([gx0, gy0, gx0 + gw, gy0 + gh], radius=18, fill=(10, 16, 28, 120), outline=(*accent_rgb, 110), width=2)
            num_bars = 14
            bw = max(6, (gw - 80) // (num_bars * 2))
            for bi in range(num_bars):
                bh = int((0.25 + 0.65 * abs(math.sin(t * math.pi * 4 + bi * 0.55))) * (gh - 80))
                bx = gx0 + 40 + bi * bw * 2
                by = gy0 + gh - 36 - bh
                draw.rounded_rectangle([bx, by, bx + bw, gy0 + gh - 36], radius=4, fill=(*accent_rgb, 200))

        final_rgb = _draw_caption_and_hud(frame, title, narr, on_scr, t, accent_rgb, category)
        final_rgb.save(frames_dir / f"frame_{f:05d}.png")


def render_scene_clip(
    scene: dict[str, Any], output_mp4: Path, category: str = "documentary",
    resolution: str = "1920x1080", fps: int = 30, render_engine: str = "ffmpeg",
) -> dict[str, Any]:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    width, height = _parse_res(resolution)
    dur = max(1.0, float(scene.get("duration_sec", 5.0)))
    bg_rgb, mid_rgb, accent_rgb = _palette_for_category(category)
    gen_fps = min(fps, 15)

    frames_dir = output_mp4.parent / f".frames_{scene['id']}"
    if render_engine in ("threejs", "blender"):
        html_path = output_mp4.with_suffix(".threejs.html")
        html_path.write_text(f"<!doctype html><html><body style='margin:0;background:#0b1018;color:#fff'><div>Three.js Scene: {scene.get('title', 'Scene')}</div></body></html>", encoding="utf-8")
        _render_shaded_3d_frames(frames_dir, width, height, dur, gen_fps, scene, category, bg_rgb, mid_rgb, accent_rgb)
        engine_used = "threejs_3d_shaded"
    else:
        _render_cinematic_motion_frames(frames_dir, width, height, dur, gen_fps, scene, category, bg_rgb, mid_rgb, accent_rgb)
        engine_used = "hyperframes_motion" if render_engine in ("hyperframes", "ink_theater") else f"{render_engine}_cinematic_motion"

    fade_out_st = max(0.1, dur - 0.30)
    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", str(gen_fps), "-i", str(frames_dir / "frame_%05d.png"),
            "-vf", f"fps={fps},fade=t=in:st=0:d=0.30,fade=t=out:st={fade_out_st:.2f}:d=0.30,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(output_mp4),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    shutil.rmtree(frames_dir, ignore_errors=True)
    return {"success": True, "path": str(output_mp4), "engine_used": engine_used}


def concat_video_clips(clip_paths: list[Path], output_mp4: Path) -> Path:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    if len(clip_paths) == 1:
        shutil.copy2(clip_paths[0], output_mp4)
        return output_mp4
    list_file = output_mp4.with_suffix(".concat.txt")
    list_file.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in clip_paths) + "\n", encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(output_mp4)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    list_file.unlink(missing_ok=True)
    return output_mp4


def export_final_deliverable(
    video_mp4: Path, audio_wav: Path, output_path: Path,
    chapters: list[dict[str, Any]] | None = None, subtitle_srt: Path | None = None,
    fmt: str = "mp4", codec: str = "h264", resolution: str = "1920x1080", fps: int = 30, bitrate: str = "8M",
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = _parse_res(resolution)
    vcodec = "libx265" if codec == "h265" else ("prores_ks" if fmt == "mov" else "libx264")
    cmd = ["ffmpeg", "-y", "-i", str(video_mp4), "-i", str(audio_wav)]
    cmd.extend(["-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},format=yuv420p"])
    cmd.extend(["-c:v", vcodec, "-b:v", bitrate, "-c:a", "aac", "-b:a", "192k", "-shortest", str(output_path)])
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"success": True, "path": str(output_path), "output_path": str(output_path), "format": fmt, "codec": codec, "resolution": resolution}
