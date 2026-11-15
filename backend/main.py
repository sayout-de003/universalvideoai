"""FastAPI Backend Server for Universal AI Video Production Studio."""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from backend.config import (
    PROJECTS_DIR,
    detect_hardware,
    ensure_directories,
    get_configured_credentials,
    get_studio_settings,
)
from backend.db import get_conn, init_db
from backend.integrations.openmontage_adapter import openmontage_adapter
from backend.providers.image.router import image_provider_readiness
from backend.providers.video.registry import video_provider_readiness
from backend.integrations.openwhispr_adapter import openwhispr_adapter
from backend.models import (
    DirectorChatRequest,
    ExportRequest,
    ProjectCreateRequest,
    SceneRegenerateRequest,
    TimelineClipOp,
    VoiceCommandRequest,
    utc_now,
)
from backend.orchestration.audio_studio import generate_sfx, generate_subtitles
from backend.orchestration.director import (
    _log_agent_message,
    approve_single_scene,
    create_project,
    get_project_detail,
    list_projects,
    pause_production,
    regenerate_project_stage,
    regenerate_single_scene,
    run_production,
    subscribe_events,
    unsubscribe_events,
    update_project_visual_style,
)
from backend.orchestration.engine_registry import get_engine_catalog
from backend.orchestration.renderer import export_final_deliverable
from backend.orchestration.timeline import (
    apply_timeline_op,
    get_timeline,
    redo_timeline,
    undo_timeline,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_directories()
    init_db()
    yield


app = FastAPI(title="Universal AI Video Production Studio API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, Any]:
    hw = detect_hardware()
    return {
        "ok": True,
        "app": "Universal AI Video Production Studio",
        "settings": get_studio_settings(),
        "hardware": hw.to_dict(),
        "credentials_configured": get_configured_credentials(),
        "video_providers": video_provider_readiness(),
        "image_providers": image_provider_readiness(),
        "openmontage_available": openmontage_adapter.is_available(),
        "openwhispr": openwhispr_adapter.get_status(),
        "voicestudio": __import__("backend.integrations.voicestudio_adapter", fromlist=["voicestudio_adapter"]).voicestudio_adapter.get_status(),
        "lemo_opuscar": __import__("backend.integrations.lemo_opuscar_adapter", fromlist=["lemo_opuscar_adapter"]).lemo_opuscar_adapter.get_status(),
    }


@app.get("/api/engines")
def engines() -> dict[str, Any]:
    catalog = get_engine_catalog()
    om_tools = openmontage_adapter.discover_tools() if openmontage_adapter.is_available() else {"total_tools": 0, "tools": []}
    om_pipelines = openmontage_adapter.list_pipelines() if openmontage_adapter.is_available() else []
    return {
        **catalog,
        "openmontage_tools_count": om_tools.get("total_tools", 0),
        "openmontage_configured_tools": om_tools.get("configured_tools", 0),
        "openmontage_pipelines": om_pipelines,
    }


@app.get("/api/projects")
def api_list_projects() -> dict[str, Any]:
    projects = list_projects()
    total_bytes = 0
    for p in projects:
        ws = Path(p["workspace_dir"])
        if ws.exists():
            total_bytes += sum(f.stat().st_size for f in ws.rglob("*") if f.is_file())
    return {"projects": projects, "storage_used_mb": round(total_bytes / (1024 * 1024), 2)}


@app.post("/api/projects")
def api_create_project(req: ProjectCreateRequest) -> dict[str, Any]:
    return create_project(req)


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str) -> dict[str, Any]:
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    return detail


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str) -> dict[str, Any]:
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    ws = Path(detail["project"]["workspace_dir"])
    with get_conn() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    if ws.exists() and ws.parent.resolve() == PROJECTS_DIR.resolve():
        shutil.rmtree(ws, ignore_errors=True)
    return {"ok": True, "deleted": project_id}


