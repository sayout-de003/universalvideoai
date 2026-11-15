"""Stdio MCP Server for Universal AI Video Studio."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from backend.db import init_db
from backend.integrations.blender_adapter import apply_animation_and_export, render_blender_scene
from backend.integrations.lemo_opuscar_adapter import lemo_opuscar_adapter
from backend.models import ExportRequest, ProjectCreateRequest, SceneRegenerateRequest
from backend.orchestration.director import (
    approve_single_scene,
    create_project,
    get_project_detail,
    regenerate_project_stage,
    regenerate_single_scene,
    run_production,
)
from backend.orchestration.renderer import export_final_deliverable
from backend.orchestration.shot_orchestrator import plan_screenplay_shots, regenerate_shot, render_single_shot
from backend.services.animated_short_film_service import build_animated_short_package, diagnose_and_repair_shot
from backend.services.character_asset_service import (
    auto_rig_mesh,
    get_default_humanoid_asset,
    register_character_asset,
    validate_and_cleanup_mesh,
)
from backend.services.format_catalog import FORMAT_CATALOG
from backend.services.intake_service import approve_production_brief, start_intake, submit_intake_answers
from backend.services.package_service import approve_all_mandatory_gates, list_package_artifacts
from backend.services.reference_service import (
    analyze_project_references,
    register_and_analyze_reference,
    register_url_reference,
)

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
    # ------------------------------------------------------------------
    # First-class Antigravity Production Tools (Shared Pipeline)
    # ------------------------------------------------------------------
    {
        "name": "create_production",
        "description": "Create a new production from a natural-language prompt, optional URL references, uploaded files, visual style, and preferences.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "title": {"type": "string"},
                "target_duration_sec": {"type": "number"},
                "video_format": {"type": "string"},
                "visual_style": {"type": "string", "description": "pixel_art | 2d_illustrated | 3d_stylized | hand_drawn_storybook"},
                "production_mode": {"type": "string", "description": "free_open_source | hybrid | local_free | professional"},
                "references": {"type": "array", "items": {"type": "object"}},
                "uploads": {"type": "array", "items": {"type": "object"}},
                "preferences": {"type": "object"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "add_production_reference",
        "description": "Register and resolve a reference URL (YouTube, Instagram, Website, Direct Media) with role classification and honest access reporting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "production_id": {"type": "string"},
                "url": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
                "user_notes": {"type": "string"},
            },
            "required": ["production_id", "url"],
        },
    },
    {
        "name": "upload_production_asset",
        "description": "Attach and analyze a local file (image, video, audio, PDF/DOCX/TXT document) as a reference asset on a production.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "production_id": {"type": "string"},
                "file_path": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
                "user_notes": {"type": "string"},
            },
            "required": ["production_id", "file_path"],
        },
    },
    {
        "name": "analyze_references",
        "description": "Re-analyze all references attached to a production and compile the unified reference style guide and bible.",
        "inputSchema": {
            "type": "object",
            "properties": {"production_id": {"type": "string"}},
            "required": ["production_id"],
        },
    },
    {
        "name": "get_production_brief",
        "description": "Inspect the structured creative brief, AI decisions, reference summary, and pending questions for a production.",
        "inputSchema": {
            "type": "object",
            "properties": {"production_id": {"type": "string"}},
            "required": ["production_id"],
        },
    },
    {
        "name": "approve_production_brief",
        "description": "Approve the creative brief (and optionally apply edits to visual_style, target_duration_sec, video_format, production_mode).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "production_id": {"type": "string"},
                "edits": {"type": "object"},
            },
            "required": ["production_id"],
        },
    },
    {
        "name": "generate_research",
        "description": "Run or refresh factual research and claim verification for a production.",
        "inputSchema": {
            "type": "object",
            "properties": {"production_id": {"type": "string"}, "instructions": {"type": "string"}},
            "required": ["production_id"],
        },
    },
    {
        "name": "generate_script",
        "description": "Generate or regenerate the structured multi-scene screenplay and Production Bible.",
        "inputSchema": {
            "type": "object",
            "properties": {"production_id": {"type": "string"}, "instructions": {"type": "string"}},
            "required": ["production_id"],
        },
    },
    {
        "name": "generate_storyboard",
        "description": "Generate or regenerate the storyboard scenes, shot cards, and camera/lighting plan.",
        "inputSchema": {
            "type": "object",
            "properties": {"production_id": {"type": "string"}, "instructions": {"type": "string"}},
            "required": ["production_id"],
        },
    },
    {
        "name": "get_production_status",
        "description": "Get full status, scenes, references, checkpoints, QA reports, and deliverables for a production.",
        "inputSchema": {
            "type": "object",
            "properties": {"production_id": {"type": "string"}},
            "required": ["production_id"],
        },
    },
    {
        "name": "approve_scene",
        "description": "Approve or request revision on a specific scene in a production.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "production_id": {"type": "string"},
                "scene_id": {"type": "string"},
                "approved": {"type": "boolean"},
                "notes": {"type": "string"},
            },
            "required": ["production_id", "scene_id"],
        },
    },
    {
        "name": "regenerate_scene",
        "description": "Regenerate a single scene in isolation (optionally overriding narration, visual prompt, render engine, or visual style) without rebuilding other scenes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "production_id": {"type": "string"},
                "scene_id": {"type": "string"},
                "instructions": {"type": "string"},
                "narration_text": {"type": "string"},
                "visual_prompt": {"type": "string"},
                "render_engine": {"type": "string"},
                "visual_style": {"type": "string"},
            },
            "required": ["production_id", "scene_id"],
        },
    },
    {
        "name": "render_production",
        "description": "Execute full multi-scene rendering, neural voice synthesis, music/stem mixing, subtitle generation, and QA verification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "production_id": {"type": "string"},
                "resume": {"type": "boolean"},
                "enforce_approval": {"type": "boolean"},
            },
            "required": ["production_id"],
        },
    },
    {
        "name": "export_production",
        "description": "Export the final rendered production with custom format, codec, or resolution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "production_id": {"type": "string"},
                "format": {"type": "string"},
                "codec": {"type": "string"},
                "resolution": {"type": "string"},
                "fps": {"type": "integer"},
            },
            "required": ["production_id"],
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
    if name == "create_production":
        req = ProjectCreateRequest(
            prompt=str(args["prompt"]),
            title=args.get("title"),
            target_duration_sec=args.get("target_duration_sec"),
            video_format=args.get("video_format"),
            visual_style=args.get("visual_style"),
            production_mode=args.get("production_mode"),
            references=args.get("references") or [],
            uploads=args.get("uploads") or [],
            preferences=args.get("preferences") or {},
        )
        detail = create_project(req)
        return {"ok": True, "production_id": detail["project"]["id"], "project_id": detail["project"]["id"], **detail}
    if name == "add_production_reference":
        pid = str(args.get("production_id") or args.get("project_id"))
        return register_url_reference(
            project_id=pid,
            url=str(args["url"]),
            roles=args.get("roles"),
            user_notes=str(args.get("user_notes") or ""),
        )
    if name == "upload_production_asset":
        pid = str(args.get("production_id") or args.get("project_id"))
        fp = Path(str(args["file_path"]))
        roles = args.get("roles") or ["visual_style"]
        return register_and_analyze_reference(
            project_id=pid,
            file_path=fp,
            intended_role=roles[0] if isinstance(roles, list) and roles else "visual_style",
            roles=roles if isinstance(roles, list) else [str(roles)],
            user_notes=str(args.get("user_notes") or ""),
        )
    if name == "analyze_references":
        pid = str(args.get("production_id") or args.get("project_id"))
        return analyze_project_references(pid)
    if name == "get_production_brief":
        pid = str(args.get("production_id") or args.get("project_id"))
        detail = get_project_detail(pid)
        if not detail:
            return {"ok": False, "error": f"Production '{pid}' not found"}
        return {
            "ok": True,
            "production_id": pid,
            "project": detail["project"],
            "creative_brief": detail["creative_brief"],
            "reference_assets": detail["reference_assets"],
        }
    if name == "approve_production_brief":
        pid = str(args.get("production_id") or args.get("project_id"))
        return approve_production_brief(pid, edits=args.get("edits"))
    if name == "generate_research":
        pid = str(args.get("production_id") or args.get("project_id"))
        return regenerate_project_stage(pid, "research", instructions=str(args.get("instructions") or ""))
    if name == "generate_script":
        pid = str(args.get("production_id") or args.get("project_id"))
        return regenerate_project_stage(pid, "script", instructions=str(args.get("instructions") or ""))
    if name == "generate_storyboard":
        pid = str(args.get("production_id") or args.get("project_id"))
        return regenerate_project_stage(pid, "storyboard", instructions=str(args.get("instructions") or ""))
    if name == "get_production_status":
        pid = str(args.get("production_id") or args.get("project_id"))
        detail = get_project_detail(pid)
        if not detail:
            return {"ok": False, "error": f"Production '{pid}' not found"}
        return {"ok": True, "production_id": pid, **detail}
    if name == "approve_scene":
        pid = str(args.get("production_id") or args.get("project_id"))
        return approve_single_scene(
            project_id=pid,
            scene_id=str(args["scene_id"]),
            approved=bool(args.get("approved", True)),
            notes=str(args.get("notes") or ""),
        )
    if name == "regenerate_scene":
        pid = str(args.get("production_id") or args.get("project_id"))
        req = SceneRegenerateRequest(
            scene_id=str(args["scene_id"]),
            narration_text=args.get("narration_text"),
            visual_prompt=args.get("visual_prompt") or args.get("instructions"),
            render_engine=args.get("render_engine"),
            visual_style=args.get("visual_style"),
        )
        return regenerate_single_scene(pid, req)
    if name == "render_production":
        pid = str(args.get("production_id") or args.get("project_id"))
        return run_production(
            pid,
            resume=bool(args.get("resume", False)),
            enforce_approval=bool(args.get("enforce_approval", False)),
        )
    if name == "export_production":
        pid = str(args.get("production_id") or args.get("project_id"))
        detail = get_project_detail(pid)
        if not detail:
            return {"ok": False, "error": f"Production '{pid}' not found"}
        ws = Path(detail["project"]["workspace_dir"])
        silent_master = ws / "renders" / "master_video_only.mp4"
        master_mix = ws / "stems" / "master_mix.wav"
        if not silent_master.exists() or not master_mix.exists():
            run_production(pid, resume=True, enforce_approval=False)
        fmt = str(args.get("format") or "mp4")
        codec = str(args.get("codec") or "h264")
        res = str(args.get("resolution") or detail["project"]["resolution"])
        fps = int(args.get("fps") or detail["project"]["fps"])
        out_path = ws / "exports" / f"export_{res}_{codec}.{fmt}"
        chapters = [{"title": c["title"], "duration_sec": c["target_duration_sec"]} for c in detail["chapters"]]
        return export_final_deliverable(silent_master, master_mix, out_path, chapters=chapters, fmt=fmt, codec=codec, resolution=res, fps=fps)
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
