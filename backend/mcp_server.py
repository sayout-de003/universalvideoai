"""Stdio MCP Server for Universal AI Video Studio."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from backend.db import init_db
from backend.integrations.blender_adapter import apply_animation_and_export, render_blender_scene
from backend.integrations.lemo_opuscar_adapter import lemo_opuscar_adapter
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project, get_project_detail, run_production
from backend.orchestration.shot_orchestrator import plan_screenplay_shots, regenerate_shot, render_single_shot
from backend.services.animated_short_film_service import build_animated_short_package, diagnose_and_repair_shot
from backend.services.character_asset_service import (
    auto_rig_mesh,
    get_default_humanoid_asset,
    register_character_asset,
    validate_and_cleanup_mesh,
)
from backend.services.format_catalog import FORMAT_CATALOG
from backend.services.intake_service import start_intake, submit_intake_answers
from backend.services.package_service import approve_all_mandatory_gates, list_package_artifacts

TOOLS = [
    {"name": "studio_list_formats", "description": "List all 25 supported video formats and their rules.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "studio_start_intake", "description": "Start guided creative intake (asks video type & duration first).", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "studio_answer_intake", "description": "Submit answers to creative intake questions.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}, "answers": {"type": "object"}}, "required": ["project_id", "answers"]}},
    {"name": "studio_create_project", "description": "Plan a full 28-artifact production package for a video prompt.", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}, "target_duration_sec": {"type": "number"}}, "required": ["prompt"]}},
    {"name": "studio_get_package", "description": "Fetch the 28-artifact production package for a project.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}},
    {"name": "studio_approve_gates", "description": "Approve mandatory screenplay, storyboard, and production plan gates.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}},
    {"name": "studio_produce_video", "description": "Render, mix audio, and QA-verify an approved project.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}, "enforce_approval": {"type": "boolean"}}, "required": ["project_id"]}},
    {
        "name": "blender_validate_mesh",
        "description": "Inspect and clean up a 3D mesh (.glb/.fbx/.obj/.blend) in headless Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {"mesh_path": {"type": "string"}, "output_path": {"type": "string"}, "cleanup": {"type": "boolean"}},
            "required": ["mesh_path"],
        },
    },
    {
        "name": "blender_auto_rig_mesh",
        "description": "Attach a humanoid armature with automatic weights to an unrigged 3D mesh and export GLB.",
        "inputSchema": {
            "type": "object",
            "properties": {"mesh_path": {"type": "string"}, "output_glb": {"type": "string"}},
            "required": ["mesh_path", "output_glb"],
        },
    },
    {
        "name": "blender_register_character_asset",
        "description": "Validate and register a real 3D character asset with continuity hash in the studio DB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "name": {"type": "string"},
                "mesh_path": {"type": "string"},
                "reference_image_path": {"type": "string"},
                "voice_id": {"type": "string"},
            },
            "required": ["project_id", "name", "mesh_path"],
        },
    },
    {
        "name": "blender_apply_animation",
        "description": "Bind an animation from the character's action library and export GLB.",
        "inputSchema": {
            "type": "object",
            "properties": {"mesh_path": {"type": "string"}, "output_glb": {"type": "string"}, "animation_name": {"type": "string"}},
            "required": ["mesh_path", "output_glb"],
        },
    },
    {
        "name": "blender_render_character_shot",
        "description": "Render an animated 3D character shot in headless Blender (room/outdoor environment, 3-point lighting, tracked camera) to MP4.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_mp4": {"type": "string"},
                "work_dir": {"type": "string"},
                "character_mesh_path": {"type": "string"},
                "animation_name": {"type": "string"},
                "environment_type": {"type": "string"},
                "duration_sec": {"type": "number"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "fps": {"type": "integer"},
            },
            "required": ["output_mp4"],
        },
    },
    {
        "name": "studio_orchestrate_screenplay",
        "description": "Plan screenplay shots across engines (ai_video, blender, remotion, licensed_footage, hybrid) and optionally render them.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "screenplay": {"type": "object"}, "render": {"type": "boolean"}},
            "required": ["project_id", "screenplay"],
        },
    },
    {
        "name": "studio_regenerate_shot",
        "description": "Regenerate a single shot while preserving all other shot-level assets.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "shot_id": {"type": "string"}, "engine_override": {"type": "string"}, "description_override": {"type": "string"}},
            "required": ["project_id", "shot_id"],
        },
    },
    {
        "name": "opuscar_list_styles",
        "description": "List or search the 99 Lemo-Opuscar code-drawn film styles by category or keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {"category": {"type": "string"}, "query": {"type": "string"}},
        },
    },
    {
        "name": "opuscar_get_style",
        "description": "Fetch the full STYLE.md invariants, DEMO.md, metadata, and guide paths for a Lemo-Opuscar film style.",
        "inputSchema": {
            "type": "object",
            "properties": {"slug_or_name": {"type": "string"}},
            "required": ["slug_or_name"],
        },
    },
    {
        "name": "opuscar_render_page",
        "description": "Render a Lemo-Opuscar HTML/Canvas/WebGL film directory (index.html with window.READY & window.render(t)) to MP4.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_dir": {"type": "string"},
                "output_mp4": {"type": "string"},
                "fps": {"type": "integer"},
                "size": {"type": "string"},
            },
            "required": ["page_dir", "output_mp4"],
        },
    },
    {
        "name": "studio_animate_short_film",
        "description": "Compile a painterly 2D Animated Short Film package (causal story beats, character/environment/vehicle plate prompts, ordered reference manifest, timestamped Master Video Prompt with opening/closing style locks, and sound cue list).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "idea": {"type": "string"},
                "duration_sec": {"type": "integer"},
                "aspect_ratio": {"type": "string"},
                "hero_description": {"type": "string"},
                "world_description": {"type": "string"},
                "vehicle_or_prop": {"type": "string"},
                "editing_mode": {"type": "string"},
                "audio_mode": {"type": "string"},
                "project_id": {"type": "string"},
                "execute_plates": {"type": "boolean"},
            },
            "required": ["idea"],
        },
    },
    {
        "name": "studio_repair_animated_shot",
        "description": "Diagnose a rendered animated short film defect (look/CGI drift, identity, prop duplication, space/time, motion, pace, ending) and return a repaired Master Video Prompt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_description": {"type": "string"},
                "master_prompt": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["issue_description", "master_prompt"],
        },
    },
]


def handle_tool_call(name: str, args: dict[str, Any]) -> Any:
    init_db()
    if name == "studio_list_formats":
        return {"formats": list(FORMAT_CATALOG.keys())}
    if name == "studio_start_intake":
        return start_intake(args["prompt"])
    if name == "studio_answer_intake":
        return submit_intake_answers(args["project_id"], args["answers"])
    if name == "studio_create_project":
        return create_project(ProjectCreateRequest(prompt=args["prompt"], target_duration_sec=args.get("target_duration_sec")))
    if name == "studio_get_package":
        return {"detail": get_project_detail(args["project_id"]), "artifacts": list_package_artifacts(args["project_id"])}
    if name == "studio_approve_gates":
        return approve_all_mandatory_gates(args["project_id"])
    if name == "studio_produce_video":
        return run_production(args["project_id"], enforce_approval=bool(args.get("enforce_approval", True)))
    if name == "blender_validate_mesh":
        out_p = Path(args["output_path"]) if args.get("output_path") else None
        return validate_and_cleanup_mesh(Path(args["mesh_path"]), output_path=out_p, cleanup=bool(args.get("cleanup", True)))
    if name == "blender_auto_rig_mesh":
        return auto_rig_mesh(Path(args["mesh_path"]), Path(args["output_glb"]))
    if name == "blender_register_character_asset":
        ref_p = Path(args["reference_image_path"]) if args.get("reference_image_path") else None
        return register_character_asset(
            project_id=args["project_id"],
            name=args["name"],
            mesh_path=Path(args["mesh_path"]),
            reference_image_path=ref_p,
            voice_id=args.get("voice_id", "default"),
        )
    if name == "blender_apply_animation":
        return apply_animation_and_export(Path(args["mesh_path"]), Path(args["output_glb"]), animation_name=args.get("animation_name", "walk"))
    if name == "blender_render_character_shot":
        out_mp4 = Path(args["output_mp4"])
        work_dir = Path(args.get("work_dir") or out_mp4.parent / "blender_work")
        default_mesh = get_default_humanoid_asset()
        scene = {
            "character_mesh_path": args.get("character_mesh_path") or (str(default_mesh) if default_mesh else None),
            "animation_name": args.get("animation_name", "walk"),
            "environment_type": args.get("environment_type", "room"),
            "duration_sec": float(args.get("duration_sec", 2.0)),
        }
        return render_blender_scene(
            scene=scene,
            output_mp4=out_mp4,
            work_dir=work_dir,
            width=int(args.get("width", 640)),
            height=int(args.get("height", 360)),
            fps=int(args.get("fps", 12)),
        )
    if name == "studio_orchestrate_screenplay":
        planned = plan_screenplay_shots(args["project_id"], args["screenplay"])
        rendered = [render_single_shot(args["project_id"], p["shot_id"]) for p in planned] if args.get("render") else []
        return {"planned": planned, "rendered": rendered}
    if name == "studio_regenerate_shot":
        return regenerate_shot(
            project_id=args["project_id"],
            shot_id=args["shot_id"],
            engine_override=args.get("engine_override"),
            description_override=args.get("description_override"),
        )
    if name == "opuscar_list_styles":
        return lemo_opuscar_adapter.list_styles(category=args.get("category"), query=args.get("query"))
    if name == "opuscar_get_style":
        return lemo_opuscar_adapter.get_style(args["slug_or_name"])
    if name == "opuscar_render_page":
        return lemo_opuscar_adapter.render_page_to_video(
            page_dir=Path(args["page_dir"]),
            output_mp4=Path(args["output_mp4"]),
            fps=int(args.get("fps", 24)),
            size=str(args.get("size", "1280x720")),
        )
    if name == "studio_animate_short_film":
        return build_animated_short_package(
            idea=str(args["idea"]),
            duration_sec=int(args.get("duration_sec", 30)),
            aspect_ratio=str(args.get("aspect_ratio", "16:9")),
            hero_description=args.get("hero_description"),
            world_description=args.get("world_description"),
            vehicle_or_prop=args.get("vehicle_or_prop"),
            editing_mode=str(args.get("editing_mode", "motivated_cuts")),
            audio_mode=str(args.get("audio_mode", "native_diegetic")),
            project_id=args.get("project_id"),
            execute_plates=bool(args.get("execute_plates", False)),
        )
    if name == "studio_repair_animated_shot":
        return diagnose_and_repair_shot(
            issue_description=str(args["issue_description"]),
            master_prompt=str(args["master_prompt"]),
            category=args.get("category"),
        )
    raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
        try:
            if method == "initialize":
                res = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "universal-video-studio", "version": "2.0.0"}}
            elif method == "tools/list":
                res = {"tools": TOOLS}
            elif method == "tools/call":
                out = handle_tool_call(params["name"], params.get("arguments") or {})
                res = {"content": [{"type": "text", "text": json.dumps(out, default=str)}]}
            else:
                res = {"ok": True}
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": res}) + "\n")
        except Exception as exc:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