@app.post("/api/projects/{project_id}/run")
def api_run_project(project_id: str, background_tasks: BackgroundTasks, sync: bool = False, enforce_approval: bool = False) -> dict[str, Any]:
    if not get_project_detail(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if enforce_approval:
        from backend.services.package_service import check_mandatory_approvals
        gate_check = check_mandatory_approvals(project_id)
        if not gate_check["approved"]:
            raise HTTPException(status_code=409, detail=f"Mandatory approvals pending: {', '.join(gate_check['missing_gates'])}")
    if sync:
        return run_production(project_id, resume=False, enforce_approval=enforce_approval)
    background_tasks.add_task(run_production, project_id, False, enforce_approval)
    return {"ok": True, "project_id": project_id, "status": "running"}


@app.post("/api/projects/{project_id}/pause")
def api_pause_project(project_id: str) -> dict[str, Any]:
    return pause_production(project_id)


@app.post("/api/projects/{project_id}/resume")
def api_resume_project(project_id: str, background_tasks: BackgroundTasks, sync: bool = False) -> dict[str, Any]:
    if not get_project_detail(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if sync:
        return run_production(project_id, resume=True)
    background_tasks.add_task(run_production, project_id, True)
    return {"ok": True, "project_id": project_id, "status": "resuming"}


@app.post("/api/projects/{project_id}/scenes/regenerate")
def api_regenerate_scene(project_id: str, req: SceneRegenerateRequest) -> dict[str, Any]:
    res = regenerate_single_scene(project_id, req)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Regeneration failed"))
    return res


@app.post("/api/projects/{project_id}/chat")
def api_director_chat(project_id: str, req: DirectorChatRequest) -> dict[str, Any]:
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    _log_agent_message(project_id, "User", req.message, role="user", metadata={"source": req.source})
    parsed = openwhispr_adapter.parse_voice_command(req.message)
    if parsed["requires_confirmation"] and not req.confirmed_destructive:
        reply = f"Confirmation required before executing: {parsed['summary']}."
        _log_agent_message(project_id, "AI Director", reply, metadata={"pending_action": parsed})
        return {"ok": True, "requires_confirmation": True, "parsed_action": parsed, "reply": reply}
    exec_result = _execute_parsed_action(project_id, parsed)
    reply = exec_result.get("reply", f"Executed: {parsed['summary']}")
    _log_agent_message(project_id, "AI Director", reply, metadata={"action": parsed, "result": exec_result})
    return {"ok": True, "requires_confirmation": False, "parsed_action": parsed, "result": exec_result, "reply": reply}


def _execute_parsed_action(project_id: str | None, parsed: dict[str, Any]) -> dict[str, Any]:
    intent = parsed["intent"]
    params = parsed.get("params", {})
    if intent == "create_project":
        proj = create_project(ProjectCreateRequest(prompt=params["prompt"]))
        return {"created_project_id": proj["project"]["id"], "reply": f"Created project '{proj['project']['title']}'."}
    if not project_id:
        return {"reply": f"Parsed intent '{intent}', please select an active project."}
    detail = get_project_detail(project_id)
    if not detail:
        return {"reply": "Project not found."}
    if intent == "regenerate_scene":
        num = max(1, int(params.get("scene_number", 1)))
        scenes = detail["scenes"]
        if num <= len(scenes):
            sc = scenes[num - 1]
            res = regenerate_single_scene(project_id, SceneRegenerateRequest(scene_id=sc["id"]))
            return {"regenerated_scene_id": sc["id"], "reply": f"Regenerated Scene {num} ({sc['title']}).", "ok": res.get("ok")}
        return {"reply": f"Scene {num} does not exist."}
    if intent == "generate_subtitles":
        langs = params.get("languages", ["en"])
        ws = Path(detail["project"]["workspace_dir"])
        cursor = 0.0
        timed = []
        for s in detail["scenes"]:
            timed.append({**s, "start_sec": cursor})
            cursor += float(s["duration_sec"])
        subs = generate_subtitles(timed, ws / "subtitles", languages=langs)
        return {"subtitles": subs, "reply": f"Generated subtitles in {', '.join(langs)}."}
    if intent == "adjust_music_volume":
        delta = float(params.get("volume_delta", -0.2))
        with get_conn() as conn:
            for c in conn.execute("SELECT id, properties_json FROM timeline_clips WHERE project_id=? AND track='music'", (project_id,)).fetchall():
                props = json.loads(c["properties_json"] or "{}")
                props["volume"] = round(max(0.05, min(1.0, float(props.get("volume", 0.25)) + delta)), 2)
                conn.execute("UPDATE timeline_clips SET properties_json=?, manual_edited=1 WHERE id=?", (json.dumps(props), c["id"]))
        return {"reply": f"Adjusted music track volume by {delta:+.2f}."}
    if intent == "add_sfx":
        ws = Path(detail["project"]["workspace_dir"])
        sfx_path = ws / "audio" / f"sfx_custom_{uuid.uuid4().hex[:6]}.wav"
        generate_sfx(sfx_path, sfx_type="impact", duration_sec=0.9)
        return {"sfx_path": str(sfx_path), "reply": f"Generated SFX cue for '{params.get('description')}'."}
    if intent == "change_narrator_voice":
        with get_conn() as conn:
            conn.execute("UPDATE speakers SET voice_id='narrator_deep' WHERE project_id=? AND role='narrator'", (project_id,))
        return {"reply": f"Updated narrator voice profile per instruction: '{params.get('instruction')}'."}
    if intent == "extend_chapter":
        chap_num = max(1, int(params.get("chapter_number", 1)))
        extra = float(params.get("extra_seconds", 60.0))
        chapters = detail["chapters"]
        if chap_num <= len(chapters):
            with get_conn() as conn:
                conn.execute("UPDATE chapters SET target_duration_sec = target_duration_sec + ? WHERE id=?", (extra, chapters[chap_num - 1]["id"]))
            return {"reply": f"Extended Chapter {chap_num} target duration by {extra:.0f}s."}
    if intent == "export_video":
        return {"reply": f"Ready to export {params.get('format', 'mp4').upper()} at {params.get('resolution', '1920x1080')}."}
    return {"reply": f"AI Director noted: '{params.get('message', '')}'."}


@app.get("/api/projects/{project_id}/timeline")
def api_get_timeline(project_id: str) -> dict[str, Any]:
    return {"clips": get_timeline(project_id)}


@app.post("/api/projects/{project_id}/timeline/op")
def api_timeline_op(project_id: str, op: TimelineClipOp) -> dict[str, Any]:
    res = apply_timeline_op(project_id, op)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Timeline operation failed"))
    return res


@app.post("/api/projects/{project_id}/timeline/undo")
def api_timeline_undo(project_id: str) -> dict[str, Any]:
    return undo_timeline(project_id)


@app.post("/api/projects/{project_id}/timeline/redo")
def api_timeline_redo(project_id: str) -> dict[str, Any]:
    return redo_timeline(project_id)


@app.post("/api/projects/{project_id}/export")
def api_export_project(project_id: str, req: ExportRequest) -> dict[str, Any]:
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    ws = Path(detail["project"]["workspace_dir"])
    silent_master = ws / "renders" / "master_video_only.mp4"
    master_mix = ws / "stems" / "master_mix.wav"
    if not silent_master.exists() or not master_mix.exists():
        raise HTTPException(status_code=400, detail="Project must be rendered before exporting.")
    out_path = ws / "exports" / f"export_{req.resolution}_{req.codec}.{req.format}"
    chapters = [{"title": c["title"], "duration_sec": c["target_duration_sec"]} for c in detail["chapters"]] if req.include_chapters else None
    return export_final_deliverable(silent_master, master_mix, out_path, chapters=chapters, fmt=req.format, codec=req.codec, resolution=req.resolution, fps=req.fps, bitrate=req.bitrate)


@app.post("/api/files/extract")
async def api_extract_any_file(file: UploadFile = File(...)) -> dict[str, Any]:
    """Read and extract text, scenes, and metadata from ANY uploaded file type (.pdf, .docx, .doc, .rtf, .md, .txt, .json, .csv, .srt, .vtt, .html, media)."""
    from backend.services.document_parser import extract_text_from_any_file

    tmp_dir = PROJECTS_DIR / "_extract_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name
    tmp_path = tmp_dir / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    content = await file.read()
    tmp_path.write_bytes(content)
    try:
        return extract_text_from_any_file(tmp_path, filename=safe_name)
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/projects/{project_id}/upload")
async def api_upload_asset(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    from backend.services.document_parser import extract_text_from_any_file

    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    ws = Path(detail["project"]["workspace_dir"])
    safe_name = Path(file.filename or "upload.bin").name
    dest = ws / "assets" / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    extracted = extract_text_from_any_file(dest, filename=safe_name)
    asset_id = f"ast_{uuid.uuid4().hex[:8]}"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO assets (id, project_id, asset_type, provider, file_path, license, metadata_json, created_at) VALUES (?, ?, 'user_upload', 'user', ?, 'user_owned', ?, ?)",
            (asset_id, project_id, str(dest), json.dumps({"extracted_kind": extracted.get("kind"), "scene_count": extracted.get("scene_count", 0)}), utc_now()),
        )
    return {"ok": True, "asset_id": asset_id, "file_path": str(dest), "size_bytes": len(content), "extracted": extracted}


@app.get("/api/projects/{project_id}/events")
async def api_project_events(project_id: str) -> StreamingResponse:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    subscribe_events(project_id, queue)

    async def event_stream():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'project_id': project_id})}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            unsubscribe_events(project_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/files")
def api_list_project_files(project_id: str) -> dict[str, Any]:
    ws = (PROJECTS_DIR / project_id).resolve()
    if not ws.exists() or not ws.is_dir():
        raise HTTPException(status_code=404, detail="Project workspace not found")
    folders: dict[str, list[dict[str, Any]]] = {}
    for sub in sorted(ws.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        files_list = []
        for f in sorted(sub.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                rel = f.relative_to(ws).as_posix()
                files_list.append({
                    "name": f.name,
                    "subpath": rel,
                    "size_bytes": f.stat().st_size,
                    "is_video": f.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"),
                })
        folders[sub.name] = files_list
    return {"project_id": project_id, "workspace_dir": str(ws), "folders": folders}


@app.get("/api/projects/{project_id}/media/{subpath:path}")
def api_serve_media(project_id: str, subpath: str, download: bool = False) -> FileResponse:
    ws = (PROJECTS_DIR / project_id).resolve()
    target = (ws / subpath).resolve()
    if not str(target).startswith(str(ws)) or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    if download:
        return FileResponse(target, filename=target.name, media_type="application/octet-stream")
    return FileResponse(target)


@app.delete("/api/projects/{project_id}/media/{subpath:path}")
def api_delete_media(project_id: str, subpath: str) -> dict[str, Any]:
    ws = (PROJECTS_DIR / project_id).resolve()
    target = (ws / subpath).resolve()
    if not str(target).startswith(str(ws)) or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    target.unlink()
    return {"ok": True, "deleted": subpath}


@app.get("/api/projects/{project_id}/share-bundle")
def api_share_bundle(project_id: str) -> FileResponse:
    from backend.cli import create_share_bundle

    try:
        bundle_path = create_share_bundle(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    return FileResponse(bundle_path, filename=bundle_path.name, media_type="application/zip")


@app.post("/api/voice/transcribe")
async def api_voice_transcribe(file: UploadFile = File(...), language: str | None = None) -> dict[str, Any]:
    tmp_dir = PROJECTS_DIR / "_voice_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex[:8]}_{Path(file.filename or 'audio.wav').name}"
    tmp_path.write_bytes(await file.read())
    try:
        return openwhispr_adapter.transcribe_file(tmp_path, language=language)
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/voice/command")
def api_voice_command(req: VoiceCommandRequest) -> dict[str, Any]:
    parsed = openwhispr_adapter.parse_voice_command(req.transcript)
    if parsed["requires_confirmation"] and not req.confirmed:
        return {"ok": True, "requires_confirmation": True, "parsed_action": parsed, "message": f"Confirm action: {parsed['summary']}"}
    result = _execute_parsed_action(req.project_id, parsed)
    return {"ok": True, "requires_confirmation": False, "parsed_action": parsed, "result": result}


@app.get("/api/formats")
def api_list_formats() -> dict[str, Any]:
    from backend.services.format_catalog import FORMAT_CATALOG
    return {"formats": [{"key": k, **v} for k, v in FORMAT_CATALOG.items()]}


@app.post("/api/intake/interpret")
def api_intake_interpret(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.intake_service import interpret_prompt_preview
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    return interpret_prompt_preview(
        prompt=prompt,
        references=payload.get("references"),
        uploads=payload.get("uploads"),
        preferences=payload.get("preferences"),
        production_mode=payload.get("production_mode"),
    )


@app.post("/api/intake/start")
def api_intake_start(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.intake_service import start_intake
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    return start_intake(
        prompt,
        title=payload.get("title"),
        language=payload.get("language", "en"),
        preferences=payload.get("preferences"),
        references=payload.get("references"),
        uploads=payload.get("uploads"),
        production_mode=payload.get("production_mode"),
    )


@app.post("/api/intake/{project_id}/answer")
def api_intake_answer(project_id: str, answers: dict[str, Any]) -> dict[str, Any]:
    from backend.services.intake_service import submit_intake_answers
    res = submit_intake_answers(project_id, answers)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Project not found"))
    return res


@app.post("/api/projects/{project_id}/research")
def api_run_research(project_id: str, allow_web: bool = True) -> dict[str, Any]:
    from backend.services.research_service import run_project_research
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    return run_project_research(project_id, detail["project"]["title"], Path(detail["project"]["workspace_dir"]), allow_web=allow_web)


@app.post("/api/projects/{project_id}/references/upload")
async def api_upload_reference(
    project_id: str,
    file: UploadFile = File(...),
    intended_role: str = "visual_style",
    roles: str | None = None,
    user_notes: str = "",
    permissions: str = "user_owned",
) -> dict[str, Any]:
    from backend.services.reference_service import register_and_analyze_reference
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    ws = Path(detail["project"]["workspace_dir"])
    ref_dir = ws / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "reference.bin").name
    dest = ref_dir / f"{uuid.uuid4().hex[:6]}_{safe_name}"
    dest.write_bytes(await file.read())
    role_list = [r.strip() for r in roles.split(",") if r.strip()] if roles else [intended_role]
    return register_and_analyze_reference(
        project_id,
        ws,
        dest,
        intended_role=intended_role,
        permissions=permissions,
        roles=role_list,
        user_notes=user_notes,
    )


@app.post("/api/projects/{project_id}/references/url")
def api_add_url_reference(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.reference_service import register_url_reference
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    url = str(payload.get("url", "")).strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    roles = payload.get("roles") or ([payload["role"]] if payload.get("role") else None)
    user_notes = str(payload.get("user_notes") or payload.get("notes") or "")
    return register_url_reference(project_id=project_id, url=url, roles=roles, user_notes=user_notes)


@app.post("/api/projects/{project_id}/references/analyze")
def api_analyze_project_references(project_id: str) -> dict[str, Any]:
    from backend.services.reference_service import analyze_project_references
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    return analyze_project_references(project_id)


@app.post("/api/projects/{project_id}/scenes/{scene_id}/approve")
def api_approve_scene(project_id: str, scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = payload or {}
    res = approve_single_scene(
        project_id=project_id,
        scene_id=scene_id,
        approved=bool(body.get("approved", True)),
        notes=str(body.get("notes", "")),
    )
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Scene not found"))
    return res


@app.post("/api/projects/{project_id}/visual-style")
def api_update_visual_style(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    style = str(payload.get("visual_style", "")).strip()
    if not style:
        raise HTTPException(status_code=400, detail="visual_style is required")
    res = update_project_visual_style(project_id, style)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Project not found"))
    return res


@app.get("/api/projects/{project_id}/package")
def api_get_package(project_id: str) -> dict[str, Any]:
    from backend.services.package_service import check_mandatory_approvals, list_package_artifacts
    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": project_id,
        "artifacts": list_package_artifacts(project_id),
        "approval_status": check_mandatory_approvals(project_id),
    }


@app.put("/api/projects/{project_id}/package/{artifact_name}")
def api_update_artifact(project_id: str, artifact_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.document_parser import parse_structured_screenplay
    from backend.services.package_service import save_artifact_version

    detail = get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    content = str(payload.get("content", ""))
    author = str(payload.get("author", "user"))
    res = save_artifact_version(project_id, Path(detail["project"]["workspace_dir"]), artifact_name, content, author=author, status="edited")
    if artifact_name == "screenplay.md":
        parsed = parse_structured_screenplay(content)
        if parsed.get("is_structured") and parsed.get("scenes"):
            db_scenes = detail.get("scenes") or []
            with get_conn() as conn:
                if parsed.get("title"):
                    conn.execute("UPDATE projects SET title=?, updated_at=? WHERE id=?", (str(parsed["title"])[:90], utc_now(), project_id))
                for idx, sc_new in enumerate(parsed["scenes"]):
                    if idx < len(db_scenes):
                        sc_id = db_scenes[idx]["id"]
                        raw_t = str(sc_new["title"]).strip()
                        sc_title = raw_t if raw_t.lower().startswith("scene ") else f"Scene {idx + 1}: {raw_t}"
                        conn.execute(
                            """UPDATE scenes SET title=?, script_segment=?, narration_segment=?,
                               visual_description=?, generation_prompt=?, duration_sec=?
                               WHERE id=?""",
                            (
                                sc_title,
                                sc_new["narration_segment"],
                                sc_new["narration_segment"],
                                sc_new["visual_description"],
                                sc_new["visual_description"],
                                float(sc_new.get("duration_sec") or db_scenes[idx]["duration_sec"]),
                                sc_id,
                            ),
                        )
    return res


@app.post("/api/projects/{project_id}/package/{artifact_name}/comments")
def api_add_comment(project_id: str, artifact_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.package_service import add_artifact_comment
    return add_artifact_comment(project_id, artifact_name, str(payload.get("comment_text", "")), section_ref=str(payload.get("section_ref", "")), author=str(payload.get("author", "user")))


@app.post("/api/projects/{project_id}/gates/approve")
def api_approve_gates(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.package_service import approve_all_mandatory_gates, approve_gate
    gate = payload.get("gate_name")
    notes = str(payload.get("notes", ""))
    if gate and gate != "all":
        res = approve_gate(project_id, gate, decision=str(payload.get("decision", "approved")), notes=notes)
        if not res.get("ok"):
            raise HTTPException(status_code=400, detail=res.get("error"))
        return res
    return approve_all_mandatory_gates(project_id, notes=notes)


@app.post("/api/projects/{project_id}/screenplay/orchestrate")
def api_orchestrate_screenplay(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from backend.orchestration.shot_orchestrator import plan_screenplay_shots, render_single_shot
    planned = plan_screenplay_shots(project_id, payload)
    rendered = [render_single_shot(project_id, p["shot_id"]) for p in planned] if payload.get("render") else []
    return {"planned": planned, "rendered": rendered}


@app.post("/api/projects/{project_id}/shots/{shot_id}/regenerate")
def api_regenerate_shot(project_id: str, shot_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.orchestration.shot_orchestrator import regenerate_shot
    body = payload or {}
    return regenerate_shot(
        project_id=project_id,
        shot_id=shot_id,
        engine_override=body.get("engine_override"),
        description_override=body.get("description_override"),
    )


@app.post("/api/projects/{project_id}/qa/human-approve")
def api_human_approve_qa(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from backend.orchestration.qa import record_human_visual_approval
    return record_human_visual_approval(
        project_id=project_id,
        report_id=str(payload["report_id"]),
        approved=bool(payload.get("approved", False)),
        reviewer_notes=str(payload.get("reviewer_notes", "")),
    )


@app.get("/api/projects/{project_id}/characters/3d")
def api_list_characters_3d(project_id: str) -> dict[str, Any]:
    from backend.services.character_asset_service import list_character_assets
    return {"project_id": project_id, "characters_3d": list_character_assets(project_id)}


@app.get("/api/opuscar/styles")
def api_list_opuscar_styles(category: str | None = None, query: str | None = None) -> dict[str, Any]:
    from backend.integrations.lemo_opuscar_adapter import lemo_opuscar_adapter
    return lemo_opuscar_adapter.list_styles(category=category, query=query)


@app.get("/api/opuscar/styles/{slug_or_name}")
def api_get_opuscar_style(slug_or_name: str) -> dict[str, Any]:
    from backend.integrations.lemo_opuscar_adapter import lemo_opuscar_adapter
    res = lemo_opuscar_adapter.get_style(slug_or_name)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Style not found"))
    return res


@app.post("/api/animated-short/package")
def api_create_animated_short_package(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.animated_short_film_service import build_animated_short_package
    idea = str(payload.get("idea", "")).strip()
    if not idea:
        raise HTTPException(status_code=400, detail="idea is required")
    return build_animated_short_package(
        idea=idea,
        duration_sec=int(payload.get("duration_sec", 30)),
        aspect_ratio=str(payload.get("aspect_ratio", "16:9")),
        hero_description=payload.get("hero_description"),
        world_description=payload.get("world_description"),
        vehicle_or_prop=payload.get("vehicle_or_prop"),
        editing_mode=str(payload.get("editing_mode", "motivated_cuts")),
        audio_mode=str(payload.get("audio_mode", "native_diegetic")),
        project_id=payload.get("project_id"),
        execute_plates=bool(payload.get("execute_plates", False)),
    )


@app.post("/api/animated-short/repair")
def api_repair_animated_short(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.animated_short_film_service import diagnose_and_repair_shot
    issue = str(payload.get("issue_description", "")).strip()
    master_prompt = str(payload.get("master_prompt", "")).strip()
    if not issue or not master_prompt:
        raise HTTPException(status_code=400, detail="issue_description and master_prompt are required")
    return diagnose_and_repair_shot(
        issue_description=issue,
        master_prompt=master_prompt,
        category=payload.get("category"),
    )


# ---------------------------------------------------------------------------
# Unified v1 Production API (/api/v1/productions/*) — Shared Entry Point
# ---------------------------------------------------------------------------


@app.post("/api/v1/productions")
def api_v1_create_production(req: ProjectCreateRequest) -> dict[str, Any]:
    detail = create_project(req)
    return {
        "ok": True,
        "production_id": detail["project"]["id"],
        "project_id": detail["project"]["id"],
        **detail,
    }


@app.get("/api/v1/productions/{production_id}")
def api_v1_get_production(production_id: str) -> dict[str, Any]:
    detail = get_project_detail(production_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Production not found")
    return {
        "ok": True,
        "production_id": production_id,
        **detail,
    }


@app.get("/api/v1/productions/{production_id}/events")
async def api_v1_production_events(production_id: str) -> StreamingResponse:
    return await api_project_events(production_id)


@app.post("/api/v1/productions/{production_id}/references")
def api_v1_add_reference(production_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from backend.services.reference_service import register_url_reference
    detail = get_project_detail(production_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Production not found")
    items = payload.get("references")
    if isinstance(items, list):
        added = []
        for item in items:
            if isinstance(item, dict) and item.get("url"):
                added.append(
                    register_url_reference(
                        project_id=production_id,
                        url=str(item["url"]),
                        roles=item.get("roles") or ([item["role"]] if item.get("role") else None),
                        user_notes=str(item.get("user_notes") or item.get("notes") or ""),
                    )
                )
            elif isinstance(item, str) and item.strip():
                added.append(register_url_reference(project_id=production_id, url=item.strip()))
        return {"ok": True, "production_id": production_id, "references": added}
    url = str(payload.get("url", "")).strip()
    if not url:
        raise HTTPException(status_code=400, detail="url or references list is required")
    roles = payload.get("roles") or ([payload["role"]] if payload.get("role") else None)
    notes = str(payload.get("user_notes") or payload.get("notes") or "")
    rec = register_url_reference(project_id=production_id, url=url, roles=roles, user_notes=notes)
    return {"ok": True, "production_id": production_id, "reference": rec}


@app.post("/api/v1/productions/{production_id}/uploads")
async def api_v1_upload_reference(
    production_id: str,
    file: UploadFile = File(...),
    intended_role: str = "visual_style",
    roles: str | None = None,
    user_notes: str = "",
    permissions: str = "user_owned",
) -> dict[str, Any]:
    return await api_upload_reference(
        project_id=production_id,
        file=file,
        intended_role=intended_role,
        roles=roles,
        user_notes=user_notes,
        permissions=permissions,
    )


@app.post("/api/v1/productions/{production_id}/analyze-references")
def api_v1_analyze_references(production_id: str) -> dict[str, Any]:
    from backend.services.reference_service import analyze_project_references
    detail = get_project_detail(production_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Production not found")
    return analyze_project_references(production_id)


@app.post("/api/v1/productions/{production_id}/approve-brief")
def api_v1_approve_brief(production_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.services.intake_service import approve_production_brief
    body = payload or {}
    res = approve_production_brief(production_id, edits=body.get("edits") or body)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Production not found"))
    return res


@app.post("/api/v1/productions/{production_id}/research")
def api_v1_research(production_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    res = regenerate_project_stage(production_id, "research", instructions=str((payload or {}).get("instructions", "")))
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Production not found"))
    return res


@app.post("/api/v1/productions/{production_id}/script")
def api_v1_script(production_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    res = regenerate_project_stage(production_id, "script", instructions=str((payload or {}).get("instructions", "")))
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Production not found"))
    return res


@app.post("/api/v1/productions/{production_id}/storyboard")
def api_v1_storyboard(production_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    res = regenerate_project_stage(production_id, "storyboard", instructions=str((payload or {}).get("instructions", "")))
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Production not found"))
    return res


@app.post("/api/v1/productions/{production_id}/scenes/{scene_id}/approve")
def api_v1_approve_scene(production_id: str, scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return api_approve_scene(production_id, scene_id, payload)


@app.post("/api/v1/productions/{production_id}/scenes/{scene_id}/regenerate")
def api_v1_regenerate_scene(production_id: str, scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = dict(payload or {})
    req = SceneRegenerateRequest(
        scene_id=scene_id,
        narration_text=body.get("narration_text"),
        visual_prompt=body.get("visual_prompt") or body.get("instructions"),
        render_engine=body.get("render_engine"),
        visual_style=body.get("visual_style"),
        preserve_manual_edits=bool(body.get("preserve_manual_edits", True)),
    )
    return api_regenerate_scene(production_id, req)


@app.post("/api/v1/productions/{production_id}/render")
def api_v1_render_production(
    production_id: str,
    background_tasks: BackgroundTasks,
    sync: bool = True,
    enforce_approval: bool = False,
) -> dict[str, Any]:
    return api_run_project(production_id, background_tasks, sync=sync, enforce_approval=enforce_approval)


@app.post("/api/v1/productions/{production_id}/export")
def api_v1_export_production(production_id: str, req: ExportRequest | None = None) -> dict[str, Any]:
    return api_export_project(production_id, req or ExportRequest())


# ---------------------------------------------------------------------------
# Hypit Clean-Room Integration Endpoints (/api/v1/hypit/*)
# ---------------------------------------------------------------------------


@app.post("/api/v1/hypit/author")
def api_hypit_author(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse SVML / semantic script into structured segments, roles, moments, and clean dialogue."""
    from backend.services.hypit_engine import parse_semantic_script
    script_text = str(payload.get("script", "") or payload.get("source_text", "")).strip()
    if not script_text:
        raise HTTPException(status_code=400, detail="script or source_text is required")
    return parse_semantic_script(script_text)


@app.post("/api/v1/hypit/clone-reference")
def api_hypit_clone_reference(payload: dict[str, Any]) -> dict[str, Any]:
    """Deconstruct reference video and generate target production blueprint."""
    from backend.services.hypit_engine import analyze_and_clone_reference
    ref = str(payload.get("reference_video") or payload.get("url") or payload.get("path", "")).strip()
    target_prompt = str(payload.get("prompt") or payload.get("target_prompt", "")).strip()
    if not ref or not target_prompt:
        raise HTTPException(status_code=400, detail="reference_video and prompt are required")
    dur = payload.get("duration_sec") or payload.get("target_duration_sec")
    return analyze_and_clone_reference(ref, target_prompt, target_duration_sec=float(dur) if dur else None, options=payload)


@app.post("/api/v1/hypit/kinetic-caption")
def api_hypit_kinetic_caption(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate word-synchronized kinetic caption files (SRT, VTT, JSON)."""
    from backend.services.hypit_engine import generate_word_synchronized_captions
    tokens = payload.get("tokens") or []
    project_id = str(payload.get("project_id", "hypit_temp"))
    out_dir = PROJECTS_DIR / project_id / "subtitles"
    return generate_word_synchronized_captions(tokens, out_dir, style=str(payload.get("style", "kinetic_highlight")))


@app.post("/api/v1/hypit/variants")
def api_hypit_variants(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate production variants for an existing project reusing unchanged renders."""
    from backend.services.hypit_engine import generate_production_variants
    project_id = str(payload.get("project_id", "")).strip()
    variants = payload.get("variants") or []
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    res = generate_production_variants(project_id, variants)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Failed to generate variants"))
    return res


_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "desktop" / "dist"
if _FRONTEND_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")



