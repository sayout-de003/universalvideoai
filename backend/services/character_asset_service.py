"""3D Character Asset Management, Mesh Validation, Auto-Rigging, Image-to-3D, and Continuity."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from backend.config import MEDIA_LIBRARY_DIR
from backend.db import get_conn, init_db, row_to_dict, rows_to_dicts
from backend.integrations.blender_adapter import find_blender_binary
from backend.integrations.openmontage_adapter import openmontage_adapter
from backend.models import utc_now

DEFAULT_HUMANOID_GLB = MEDIA_LIBRARY_DIR / "characters" / "soldier_rigged.glb"

ANIMATION_LIBRARY: dict[str, dict[str, Any]] = {
    "walk": {"action_aliases": ["Walk", "walk", "Walking"], "loop": True, "speed_mps": 1.35},
    "idle": {"action_aliases": ["Idle", "idle", "Stand"], "loop": True, "speed_mps": 0.0},
    "run": {"action_aliases": ["Run", "run", "Running"], "loop": True, "speed_mps": 3.4},
    "talk": {"action_aliases": ["Talk", "Idle", "idle"], "loop": True, "speed_mps": 0.0, "gesture": "talk"},
    "wave": {"action_aliases": ["Wave", "Idle", "idle"], "loop": False, "speed_mps": 0.0, "gesture": "wave"},
}


def get_default_humanoid_asset() -> Path | None:
    if DEFAULT_HUMANOID_GLB.is_file() and DEFAULT_HUMANOID_GLB.stat().st_size > 1024:
        return DEFAULT_HUMANOID_GLB
    return None


def compute_continuity_hash(
    mesh_path: Path,
    wardrobe_spec: dict[str, Any] | None = None,
    voice_id: str = "default",
) -> str:
    h = hashlib.sha256()
    if mesh_path.is_file():
        h.update(mesh_path.read_bytes()[:65536])
        h.update(str(mesh_path.stat().st_size).encode("utf-8"))
    h.update(json.dumps(wardrobe_spec or {}, sort_keys=True).encode("utf-8"))
    h.update(voice_id.encode("utf-8"))
    return h.hexdigest()[:16]


def validate_and_cleanup_mesh(
    mesh_path: Path,
    output_path: Path | None = None,
    cleanup: bool = True,
) -> dict[str, Any]:
    """Inspect and optionally clean up a 3D mesh in headless Blender."""
    src = Path(mesh_path)
    if not src.is_file() or src.stat().st_size < 128:
        return {"ok": False, "reason": f"Mesh file missing or empty: {src}"}

    blender_bin = find_blender_binary()
    if not blender_bin:
        return {"ok": False, "status": "UNAVAILABLE", "reason": "Blender binary not installed on host."}

    ext = src.suffix.lower()
    if ext not in (".glb", ".gltf", ".fbx", ".obj", ".blend"):
        return {"ok": False, "reason": f"Unsupported 3D format: {ext}"}

    report_json = (output_path or src).with_suffix(".validation.json")
    out_target = Path(output_path) if output_path else None
    cleanup_flag = "True" if cleanup else "False"
    out_posix = out_target.as_posix() if out_target else ""

    script = f'''import json
import bpy
import bmesh

bpy.ops.wm.read_factory_settings(use_empty=True)
src = "{src.as_posix()}"
ext = "{ext}"
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=src)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=src)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=src)
elif ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=src)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
total_verts = 0
total_faces = 0
shape_keys = []
cleaned_verts_removed = 0

for obj in meshes:
    if {cleanup_flag}:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(obj.data)
        before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.update_edit_mesh(obj.data)
        cleaned_verts_removed += max(0, before - len(bm.verts))
        bpy.ops.object.mode_set(mode="OBJECT")
    total_verts += len(obj.data.vertices)
    total_faces += len(obj.data.polygons)
    if obj.data.shape_keys and obj.data.shape_keys.key_blocks:
        shape_keys.extend([kb.name for kb in obj.data.shape_keys.key_blocks if kb.name != "Basis"])

actions = [a.name for a in bpy.data.actions]
out_path = "{out_posix}"
if out_path:
    if out_path.lower().endswith((".glb", ".gltf")):
        bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB")
    elif out_path.lower().endswith(".blend"):
        bpy.ops.wm.save_as_mainfile(filepath=out_path)

with open("{report_json.as_posix()}", "w", encoding="utf-8") as f:
    json.dump({{
        "mesh_count": len(meshes),
        "armature_count": len(armatures),
        "vertex_count": total_verts,
        "face_count": total_faces,
        "cleaned_verts_removed": cleaned_verts_removed,
        "animations": actions,
        "shape_keys": sorted(set(shape_keys)),
    }}, f)
'''
    script_path = report_json.with_suffix(".inspect.py")
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run(
            [str(blender_bin), "-b", "--python-exit-code", "1", "-P", str(script_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0 or not report_json.is_file():
            return {"ok": False, "reason": (proc.stderr or proc.stdout)[-400:]}
        stats = json.loads(report_json.read_text(encoding="utf-8"))
        return {
            "ok": stats.get("mesh_count", 0) > 0 and stats.get("vertex_count", 0) > 0,
            "mesh_path": str(out_target if (out_target and out_target.is_file()) else src),
            **stats,
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
    finally:
        script_path.unlink(missing_ok=True)
        report_json.unlink(missing_ok=True)


def auto_rig_mesh(mesh_path: Path, output_glb: Path) -> dict[str, Any]:
    """Attach a basic humanoid armature with automatic weights to an unrigged mesh and export GLB."""
    src = Path(mesh_path)
    if not src.is_file():
        return {"ok": False, "reason": f"Mesh file not found: {src}"}
    blender_bin = find_blender_binary()
    if not blender_bin:
        return {"ok": False, "status": "UNAVAILABLE", "reason": "Blender binary not installed on host."}

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    script_path = output_glb.with_suffix(".autorig.py")
    ext = src.suffix.lower()
    script_path.write_text(
        f'''import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
src = "{src.as_posix()}"
ext = "{ext}"
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=src)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=src)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=src)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
if not meshes:
    raise RuntimeError("No mesh found to rig")

if not armatures:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    arm = bpy.context.active_object
    arm.name = "AutoHumanoidRig"
    eb = arm.data.edit_bones
    root = eb[0]
    root.name = "Pelvis"
    root.head = (0, 0, 0.9)
    root.tail = (0, 0, 1.05)

    spine = eb.new("Spine")
    spine.head = root.tail
    spine.tail = (0, 0, 1.45)
    spine.parent = root

    head = eb.new("Head")
    head.head = spine.tail
    head.tail = (0, 0, 1.75)
    head.parent = spine

    for side, sx in (("L", 1.0), ("R", -1.0)):
        arm_b = eb.new(f"Arm_{{side}}")
        arm_b.head = (0.18 * sx, 0, 1.4)
        arm_b.tail = (0.52 * sx, 0, 1.1)
        arm_b.parent = spine

        leg_b = eb.new(f"Leg_{{side}}")
        leg_b.head = (0.12 * sx, 0, 0.9)
        leg_b.tail = (0.12 * sx, 0, 0.05)
        leg_b.parent = root

    bpy.ops.object.mode_set(mode="OBJECT")
    for m in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        m.select_set(True)
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")

bpy.ops.export_scene.gltf(filepath="{output_glb.as_posix()}", export_format="GLB")
''',
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [str(blender_bin), "-b", "--python-exit-code", "1", "-P", str(script_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0 or not output_glb.is_file():
            return {"ok": False, "reason": (proc.stderr or proc.stdout)[-400:]}
        return {"ok": True, "output": str(output_glb), "rig_type": "humanoid_auto"}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
    finally:
        script_path.unlink(missing_ok=True)


def generate_character_3d_from_image(
    image_path: Path,
    output_glb: Path,
    prompt: str = "",
) -> dict[str, Any]:
    """Generate a textured 3D GLB from a character design reference image via OpenMontage fal_3d."""
    img = Path(image_path)
    if not img.is_file():
        return {"ok": False, "reason": f"Reference image not found: {img}"}
    if not openmontage_adapter.is_available():
        return {"ok": False, "status": "UNAVAILABLE", "reason": "OpenMontage tool registry unavailable."}
    res = openmontage_adapter.execute_tool(
        "fal_3d",
        {
            "operation": "image_to_3d",
            "image_path": str(img),
            "prompt": prompt,
            "output_path": str(output_glb),
            "enable_pbr": True,
            "export_textured_glb": True,
        },
    )
    if res.get("success") and output_glb.is_file() and output_glb.stat().st_size > 1024:
        return {"ok": True, "output": str(output_glb), "provider": "fal_3d"}
    return {"ok": False, "status": "UNAVAILABLE", "reason": str(res.get("error") or "image_to_3d failed")}


def register_character_asset(
    project_id: str,
    name: str,
    mesh_path: Path,
    character_id: str | None = None,
    reference_image_path: Path | None = None,
    wardrobe_spec: dict[str, Any] | None = None,
    voice_id: str = "default",
    license_name: str = "project_owned",
    validate: bool = True,
) -> dict[str, Any]:
    """Persist a 3D character asset record ONLY if the real mesh file exists and validates."""
    mesh = Path(mesh_path)
    if not mesh.is_file() or mesh.stat().st_size < 128:
        raise ValueError(f"Cannot register character asset without a real mesh file: {mesh}")

    if reference_image_path and not Path(reference_image_path).is_file():
        raise ValueError(f"Design reference image does not exist: {reference_image_path}")

    validation: dict[str, Any] = {"ok": True, "animations": [], "shape_keys": [], "armature_count": 0}
    if validate and find_blender_binary():
        validation = validate_and_cleanup_mesh(mesh, cleanup=False)
        if not validation.get("ok"):
            raise ValueError(f"Mesh validation failed for {mesh}: {validation.get('reason')}")

    init_db()
    asset_id = f"char3d_{uuid.uuid4().hex[:10]}"
    validation["voice_id"] = voice_id
    continuity_hash = compute_continuity_hash(mesh, wardrobe_spec=wardrobe_spec, voice_id=voice_id)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO character_3d_assets
               (id, project_id, character_id, name, mesh_path, reference_image_path, rig_type,
                has_armature, animations_json, shape_keys_json, wardrobe_spec_json,
                continuity_hash, license, validation_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                project_id,
                character_id,
                name,
                str(mesh.resolve()),
                str(Path(reference_image_path).resolve()) if reference_image_path else None,
                "humanoid",
                1 if validation.get("armature_count", 0) > 0 else 0,
                json.dumps(validation.get("animations", [])),
                json.dumps(validation.get("shape_keys", [])),
                json.dumps(wardrobe_spec or {}),
                continuity_hash,
                license_name,
                json.dumps(validation),
                utc_now(),
            ),
        )
        row = conn.execute("SELECT * FROM character_3d_assets WHERE id=?", (asset_id,)).fetchone()
    return row_to_dict(row) or {"id": asset_id, "mesh_path": str(mesh)}


def list_character_assets(project_id: str) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM character_3d_assets WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()
    return rows_to_dicts(rows)


def verify_character_continuity(project_id: str, asset_id: str) -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM character_3d_assets WHERE id=? AND project_id=?", (asset_id, project_id)).fetchone()
    asset = row_to_dict(row)
    if not asset:
        return {"ok": False, "reason": "Character 3D asset not found"}
    mesh = Path(asset["mesh_path"])
    if not mesh.is_file():
        return {"ok": False, "reason": f"Character mesh missing on disk: {mesh}"}
    voice_id = str((asset.get("validation") or {}).get("voice_id") or "default")
    if asset.get("character_id"):
        with get_conn() as conn:
            crow = conn.execute("SELECT voice_id FROM characters WHERE id=?", (asset["character_id"],)).fetchone()
        if crow:
            voice_id = crow["voice_id"]
    current_hash = compute_continuity_hash(mesh, wardrobe_spec=asset.get("wardrobe_spec") or {}, voice_id=voice_id)
    matches = current_hash == asset.get("continuity_hash")
    return {"ok": matches, "asset_id": asset_id, "expected_hash": asset.get("continuity_hash"), "current_hash": current_hash}
