"""Real Blender CLI / bpy 3D Scene & Animation Adapter (never fakes renders)."""

from __future__ import annotations

import colorsys
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def find_blender_binary() -> Path | None:
    env_path = os.environ.get("BLENDER_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    which = shutil.which("blender")
    return Path(which) if which else None


def get_blender_status() -> dict[str, Any]:
    b = find_blender_binary()
    if not b:
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "binary": None,
            "reason": "Blender binary not installed on host (install Blender 4.x or set BLENDER_PATH).",
        }
    return {"available": True, "status": "READY", "binary": str(b), "reason": None}


def render_blender_scene(
    scene: dict[str, Any],
    output_mp4: Path,
    work_dir: Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> dict[str, Any]:
    blender_bin = find_blender_binary()
    if not blender_bin:
        return {
            "ok": False,
            "status": "UNAVAILABLE",
            "engine": "blender",
            "reason": "Blender binary not installed on host.",
        }

    work_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = work_dir / "blender_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    duration = max(2.0, float(scene.get("duration_sec", 4.0) or 4.0))
    total_frames = max(24, int(duration * fps))
    title = str(scene.get("title", "3D Scene")).replace('"', "'")
    picture = str(scene.get("picture_prompt") or scene.get("visual_description") or title)
    hue = abs(hash(picture)) % 360
    # One subject color per shot, derived from the written picture, so scenes do not share one gold ball.
    r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 0.45, 0.85)

    bpy_script = work_dir / "scene_render.py"
    bpy_script.write_text(
        f'''import math
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in scene.render.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
scene.render.resolution_x = {width}
scene.render.resolution_y = {height}
scene.render.fps = {fps}
scene.frame_start = 1
scene.frame_end = {total_frames}
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = "{(frames_dir / 'frame_').as_posix()}"

# World environment
world = bpy.data.worlds.new("StudioWorld")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.02, 0.03, 0.06, 1.0)
    bg.inputs[1].default_value = 0.8

# Ground plane
bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, 0))
ground = bpy.context.active_object
mat_g = bpy.data.materials.new("GroundMat")
mat_g.use_nodes = True
bsdf_g = mat_g.node_tree.nodes.get("Principled BSDF")
if bsdf_g:
    bsdf_g.inputs["Base Color"].default_value = (0.08, 0.09, 0.12, 1.0)
    bsdf_g.inputs["Roughness"].default_value = 0.35
ground.data.materials.append(mat_g)

# Hero monolith / architectural centerpiece
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.2, location=(0, 0, 1.5))
hero = bpy.context.active_object
hero.name = "HeroSubject_{title[:20]}"
mat_h = bpy.data.materials.new("HeroMat")
mat_h.use_nodes = True
bsdf_h = mat_h.node_tree.nodes.get("Principled BSDF")
if bsdf_h:
    bsdf_h.inputs["Base Color"].default_value = ({r:.3f}, {g:.3f}, {b:.3f}, 1.0)
    bsdf_h.inputs["Metallic"].default_value = 0.85
    bsdf_h.inputs["Roughness"].default_value = 0.22
hero.data.materials.append(mat_h)

# Key & Rim Lights
bpy.ops.object.light_add(type='AREA', location=(4.5, -4.5, 5.5))
key = bpy.context.active_object
key.data.energy = 600
key.data.size = 3.0

bpy.ops.object.light_add(type='AREA', location=(-4.0, 4.0, 3.5))
rim = bpy.context.active_object
rim.data.energy = 320
rim.data.color = (0.35, 0.65, 1.0)

# Camera orbit animation
bpy.ops.object.camera_add(location=(0, -6.0, 2.2))
cam = bpy.context.active_object
scene.camera = cam
constraint = cam.constraints.new(type='TRACK_TO')
constraint.target = hero
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'

for f in (1, {total_frames}):
    t = (f - 1) / max(1, {total_frames} - 1)
    angle = -0.6 + 1.2 * t
    cam.location = (6.0 * math.sin(angle), -6.0 * math.cos(angle), 1.8 + 0.8 * t)
    cam.keyframe_insert(data_path="location", frame=f)

bpy.ops.render.render(animation=True)
''',
        encoding="utf-8",
    )

    try:
        proc = subprocess.run(
            [str(blender_bin), "-b", "-P", str(bpy_script)],
            capture_output=True,
            text=True,
            timeout=240,
        )
        if proc.returncode != 0:
            return {"ok": False, "status": "UNAVAILABLE", "engine": "blender", "reason": (proc.stderr or proc.stdout)[-400:]}
        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        ff = subprocess.run(
            [
                "ffmpeg", "-y", "-framerate", str(fps),
                "-i", str(frames_dir / "frame_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output_mp4),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if ff.returncode != 0 or not output_mp4.is_file():
            return {"ok": False, "status": "UNAVAILABLE", "engine": "blender", "reason": ff.stderr[-300:]}
        return {"ok": True, "status": "READY", "engine": "blender", "output": str(output_mp4)}
    except Exception as exc:
        return {"ok": False, "status": "UNAVAILABLE", "engine": "blender", "reason": str(exc)}
