"""Real Headless Blender 3D Character, Environment, Animation & Facial Rigging Engine."""

from __future__ import annotations

import colorsys
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.config import MEDIA_LIBRARY_DIR

_MAC_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
_DEFAULT_HUMANOID = MEDIA_LIBRARY_DIR / "characters" / "soldier_rigged.glb"


def find_blender_binary() -> Path | None:
    env_path = os.environ.get("BLENDER_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    which = shutil.which("blender")
    if which:
        return Path(which)
    if _MAC_BLENDER.is_file():
        return _MAC_BLENDER
    return None


def get_blender_status() -> dict[str, Any]:
    b = find_blender_binary()
    if not b:
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "binary": None,
            "reason": "Blender binary not installed on host (install Blender 4.x/5.x or set BLENDER_PATH).",
        }
    return {"available": True, "status": "READY", "binary": str(b), "reason": None}


def _detect_environment(scene: dict[str, Any]) -> str:
    explicit = str(scene.get("environment_type") or "").strip().lower()
    if explicit in ("room", "indoor", "outdoor"):
        return "room" if explicit in ("room", "indoor") else "outdoor"
    text = f"{scene.get('environment_ref') or ''} {scene.get('visual_description') or ''} {scene.get('title') or ''}".lower()
    if any(k in text for k in ("room", "office", "studio", "hall", "corridor", "lab", "indoor", "interior", "apartment")):
        return "room"
    return "outdoor"


def _detect_animation(scene: dict[str, Any]) -> str:
    explicit = str(scene.get("animation_name") or "").strip().lower()
    if explicit:
        return explicit
    text = f"{scene.get('visual_description') or ''} {scene.get('generation_prompt') or ''} {scene.get('title') or ''}".lower()
    if "run" in text or "sprint" in text:
        return "run"
    if "idle" in text or "stand" in text:
        return "idle"
    if "talk" in text or "speak" in text:
        return "talk"
    return "walk"


