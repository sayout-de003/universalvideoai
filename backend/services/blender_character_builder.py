"""Procedural Rigged 3D Cartoon Character & Office Break-Room Asset Builder (Blender 5.x)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from backend.config import MEDIA_LIBRARY_DIR
from backend.integrations.blender_adapter import find_blender_binary

CHARACTER_SPECS: dict[str, dict[str, Any]] = {
    "boss": {
        "name": "Boss",
        "filename": "boss_purple.blend",
        "skin_rgb": (0.42, 0.18, 0.72),
        "shirt_rgb": (0.92, 0.93, 0.96),
        "pants_rgb": (0.14, 0.15, 0.20),
        "scale": (1.08, 1.04, 1.06),
        "wardrobe": {"tie": "black", "shirt": "white_collar", "color": "purple"},
        "props": [],
        "expression": "serious",
    },
    "employee": {
        "name": "Employee",
        "filename": "employee_purple.blend",
        "skin_rgb": (0.50, 0.24, 0.80),
        "shirt_rgb": (0.82, 0.87, 0.94),
        "pants_rgb": (0.18, 0.20, 0.26),
        "scale": (0.98, 0.98, 1.00),
        "wardrobe": {"id_card": "blue", "shirt": "light_blue", "color": "purple"},
        "props": ["coffee_cup"],
        "expression": "shocked",
    },
    "friend": {
        "name": "Friend",
        "filename": "friend_purple.blend",
        "skin_rgb": (0.36, 0.16, 0.66),
        "shirt_rgb": (0.20, 0.24, 0.30),
        "pants_rgb": (0.12, 0.14, 0.18),
        "scale": (0.96, 0.96, 0.99),
        "wardrobe": {"headphones": "dark_cyan", "shirt": "casual_jacket", "color": "purple"},
        "props": ["headphones"],
        "expression": "sarcastic",
    },
}

BREAKROOM_BLEND = MEDIA_LIBRARY_DIR / "environments" / "office_breakroom.blend"


def get_character_blend_path(role_or_name: str) -> Path:
    low = (role_or_name or "").strip().lower()
    if "boss" in low:
        key = "boss"
    elif "employee" in low:
        key = "employee"
    elif "friend" in low:
        key = "friend"
    else:
        key = low
    spec = CHARACTER_SPECS.get(key)
    if not spec:
        return MEDIA_LIBRARY_DIR / "characters" / f"{key}.blend"
    return MEDIA_LIBRARY_DIR / "characters" / spec["filename"]


def ensure_office_cast_and_set(force_rebuild: bool = False) -> dict[str, Any]:
    """Build persistent rigged purple Boss/Employee/Friend .blend assets and break-room set if missing."""
    blender_bin = find_blender_binary()
    if not blender_bin:
        return {"ok": False, "reason": "Blender binary not installed on host."}

    chars_dir = MEDIA_LIBRARY_DIR / "characters"
    envs_dir = MEDIA_LIBRARY_DIR / "environments"
    chars_dir.mkdir(parents=True, exist_ok=True)
    envs_dir.mkdir(parents=True, exist_ok=True)

    built: list[str] = []
    for role, spec in CHARACTER_SPECS.items():
        target = chars_dir / spec["filename"]
        if force_rebuild or not target.is_file() or target.stat().st_size < 4096:
            res = _build_character_blend(blender_bin, role, spec, target)
            if not res.get("ok"):
                return res
            built.append(str(target))

    if force_rebuild or not BREAKROOM_BLEND.is_file() or BREAKROOM_BLEND.stat().st_size < 4096:
        res = _build_breakroom_blend(blender_bin, BREAKROOM_BLEND)
        if not res.get("ok"):
            return res
        built.append(str(BREAKROOM_BLEND))

    return {
        "ok": True,
        "built": built,
        "characters": {k: str(chars_dir / v["filename"]) for k, v in CHARACTER_SPECS.items()},
        "environment": str(BREAKROOM_BLEND),
    }


def _build_character_blend(blender_bin: Path, role: str, spec: dict[str, Any], output_blend: Path) -> dict[str, Any]:
    script_path = output_blend.with_suffix(".build.py")
    sr, sg, sb = spec["skin_rgb"]
    shr, shg, shb = spec["shirt_rgb"]
    pr, pg, pb = spec["pants_rgb"]
    sx, sy, sz = spec["scale"]
    char_name = spec["name"]

    script = f'''import math
import bpy
import bmesh

bpy.ops.wm.read_factory_settings(use_empty=True)

def make_mat(name, color, roughness=0.45, metallic=0.05):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return m

skin_mat = make_mat("{char_name}_Skin", ({sr}, {sg}, {sb}), roughness=0.42)
shirt_mat = make_mat("{char_name}_Shirt", ({shr}, {shg}, {shb}), roughness=0.55)
pants_mat = make_mat("{char_name}_Pants", ({pr}, {pg}, {pb}), roughness=0.65)
eye_white_mat = make_mat("{char_name}_EyeWhite", (0.98, 0.98, 0.99), roughness=0.15)
pupil_mat = make_mat("{char_name}_Pupil", (0.04, 0.04, 0.06), roughness=0.1)
mouth_mat = make_mat("{char_name}_MouthDark", (0.14, 0.03, 0.06), roughness=0.6)
brow_mat = make_mat("{char_name}_Brow", (0.12, 0.06, 0.22), roughness=0.5)

col = bpy.data.collections.new("{char_name}Collection")
bpy.context.scene.collection.children.link(col)

def link_obj(obj):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)

# Build Armature
bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
arm = bpy.context.active_object
arm.name = "{char_name}_Armature"
link_obj(arm)
eb = arm.data.edit_bones
for b in list(eb):
    eb.remove(b)

def add_bone(name, head, tail, parent=None):
    b = eb.new(name)
    b.head = head
    b.tail = tail
    if parent:
        b.parent = parent
    return b

b_root = add_bone("Root", (0, 0, 0), (0, 0, 0.2))
b_hips = add_bone("Hips", (0, 0, 0.78), (0, 0, 0.92), b_root)
b_spine = add_bone("Spine", (0, 0, 0.92), (0, 0, 1.15), b_hips)
b_chest = add_bone("Chest", (0, 0, 1.15), (0, 0, 1.38), b_spine)
b_neck = add_bone("Neck", (0, 0, 1.38), (0, 0, 1.48), b_chest)
b_head = add_bone("Head", (0, 0, 1.48), (0, 0, 1.78), b_neck)

b_uarm_l = add_bone("UpperArm.L", (0.20, 0, 1.34), (0.36, 0, 1.12), b_chest)
b_farm_l = add_bone("Forearm.L", (0.36, 0, 1.12), (0.38, -0.18, 0.96), b_uarm_l)
b_hand_l = add_bone("Hand.L", (0.38, -0.18, 0.96), (0.38, -0.26, 0.92), b_farm_l)

b_uarm_r = add_bone("UpperArm.R", (-0.20, 0, 1.34), (-0.36, 0, 1.12), b_chest)
b_farm_r = add_bone("Forearm.R", (-0.36, 0, 1.12), (-0.38, -0.18, 0.96), b_uarm_r)
b_hand_r = add_bone("Hand.R", (-0.38, -0.18, 0.96), (-0.38, -0.26, 0.92), b_farm_r)

b_thigh_l = add_bone("Thigh.L", (0.10, 0, 0.78), (0.10, 0, 0.42), b_hips)
b_shin_l = add_bone("Shin.L", (0.10, 0, 0.42), (0.10, 0, 0.06), b_thigh_l)
b_thigh_r = add_bone("Thigh.R", (-0.10, 0, 0.78), (-0.10, 0, 0.42), b_hips)
b_shin_r = add_bone("Shin.R", (-0.10, 0, 0.42), (-0.10, 0, 0.06), b_thigh_r)

bpy.ops.object.mode_set(mode="OBJECT")

def attach_to_bone(obj, bone_name):
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    # Reset local offset because parent_bone puts origin at bone tail
    bone = arm.data.bones[bone_name]
    obj.location = obj.location - bone.tail_local
    link_obj(obj)

# Torso (Chest)
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.22, location=(0, 0, 1.16))
torso = bpy.context.active_object
torso.name = "{char_name}_Torso"
torso.scale = (1.05 * {sx}, 0.78 * {sy}, 1.25 * {sz})
torso.data.materials.append(shirt_mat)
attach_to_bone(torso, "Chest")

# Hips / Pelvis
bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.19, location=(0, 0, 0.84))
hips = bpy.context.active_object
hips.name = "{char_name}_Hips"
hips.scale = (1.02 * {sx}, 0.80 * {sy}, 0.72 * {sz})
hips.data.materials.append(pants_mat)
attach_to_bone(hips, "Hips")

# Head (stylized cartoon proportions)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, radius=0.21, location=(0, 0, 1.62))
head = bpy.context.active_object
head.name = "{char_name}_Head"
head.scale = (0.95 * {sx}, 0.92 * {sy}, 1.05 * {sz})
head.data.materials.append(skin_mat)
attach_to_bone(head, "Head")

# Mouth (with Shape Keys for visemes & expressions)
bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.055, location=(0, -0.185, 1.54))
mouth = bpy.context.active_object
mouth.name = "{char_name}_Mouth"
mouth.scale = (1.35, 0.45, 0.25)
mouth.data.materials.append(mouth_mat)

# Add Shape Keys on Mouth
mouth.shape_key_add(name="Basis", from_mix=False)
def add_mouth_sk(sk_name, z_scale=1.0, x_scale=1.0, z_shift=0.0):
    sk = mouth.shape_key_add(name=sk_name, from_mix=False)
    for i, v in enumerate(mouth.data.vertices):
        co = v.co.copy()
        co.x *= x_scale
        co.z = co.z * z_scale + z_shift
        sk.data[i].co = co
    return sk

add_mouth_sk("jaw_open", z_scale=2.8, x_scale=0.95, z_shift=-0.01)
add_mouth_sk("viseme_AA", z_scale=3.2, x_scale=1.05, z_shift=-0.015)
add_mouth_sk("viseme_EE", z_scale=1.4, x_scale=1.35, z_shift=0.0)
add_mouth_sk("viseme_OO", z_scale=2.2, x_scale=0.65, z_shift=-0.005)
add_mouth_sk("viseme_FF", z_scale=0.8, x_scale=1.15, z_shift=0.005)
add_mouth_sk("viseme_MBP", z_scale=0.3, x_scale=1.05, z_shift=0.0)
add_mouth_sk("shocked", z_scale=3.8, x_scale=0.85, z_shift=-0.02)
add_mouth_sk("smirk", z_scale=1.1, x_scale=1.25, z_shift=0.01)
add_mouth_sk("serious", z_scale=0.5, x_scale=1.0, z_shift=-0.005)

attach_to_bone(mouth, "Head")

# Eyes & Brows (with blink shape key on eyelids)
for side, ex in (("L", 0.072), ("R", -0.072)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=0.042, location=(ex, -0.175, 1.64))
    eye = bpy.context.active_object
    eye.name = f"{char_name}_Eye_{{side}}"
    eye.scale = (0.9, 0.55, 1.1)
    eye.data.materials.append(eye_white_mat)
    attach_to_bone(eye, "Head")

    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.020, location=(ex, -0.194, 1.64))
    pupil = bpy.context.active_object
    pupil.name = f"{char_name}_Pupil_{{side}}"
    pupil.scale = (0.9, 0.5, 1.0)
    pupil.data.materials.append(pupil_mat)
    attach_to_bone(pupil, "Head")

    bpy.ops.mesh.primitive_cube_add(size=1, location=(ex, -0.185, 1.70))
    brow = bpy.context.active_object
    brow.name = f"{char_name}_Brow_{{side}}"
    brow.scale = (0.065, 0.022, 0.014)
    if "{role}" == "boss":
        brow.rotation_euler = (0, 0.22 if side == "L" else -0.22, 0)
    elif "{role}" == "friend":
        brow.rotation_euler = (0, -0.15 if side == "L" else 0.08, 0)
    brow.data.materials.append(brow_mat)
    attach_to_bone(brow, "Head")

# Arms & Hands
for side, sign in (("L", 1), ("R", -1)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.045, depth=0.26, location=(sign * 0.28, 0, 1.23))
    ua = bpy.context.active_object
    ua.name = f"{char_name}_UpperArm_{{side}}"
    ua.rotation_euler = (0, sign * 0.55, 0)
    ua.data.materials.append(shirt_mat)
    attach_to_bone(ua, f"UpperArm.{{side}}")

    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.038, depth=0.24, location=(sign * 0.37, -0.09, 1.04))
    fa = bpy.context.active_object
    fa.name = f"{char_name}_Forearm_{{side}}"
    fa.rotation_euler = (0.75, 0, 0)
    fa.data.materials.append(skin_mat)
    attach_to_bone(fa, f"Forearm.{{side}}")

    bpy.ops.mesh.primitive_uv_sphere_add(segments=14, ring_count=10, radius=0.052, location=(sign * 0.38, -0.22, 0.94))
    hd = bpy.context.active_object
    hd.name = f"{char_name}_Hand_{{side}}"
    hd.data.materials.append(skin_mat)
    attach_to_bone(hd, f"Hand.{{side}}")

# Legs
for side, sign in (("L", 1), ("R", -1)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.065, depth=0.38, location=(sign * 0.10, 0, 0.60))
    th = bpy.context.active_object
    th.name = f"{char_name}_Thigh_{{side}}"
    th.data.materials.append(pants_mat)
    attach_to_bone(th, f"Thigh.{{side}}")

    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.052, depth=0.38, location=(sign * 0.10, 0, 0.24))
    sh = bpy.context.active_object
    sh.name = f"{char_name}_Shin_{{side}}"
    sh.data.materials.append(pants_mat)
    attach_to_bone(sh, f"Shin.{{side}}")

# Role-Specific Wardrobe & Props
if "{role}" == "boss":
    tie_mat = make_mat("Boss_BlackTie", (0.04, 0.04, 0.05), roughness=0.35)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.175, 1.15))
    tie = bpy.context.active_object
    tie.name = "Boss_BlackTie"
    tie.scale = (0.045, 0.025, 0.28)
    tie.data.materials.append(tie_mat)
    attach_to_bone(tie, "Chest")

elif "{role}" == "employee":
    id_mat = make_mat("Employee_BlueID", (0.10, 0.45, 0.95), roughness=0.25)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.08, -0.178, 1.17))
    badge = bpy.context.active_object
    badge.name = "Employee_BlueIDCard"
    badge.scale = (0.065, 0.015, 0.09)
    badge.data.materials.append(id_mat)
    attach_to_bone(badge, "Chest")

    cup_mat = make_mat("Employee_CoffeeCup", (0.94, 0.94, 0.92), roughness=0.2)
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.045, depth=0.11, location=(-0.38, -0.24, 0.97))
    cup = bpy.context.active_object
    cup.name = "Employee_CoffeeCup"
    cup.data.materials.append(cup_mat)
    attach_to_bone(cup, "Hand.R")

    # Coffee spit droplet cluster (scaled to 0 by default, popped during coffee_spit beat)
    spit_mat = make_mat("CoffeeSpitMat", (0.28, 0.15, 0.06), roughness=0.15)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.045, location=(0, -0.28, 1.54))
    spit = bpy.context.active_object
    spit.name = "Employee_CoffeeSpit"
    spit.scale = (0.001, 0.001, 0.001)
    spit.data.materials.append(spit_mat)
    attach_to_bone(spit, "Head")

elif "{role}" == "friend":
    hp_mat = make_mat("Friend_Headphones", (0.08, 0.09, 0.12), roughness=0.3, metallic=0.4)
    hp_accent = make_mat("Friend_HeadphonesAccent", (0.15, 0.78, 0.85), roughness=0.25)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.22, minor_radius=0.02, location=(0, 0.0, 1.66))
    band = bpy.context.active_object
    band.name = "Friend_HeadphoneBand"
    band.rotation_euler = (math.radians(90), 0, math.radians(90))
    band.data.materials.append(hp_mat)
    attach_to_bone(band, "Head")
    for side, hx in (("L", 0.21), ("R", -0.21)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.06, depth=0.045, location=(hx, 0, 1.62))
        earcup = bpy.context.active_object
        earcup.name = f"Friend_EarCup_{{side}}"
        earcup.rotation_euler = (0, math.radians(90), 0)
        earcup.data.materials.append(hp_accent)
        attach_to_bone(earcup, "Head")

bpy.ops.wm.save_as_mainfile(filepath="{output_blend.as_posix()}")
'''
    script_path.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run(
            [str(blender_bin), "-b", "--python-exit-code", "1", "-P", str(script_path)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0 or not output_blend.is_file():
            return {"ok": False, "reason": f"Failed building {role}: {(proc.stderr or proc.stdout)[-400:]}"}
        return {"ok": True, "path": str(output_blend)}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
    finally:
        script_path.unlink(missing_ok=True)


def _build_breakroom_blend(blender_bin: Path, output_blend: Path) -> dict[str, Any]:
    script_path = output_blend.with_suffix(".build.py")
    script = f'''import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
col = bpy.data.collections.new("OfficeBreakRoom")
bpy.context.scene.collection.children.link(col)

def make_mat(name, color, roughness=0.5, metallic=0.05):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return m

def add_box(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.data.materials.append(mat)
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)
    return o

floor_mat = make_mat("BreakroomFloor", (0.28, 0.22, 0.17), roughness=0.65)
wall_mat = make_mat("BreakroomWall", (0.85, 0.84, 0.80), roughness=0.75)
accent_wall_mat = make_mat("BreakroomAccentWall", (0.24, 0.34, 0.45), roughness=0.65)
table_mat = make_mat("BreakroomTable", (0.45, 0.28, 0.16), roughness=0.35)
chair_mat = make_mat("BreakroomChair", (0.18, 0.20, 0.25), roughness=0.45)
counter_mat = make_mat("BreakroomCounter", (0.78, 0.78, 0.80), roughness=0.35)
mug_mat = make_mat("BreakroomMug", (0.95, 0.95, 0.95), roughness=0.2)

# Floor & Walls
add_box("Floor", (0, 0, -0.05), (12.0, 10.0, 0.1), floor_mat)
add_box("BackWall", (0, 3.6, 2.0), (12.0, 0.2, 4.2), wall_mat)
add_box("LeftWall", (-5.0, 0, 2.0), (0.2, 10.0, 4.2), accent_wall_mat)
add_box("RightWall", (5.0, 0, 2.0), (0.2, 10.0, 4.2), wall_mat)

# Coffee Counter in background
add_box("CoffeeCounter", (0, 2.8, 0.45), (3.4, 0.7, 0.9), counter_mat)
add_box("CoffeeMachine", (-0.8, 2.8, 1.10), (0.45, 0.40, 0.42), make_mat("EspressoMetal", (0.15, 0.16, 0.18), roughness=0.25, metallic=0.7))

# Central Break-Room Table
add_box("TableTop", (0, 0, 0.74), (2.2, 1.3, 0.07), table_mat)
for lx, ly in ((-0.95, -0.52), (0.95, -0.52), (-0.95, 0.52), (0.95, 0.52)):
    add_box(f"TableLeg_{{lx}}_{{ly}}", (lx, ly, 0.36), (0.08, 0.08, 0.72), make_mat("TableMetal", (0.16, 0.16, 0.18), metallic=0.6))

# Three Chairs around table (Left=Boss, Center-Back=Employee, Right=Friend)
for cname, cx, cy in (("BossChair", -1.25, 0.0), ("EmployeeChair", 0.0, 0.85), ("FriendChair", 1.25, 0.0)):
    add_box(f"{{cname}}_Seat", (cx, cy, 0.44), (0.48, 0.48, 0.06), chair_mat)
    add_box(f"{{cname}}_Leg", (cx, cy, 0.22), (0.08, 0.08, 0.44), make_mat("ChairMetal", (0.2, 0.2, 0.22), metallic=0.7))

# Extra coffee mugs on table
for mx, my in ((-0.45, -0.15), (0.05, 0.28), (0.48, -0.10)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=18, radius=0.045, depth=0.10, location=(mx, my, 0.82))
    mug = bpy.context.active_object
    mug.name = f"TableMug_{{mx}}"
    mug.data.materials.append(mug_mat)
    for c in list(mug.users_collection):
        c.objects.unlink(mug)
    col.objects.link(mug)

bpy.ops.wm.save_as_mainfile(filepath="{output_blend.as_posix()}")
'''
    script_path.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run(
            [str(blender_bin), "-b", "--python-exit-code", "1", "-P", str(script_path)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0 or not output_blend.is_file():
            return {"ok": False, "reason": f"Failed building breakroom: {(proc.stderr or proc.stdout)[-400:]}"}
        return {"ok": True, "path": str(output_blend)}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
    finally:
        script_path.unlink(missing_ok=True)