def _ffprobe_valid(mp4_path: Path) -> bool:
    if not mp4_path.is_file() or mp4_path.stat().st_size < 2048:
        return False
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,nb_frames", "-of", "json", str(mp4_path)],
            text=True,
            timeout=15,
        )
        data = json.loads(out)
        return len(data.get("streams", [])) > 0
    except Exception:
        return False


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
    total_frames = max(24, int(round(duration * fps)))
    env_type = _detect_environment(scene)
    anim_name = _detect_animation(scene)

    mesh_raw = scene.get("character_mesh_path")
    char_mesh = Path(mesh_raw) if mesh_raw else (_DEFAULT_HUMANOID if _DEFAULT_HUMANOID.is_file() else None)
    if char_mesh and not char_mesh.is_file():
        return {"ok": False, "status": "FAILED", "engine": "blender", "reason": f"Character mesh not found: {char_mesh}"}

    lip_sync_frames = scene.get("lip_sync_frames") or []
    lip_sync_json = work_dir / "lip_sync.json"
    lip_sync_json.write_text(json.dumps(lip_sync_frames), encoding="utf-8")

    picture = str(scene.get("picture_prompt") or scene.get("visual_description") or scene.get("title") or "3D Scene")
    hue = abs(hash(picture)) % 360
    r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 0.45, 0.85)
    char_posix = char_mesh.as_posix() if char_mesh else ""
    char_ext = char_mesh.suffix.lower() if char_mesh else ""

    bpy_script = work_dir / "scene_render.py"
    bpy_script.write_text(
        f'''import json
import math
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
engines = [e.identifier for e in scene.render.bl_rna.properties['engine'].enum_items]
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in engines else ('BLENDER_EEVEE' if 'BLENDER_EEVEE' in engines else 'CYCLES')
scene.render.resolution_x = {width}
scene.render.resolution_y = {height}
scene.render.fps = {fps}
scene.frame_start = 1
scene.frame_end = {total_frames}
scene.render.image_settings.file_format = 'PNG'
scene.render.use_file_extension = True
scene.render.filepath = "{(frames_dir / 'frame_').as_posix()}"

# World lighting
world = bpy.data.worlds.new("StudioWorld")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    if "{env_type}" == "room":
        bg.inputs[0].default_value = (0.04, 0.05, 0.07, 1.0)
        bg.inputs[1].default_value = 0.6
    else:
        bg.inputs[0].default_value = (0.16, 0.28, 0.48, 1.0)
        bg.inputs[1].default_value = 1.1

def make_mat(name, color, metallic=0.1, roughness=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return m

# Environment builder (room or outdoor)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"
ground.data.materials.append(make_mat("GroundMat", (0.14, 0.15, 0.17) if "{env_type}" == "room" else (0.12, 0.22, 0.11), roughness=0.75))

if "{env_type}" == "room":
    # Back wall, side wall, architectural pillars
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 4.5, 2.5))
    wall_back = bpy.context.active_object
    wall_back.scale = (14.0, 0.3, 5.0)
    wall_back.data.materials.append(make_mat("WallMat", (0.22, 0.24, 0.28), roughness=0.6))

    bpy.ops.mesh.primitive_cube_add(size=1, location=(-6.5, 0, 2.5))
    wall_left = bpy.context.active_object
    wall_left.scale = (0.3, 10.0, 5.0)
    wall_left.data.materials.append(make_mat("WallLeftMat", (0.19, 0.21, 0.25), roughness=0.6))

    for px in (-4.0, 4.0):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=5.0, location=(px, 3.8, 2.5))
        pil = bpy.context.active_object
        pil.data.materials.append(make_mat(f"Pillar_{{px}}", (0.35, 0.36, 0.40), metallic=0.3, roughness=0.35))
else:
    # Outdoor environmental markers (trees / monoliths along path)
    for idx, (tx, ty) in enumerate([(-3.5, 3.2), (3.5, 4.0), (-5.0, -1.5), (4.8, -2.0)]):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.18, depth=2.2, location=(tx, ty, 1.1))
        trunk = bpy.context.active_object
        trunk.data.materials.append(make_mat(f"Trunk_{{idx}}", (0.24, 0.15, 0.09), roughness=0.85))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.95, location=(tx, ty, 2.6))
        crown = bpy.context.active_object
        crown.data.materials.append(make_mat(f"Crown_{{idx}}", (0.11, 0.32, 0.13), roughness=0.7))

# Import rigged humanoid character
char_path = "{char_posix}"
char_ext = "{char_ext}"
imported_objs = []
if char_path:
    before = set(bpy.data.objects)
    if char_ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=char_path)
    elif char_ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=char_path)
    elif char_ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=char_path)
    imported_objs = [o for o in bpy.data.objects if o not in before]

armatures = [o for o in imported_objs if o.type == "ARMATURE"] or [o for o in bpy.data.objects if o.type == "ARMATURE"]
meshes = [o for o in imported_objs if o.type == "MESH"] or [o for o in bpy.data.objects if o.type == "MESH" and o.name != "Ground"]

# Create root empty so character faces camera and walks cleanly
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
char_root = bpy.context.active_object
char_root.name = "CharacterRoot"

if armatures:
    arm = armatures[0]
    arm.parent = char_root
elif meshes:
    for m in meshes:
        m.parent = char_root
else:
    # Fallback rigged primitive humanoid only if no mesh was supplied
    bpy.ops.mesh.primitive_capsule_add(radius=0.25, depth=1.5, location=(0, 0, 0.9))
    hero = bpy.context.active_object
    hero.data.materials.append(make_mat("FallbackChar", ({r:.3f}, {g:.3f}, {b:.3f}), roughness=0.4))
    hero.parent = char_root

# Load walk/idle/run action from imported actions if available
anim_target = "{anim_name}".lower()
if armatures:
    arm = armatures[0]
    if not arm.animation_data:
        arm.animation_data_create()
    chosen_action = None
    for act in bpy.data.actions:
        if anim_target in act.name.lower():
            chosen_action = act
            break
    if chosen_action is None and bpy.data.actions:
        chosen_action = bpy.data.actions[0]
    if chosen_action is not None:
        arm.animation_data.action = chosen_action

# Animate character translation across the set for walk/run
if anim_target in ("walk", "run"):
    dist = 2.6 if anim_target == "walk" else 4.2
    char_root.location = (0, -dist * 0.5, 0)
    char_root.keyframe_insert(data_path="location", frame=1)
    char_root.location = (0, dist * 0.5, 0)
    char_root.keyframe_insert(data_path="location", frame={total_frames})
    act = char_root.animation_data.action if char_root.animation_data else None
    if act and hasattr(act, "fcurves"):
        for fc in act.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Facial / lip-sync shape-key animation if lip_sync_frames provided
with open("{lip_sync_json.as_posix()}", "r", encoding="utf-8") as lf:
    lip_frames = json.load(lf)

if lip_frames and meshes:
    for m in meshes:
        if m.data.shape_keys and m.data.shape_keys.key_blocks:
            for kb in m.data.shape_keys.key_blocks:
                if any(k in kb.name.lower() for k in ("jaw", "mouth", "viseme", "open")):
                    for entry in lip_frames:
                        fr = max(1, min({total_frames}, int(entry.get("frame", 1))))
                        kb.value = float(entry.get("open", 0.0))
                        kb.keyframe_insert(data_path="value", frame=fr)

# 3-Point Studio Lighting
bpy.ops.object.light_add(type="AREA", location=(3.8, -3.5, 4.2))
key = bpy.context.active_object
key.data.energy = 750
key.data.size = 2.8

bpy.ops.object.light_add(type="AREA", location=(-3.5, -2.5, 2.8))
fill = bpy.context.active_object
fill.data.energy = 240
fill.data.color = (0.75, 0.85, 1.0)

bpy.ops.object.light_add(type="AREA", location=(0.0, 4.0, 3.6))
rim = bpy.context.active_object
rim.data.energy = 420
rim.data.color = (0.45, 0.72, 1.0)

# Camera tracking character
bpy.ops.object.camera_add(location=(2.6, -4.2, 1.65))
cam = bpy.context.active_object
scene.camera = cam
track = cam.constraints.new(type="TRACK_TO")
track.target = char_root
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"

cam.location = (2.6, -4.2, 1.65)
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (1.6, -3.6, 1.55)
cam.keyframe_insert(data_path="location", frame={total_frames})

bpy.ops.render.render(animation=True)
''',
        encoding="utf-8",
    )

    try:
        proc = subprocess.run(
            [str(blender_bin), "-b", "--python-exit-code", "1", "-P", str(bpy_script)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            return {"ok": False, "status": "FAILED", "engine": "blender", "reason": (proc.stderr or proc.stdout)[-500:]}
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
        if ff.returncode != 0 or not _ffprobe_valid(output_mp4):
            return {"ok": False, "status": "FAILED", "engine": "blender", "reason": ff.stderr[-300:]}
        return {
            "ok": True,
            "status": "READY",
            "engine": "blender",
            "output": str(output_mp4),
            "environment_type": env_type,
            "animation_name": anim_name,
            "character_mesh": str(char_mesh) if char_mesh else "procedural_fallback",
            "frames_rendered": total_frames,
        }
    except Exception as exc:
        return {"ok": False, "status": "FAILED", "engine": "blender", "reason": str(exc)}


def apply_animation_and_export(
    mesh_path: Path,
    output_glb: Path,
    animation_name: str = "walk",
) -> dict[str, Any]:
    """Bind an animation from the character's action library (or procedural walk) and export GLB."""
    src = Path(mesh_path)
    if not src.is_file():
        return {"ok": False, "reason": f"Mesh file not found: {src}"}
    blender_bin = find_blender_binary()
    if not blender_bin:
        return {"ok": False, "status": "UNAVAILABLE", "reason": "Blender binary not installed on host."}

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    script = output_glb.with_suffix(".anim.py")
    ext = src.suffix.lower()
    script.write_text(
        f'''import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
src = "{src.as_posix()}"
if "{ext}" in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=src)
elif "{ext}" == ".fbx":
    bpy.ops.import_scene.fbx(filepath=src)
elif "{ext}" == ".blend":
    bpy.ops.wm.open_mainfile(filepath=src)

arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
if arms:
    arm = arms[0]
    if not arm.animation_data:
        arm.animation_data_create()
    target = "{animation_name}".lower()
    for act in bpy.data.actions:
        if target in act.name.lower():
            arm.animation_data.action = act
            break

bpy.ops.export_scene.gltf(filepath="{output_glb.as_posix()}", export_format="GLB")
''',
        encoding="utf-8",
    )
    try:
        proc = subprocess.run([str(blender_bin), "-b", "-P", str(script)], capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not output_glb.is_file():
            return {"ok": False, "reason": (proc.stderr or proc.stdout)[-400:]}
        return {"ok": True, "output": str(output_glb), "animation_name": animation_name}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
    finally:
        script.unlink(missing_ok=True)
