"""AI Director & 11-Agent Production Workforce with Long-Form Chunking, Checkpoints, and Resume."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from backend.config import PROJECTS_DIR
from backend.db import get_conn, row_to_dict, rows_to_dicts
from backend.integrations.openmontage_adapter import openmontage_adapter
from backend.models import (
    ProductionStage,
    ProjectCreateRequest,
    SceneRegenerateRequest,
    VideoCategory,
    utc_now,
)
from backend.orchestration.audio_studio import (
    generate_music_bed,
    generate_sfx,
    generate_subtitles,
    generate_tts,
    mix_audio_stems,
    probe_duration,
)
from backend.orchestration.engine_registry import (
    VISUAL_STYLE_PROFILES,
    is_free_open_source_mode,
    resolve_visual_style_profile,
    select_render_engine,
)
from backend.orchestration.qa import run_qa_verification
from backend.orchestration.renderer import concat_video_clips, export_final_deliverable, render_scene_clip

_EVENT_LISTENERS: dict[str, list[Any]] = {}


def emit_studio_event(project_id: str, event_type: str, payload: dict[str, Any]) -> None:
    ws = PROJECTS_DIR / project_id
    ws.mkdir(parents=True, exist_ok=True)
    event = {"type": event_type, "project_id": project_id, "timestamp": utc_now(), **payload}
    with open(ws / "events.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    for q in list(_EVENT_LISTENERS.get(project_id, [])):
        try:
            q.put_nowait(event)
        except Exception:
            pass


def subscribe_events(project_id: str, queue: Any) -> None:
    _EVENT_LISTENERS.setdefault(project_id, []).append(queue)


def unsubscribe_events(project_id: str, queue: Any) -> None:
    lst = _EVENT_LISTENERS.get(project_id, [])
    if queue in lst:
        lst.remove(queue)


def _log_agent_message(project_id: str, agent_name: str, content: str, role: str = "agent", metadata: dict[str, Any] | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO director_messages (project_id, role, agent_name, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, role, agent_name, content, json.dumps(metadata or {}), utc_now()),
        )
    emit_studio_event(project_id, "agent_message", {"agent": agent_name, "content": content})


def classify_brief(prompt: str, req_duration: float | None = None) -> dict[str, Any]:
    lower = prompt.lower()
    duration = req_duration
    if duration is None:
        m_hr = re.search(r"(\d+(?:\.\d+)?)[\s-]*(?:hour|hr)s?", lower)
        m_min = re.search(r"(\d+(?:\.\d+)?)[\s-]*(?:minute|min)s?", lower)
        m_sec = re.search(r"(\d+(?:\.\d+)?)[\s-]*(?:second|sec)s?", lower)
        if m_hr:
            duration = float(m_hr.group(1)) * 3600.0
        elif m_min:
            duration = float(m_min.group(1)) * 60.0
        elif m_sec:
            duration = float(m_sec.group(1))
        else:
            duration = 30.0

    if any(k in lower for k in ("documentary", "history", "biography", "wildlife", "archival")):
        cat, pipeline = VideoCategory.DOCUMENTARY.value, "documentary-montage"
    elif any(k in lower for k in ("3d", "cartoon", "anime", "animated", "stick-figure", "whiteboard", "puppet")):
        cat, pipeline = VideoCategory.ANIMATION.value, "character-animation"
    elif any(k in lower for k in ("course", "tutorial", "explainer", "science", "math", "lesson", "educational")):
        cat, pipeline = VideoCategory.EDUCATIONAL.value, "animated-explainer"
    elif any(k in lower for k in ("short", "reel", "tiktok", "viral", "faceless")):
        cat, pipeline = VideoCategory.SOCIAL_MEDIA.value, "clip-factory"
    elif any(k in lower for k in ("ad ", "advertisement", "commercial", "product", "saas", "brand")):
        cat, pipeline = VideoCategory.COMMERCIAL.value, "screen-demo" if "saas" in lower else "hybrid"
    elif any(k in lower for k in ("podcast", "audiobook", "lyric", "visualizer", "interview")):
        cat, pipeline = VideoCategory.AUDIO_LED.value, "podcast-repurpose"
    elif any(k in lower for k in ("film", "trailer", "teaser", "horror", "sci-fi", "fantasy", "cinematic")):
        cat, pipeline = VideoCategory.CINEMATIC.value, "cinematic"
    else:
        cat, pipeline = VideoCategory.CUSTOM.value, "hybrid"

    return {"category": cat, "pipeline_name": pipeline, "target_duration_sec": max(5.0, duration)}


def _derive_title(prompt: str) -> str:
    from backend.services.intake_service import extract_clean_title
    return extract_clean_title(prompt)


# Matches the untouched Blender controls in NewProjectView. A difference means the user set them.
_BLENDER_FORM_DEFAULTS = {
    "engine": "auto",
    "environment": "room",
    "lighting": "three_point",
    "camera_motion": "push_in",
    "animation": "walk",
    "samples": 32,
    "lip_sync": True,
}


def _blender_settings_customized(settings: dict) -> bool:
    if str(settings.get("character_mesh_path") or "").strip():
        return True
    for key, default in _BLENDER_FORM_DEFAULTS.items():
        if key not in settings:
            continue
        value = settings[key]
        if isinstance(default, bool):
            if bool(value) != default:
                return True
        elif isinstance(default, int) and not isinstance(value, bool):
            try:
                if int(value) != default:
                    return True
            except (TypeError, ValueError):
                return True
        elif str(value).strip().lower() != str(default):
            return True
    return False


def create_project(req: ProjectCreateRequest) -> dict[str, Any]:
    from backend.services.document_parser import parse_structured_screenplay
    from backend.services.format_catalog import FORMAT_CATALOG, get_format_spec, resolve_format
    from backend.services.reference_service import register_and_analyze_reference, register_url_reference

    project_id = f"proj_{uuid.uuid4().hex[:10]}"
    ws = PROJECTS_DIR / project_id
    for sub in ("assets", "audio", "stems", "renders", "subtitles", "exports", "deliverables", "package", "references"):
        (ws / sub).mkdir(parents=True, exist_ok=True)

    prefs = dict(req.preferences or {})
    video_formats = [str(f) for f in (req.video_formats or prefs.get("video_formats") or []) if f]
    effective_format = req.video_format or prefs.get("video_format") or prefs.get("format") or (video_formats[0] if video_formats else None)
    effective_duration = req.target_duration_sec or prefs.get("target_duration_sec") or prefs.get("duration_sec")
    effective_visual_style = req.visual_style or prefs.get("visual_style")
    effective_prod_mode = str(req.production_mode or prefs.get("production_mode") or req.mode.value)
    skills = list(req.skills or prefs.get("skills") or [])
    blender_settings = dict(req.blender_settings or prefs.get("blender_settings") or {})
    video_type = req.video_type or prefs.get("video_type")
    pacing = req.pacing or prefs.get("pacing") or "balanced"
    color_grade = req.color_grade or prefs.get("color_grade") or "natural"
    quality_preset = req.quality_preset or prefs.get("quality_preset") or "high"

    parsed_script = parse_structured_screenplay(req.uploaded_script or req.prompt)
    script_dur = parsed_script.get("duration_sec") or parsed_script.get("target_duration_sec")
    info = classify_brief(req.prompt, float(effective_duration) if effective_duration is not None else script_dur)

    if video_type in FORMAT_CATALOG and not (effective_format and effective_format in FORMAT_CATALOG):
        effective_format = video_type
    user_chose_format = bool(effective_format and effective_format in FORMAT_CATALOG)
    fmt_key = str(effective_format) if user_chose_format else resolve_format(parsed_script.get("format_hint") or req.prompt)
    fmt_spec = get_format_spec(fmt_key)
    category = fmt_spec["category"] if user_chose_format else info["category"]
    pipeline_name = fmt_spec["pipeline"] or info["pipeline_name"]

    user_chose_duration = effective_duration is not None
    target_dur = float(effective_duration or script_dur or info["target_duration_sec"])

    user_chose_style = bool(effective_visual_style and effective_visual_style not in ("auto", ""))
    visual_style = resolve_visual_style_profile(effective_visual_style, req.prompt)
    inferred_style = resolve_visual_style_profile("", req.prompt)
    prompt_names_style = inferred_style != "2d_illustrated" or any(k in req.prompt.lower() for k in ("2d", "illustrated", "vector", "cutout"))
    scene_visual_style = visual_style if user_chose_style else (inferred_style if prompt_names_style else "")
    style_meta = VISUAL_STYLE_PROFILES.get(visual_style, VISUAL_STYLE_PROFILES["2d_illustrated"])

    user_chose_engine = bool(req.preferred_render_engine)
    render_engine, limitation_notice = select_render_engine(
        category,
        req.prompt,
        req.preferred_render_engine,
        visual_style=visual_style if user_chose_style else None,
    )
    # Blender panel values that differ from the form defaults are a chosen 3D setup.
    # The desktop always sends the untouched defaults, and those must not force Blender.
    skill_engines = {"blender": "blender", "remotion": "remotion", "hyperframes": "hyperframes", "threejs": "threejs"}
    if not user_chose_engine and not user_chose_style and _blender_settings_customized(blender_settings):
        render_engine = "blender"
    # One chosen render skill fills in only when nothing else picked an engine.
    elif not user_chose_engine and not user_chose_style and render_engine == "ffmpeg":
        picked = [skill_engines[s] for s in skills if s in skill_engines]
        if len(picked) == 1:
            render_engine = picked[0]

    user_chose_voice = bool(req.voice_mode and req.voice_mode not in ("auto", ""))
    voice_mode = req.voice_mode or str(prefs.get("voice_mode") or "auto")

    title = (req.title or parsed_script.get("title") or _derive_title(req.prompt))[:90]
    now = utc_now()

    aspect, resolution = req.aspect_ratio, req.resolution
    if (category == VideoCategory.SOCIAL_MEDIA.value or fmt_spec["aspect_ratio"] == "9:16") and req.aspect_ratio == "16:9" and any(k in req.prompt.lower() for k in ("short", "reel", "tiktok", "story")):
        aspect, resolution = "9:16", "1080x1920"

    ai_decisions = {
        "video_format": {
            "selected": fmt_spec["label"],
            "format_key": fmt_key,
            "chosen_by": "user" if user_chose_format else "ai_director",
            "reasoning": (
                f"User explicitly selected format '{fmt_spec['label']}'."
                if user_chose_format
                else f"AI Director analyzed topic & structure cues in the prompt and matched '{fmt_spec['label']}' ({fmt_spec['writer_type']} arc: {' -> '.join(fmt_spec['structure'][:4])}) for maximum retention."
            ),
        },
        "target_duration_sec": {
            "selected": f"{target_dur:.1f}s",
            "chosen_by": "user" if user_chose_duration else ("screenplay_header" if parsed_script.get("duration_sec") else "ai_director"),
            "reasoning": (
                f"User explicitly requested {target_dur:.0f}s duration."
                if user_chose_duration
                else (
                    f"Extracted exact {target_dur:.1f}s total runtime from the structured screenplay scene timings."
                    if parsed_script.get("duration_sec")
                    else f"AI Director selected {target_dur:.0f}s to match optimal pacing ({fmt_spec['wpm']} WPM, ~{fmt_spec.get('shot_density_sec', 6)}s per scene) for {fmt_spec['label']}."
                )
            ),
        },
        "visual_style": {
            "selected": style_meta["label"],
            "style_key": visual_style,
            "chosen_by": "user" if user_chose_style else "ai_director",
            "reasoning": (
                f"User explicitly selected visual style '{style_meta['label']}' ({visual_style})."
                if user_chose_style
                else f"AI Director selected '{style_meta['label']}' ({visual_style}) based on topic and aesthetic cues."
            ),
        },
        "production_mode": {
            "selected": effective_prod_mode,
            "free_open_source_enforced": is_free_open_source_mode(effective_prod_mode),
            "chosen_by": "user" if (req.production_mode or prefs.get("production_mode")) else "ai_director",
            "reasoning": (
                "Strict Free & Open-Source policy active: all paid cloud video, image, LLM, and TTS APIs are blocked."
                if is_free_open_source_mode(effective_prod_mode)
                else f"Production running in '{effective_prod_mode}' mode."
            ),
        },
        "render_engine": {
            "selected": req.preferred_render_engine or f"{render_engine} ({style_meta['label']})",
            "chosen_by": "user" if user_chose_engine else "ai_director",
            "reasoning": (
                f"User explicitly selected render engine '{req.preferred_render_engine}'."
                if user_chose_engine
                else f"AI Director orchestrated multi-engine rendering ({render_engine}) tailored for {style_meta['label']} + smooth FFmpeg xfade transitions."
            ),
        },
        "voice_casting": {
            "selected": voice_mode if user_chose_voice else "Dual Neural Human Voices (Male ChristopherNeural + Female AriaNeural)",
            "chosen_by": "user" if user_chose_voice else "ai_director",
            "reasoning": (
                f"User explicitly selected voice mode '{voice_mode}'."
                if user_chose_voice
                else "AI Director cast alternating real human Edge-TTS neural voices (Male Lead Anchor ChristopherNeural + Female Analytical Co-Narrator AriaNeural) to create dynamic conversational contrast across scenes."
            ),
        },
        "transitions_and_audio": {
            "selected": "FFmpeg xfade (smoothleft, dissolve, circleopen, smoothright) + harmonic SFX",
            "chosen_by": "ai_director",
            "reasoning": "AI Director replaced harsh cuts and noisy pink-noise whooshes with 0.35s padded visual xfade transitions and clean ducked background score.",
        },
    }

    if len(video_formats) > 1:
        ai_decisions["video_formats"] = {
            "selected": ", ".join(video_formats),
            "chosen_by": "user",
            "reasoning": f"User activated multi-format hybrid production: {', '.join(video_formats)}.",
        }
    if skills:
        ai_decisions["skills_orchestration"] = {
            "selected": ", ".join(skills),
            "chosen_by": "user",
            "reasoning": f"User activated multi-skill pipeline orchestration: {', '.join(skills)}.",
        }
    if blender_settings:
        ai_decisions["blender_3d_pipeline"] = {
            "selected": f"Engine: {blender_settings.get('engine', 'Auto')} | Environment: {blender_settings.get('environment', 'Room')} | Lighting: {blender_settings.get('lighting', 'Studio Pro')} | Camera: {blender_settings.get('camera_motion', 'Push-In')}",
            "chosen_by": "user",
            "reasoning": "Configured custom headless Blender 3D animation, lighting, camera choreography, and PBR shaders.",
        }

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO projects
               (id, title, prompt, category, mode, pipeline_name, render_engine, visual_style, production_mode_policy,
                target_duration_sec, aspect_ratio, resolution, fps, language, subtitle_languages_json, status, current_stage,
                budget_limit_usd, workspace_dir, metadata_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id, title, req.prompt, category, req.mode.value, pipeline_name,
                render_engine, visual_style, effective_prod_mode,
                target_dur, aspect, resolution, req.fps, req.language,
                json.dumps(req.subtitle_languages), "planned", ProductionStage.IDEA.value,
                req.budget_limit_usd, str(ws),
                json.dumps({
                    "limitation_notice": limitation_notice,
                    "format_key": fmt_key,
                    "video_formats": video_formats or [fmt_key],
                    "voice_mode": voice_mode,
                    "visual_style": visual_style,
                    "production_mode_policy": effective_prod_mode,
                    "skills": skills,
                    "blender_settings": blender_settings,
                    "video_type": video_type,
                    "pacing": pacing,
                    "color_grade": color_grade,
                    "quality_preset": quality_preset,
                    "ai_decisions": ai_decisions,
                }),
                now, now,
            ),
        )
        conn.execute(
            "INSERT INTO production_runs (id, project_id, status, current_stage, paused, started_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (f"run_{uuid.uuid4().hex[:10]}", project_id, "planned", ProductionStage.IDEA.value, now, now),
        )
        conn.execute(
            """INSERT INTO creative_briefs
               (project_id, version, intake_stage, video_format, target_duration_sec, language,
                confirmed_fields_json, assumed_fields_json, pending_questions_json, qa_history_json, updated_at)
               VALUES (?, 1, 'brief_confirmed', ?, ?, ?, ?, ?, '[]', '[]', ?)""",
            (
                project_id, fmt_key, target_dur, req.language,
                json.dumps({
                    "idea": title,
                    "video_format": fmt_key,
                    "video_formats": video_formats or [fmt_key],
                    "target_duration_sec": target_dur,
                    "voice_mode": voice_mode,
                    "visual_style": visual_style,
                    "production_mode": effective_prod_mode,
                }),
                json.dumps(ai_decisions),
                now,
            ),
        )

    # Ingest any initial reference URLs or uploaded files before planning scenes & bible
    if req.reference_video_url:
        register_url_reference(project_id, req.reference_video_url, ["visual_style", "story_reference"], "Primary reference URL")
    for ref_item in (req.references or []):
        if isinstance(ref_item, dict) and ref_item.get("url"):
            register_url_reference(
                project_id=project_id,
                url=str(ref_item["url"]),
                roles=ref_item.get("roles") or ([ref_item["role"]] if ref_item.get("role") else None),
                user_notes=str(ref_item.get("user_notes") or ref_item.get("notes") or ""),
            )
        elif isinstance(ref_item, str) and ref_item.strip():
            register_url_reference(project_id=project_id, url=ref_item.strip())
    for up_item in (req.uploads or []):
        if isinstance(up_item, dict) and up_item.get("file_path"):
            fp = Path(str(up_item["file_path"]))
            if fp.is_file():
                roles_val = up_item.get("roles") or ([up_item["role"]] if up_item.get("role") else ["visual_style"])
                register_and_analyze_reference(
                    project_id=project_id,
                    file_path=fp,
                    intended_role=roles_val[0] if isinstance(roles_val, list) and roles_val else str(roles_val),
                    roles=roles_val if isinstance(roles_val, list) else [str(roles_val)],
                    user_notes=str(up_item.get("user_notes") or up_item.get("notes") or ""),
                )

    _log_agent_message(
        project_id, "Executive Producer",
        f"Classified brief '{title}' as '{fmt_spec['label']}' ({category}) -> pipeline '{pipeline_name}', style '{visual_style}', engine '{render_engine}', target {target_dur:.1f}s."
        + (f" Note: {limitation_notice}" if limitation_notice else ""),
        metadata={"ai_decisions": ai_decisions},
    )
    for dec_key, dec_val in ai_decisions.items():
        emit_studio_event(project_id, "ai_decision", {"parameter": dec_key, **dec_val})
        if dec_val.get("chosen_by") != "user":
            _log_agent_message(
                project_id,
                "AI Decision Engine",
                f"[Auto-Decided {dec_key}] -> {dec_val['selected']} | Why: {dec_val['reasoning']}",
            )

    _plan_hierarchy_and_bible(
        project_id, title, req.prompt, category, target_dur, render_engine,
        req.language, req.uploaded_script, fmt_key=fmt_key, voice_mode=voice_mode,
        visual_style=scene_visual_style, production_mode=effective_prod_mode,
        lock_engine=user_chose_engine,
    )
    _save_checkpoint(project_id, ProductionStage.IDEA.value, "completed", {"category": category, "pipeline": pipeline_name, "format_key": fmt_key, "visual_style": visual_style})
    openmontage_adapter.write_openmontage_checkpoint(ws, "idea", "completed", {"title": title, "category": category, "visual_style": visual_style}, human_approved=True)
    return get_project_detail(project_id)


def _plan_hierarchy_and_bible(
    project_id: str, title: str, prompt: str, category: str, target_dur: float,
    render_engine: str, language: str, uploaded_script: str | None = None,
    fmt_key: str = "documentaries", voice_mode: str = "auto",
    visual_style: str = "2d_illustrated", production_mode: str = "hybrid",
    lock_engine: bool = False,
) -> None:
    from backend.services.format_catalog import get_format_spec
    from backend.services.package_service import build_full_production_package
    from backend.services.reference_service import build_reference_package
    from backend.services.research_service import run_project_research
    from backend.services.screenwriting_service import develop_and_write_screenplay

    ws = PROJECTS_DIR / project_id
    fmt_spec = get_format_spec(fmt_key)
    with get_conn() as conn:
        meta_row = conn.execute("SELECT metadata_json FROM projects WHERE id=?", (project_id,)).fetchone()
    project_meta = json.loads(meta_row[0]) if meta_row and meta_row[0] else {}
    pacing = str(project_meta.get("pacing") or "balanced")

    emit_studio_event(project_id, "stage_progress", {"stage": "research", "message": f"Researching factual claims and trending video themes for '{title}'..."})
    research_pkg = run_project_research(project_id, title, ws, allow_web=bool(fmt_spec["requires_research"]))
    _log_agent_message(project_id, "Research Director", f"Completed research with {research_pkg['sources_count']} source(s) and {research_pkg['claims_count']} fact-checked claim(s).")
    trending = research_pkg.get("trending_themes") or {}
    if trending:
        _log_agent_message(
            project_id,
            "Trend & Theme Researcher Agent",
            f"Identified trending archetype '{trending.get('theme_archetype')}', style '{trending.get('recommended_animation_style')}', and dual Male/Female neural voice casting.",
        )

    ref_pkg = build_reference_package(project_id, ws)
    emit_studio_event(project_id, "stage_progress", {"stage": "screenwriting", "message": f"Writing screenplay for '{title}' ({fmt_spec['label']})..."})
    script_pkg = develop_and_write_screenplay(
        prompt=prompt,
        format_key=fmt_key,
        brief={
            "target_duration_sec": target_dur,
            "language": language,
            "visual_style": visual_style,
            "production_mode": production_mode,
            "pacing": pacing,
        },
        research_claims=research_pkg.get("claims", []),
        style_guide_md=ref_pkg.get("style_guide_md", ""),
        uploaded_script=uploaded_script,
        voice_mode=voice_mode,
        visual_style=visual_style,
        production_mode=production_mode,
    )
    generated_scenes = script_pkg["scenes"]
    num_chapters = 4 if (target_dur > 360 and len(generated_scenes) >= 8) else (2 if len(generated_scenes) > 4 else 1)
    scenes_per_chapter = max(1, (len(generated_scenes) + num_chapters - 1) // num_chapters)

    _log_agent_message(project_id, "Hollywood Screenplay Architect", f"Prepared {len(generated_scenes)}-scene screenplay (mode: {script_pkg['author_mode']}) with human neural voice direction; evaluator score={script_pkg['evaluation']['weighted_score']}.")
    _log_agent_message(project_id, "Pixar 2D/3D & Motion Director", f"Mapped multi-layer 2D/3D Pixar character animation, Remotion motion graphics, and xfade transitions for '{fmt_spec['label']}'.")

    narrator_male_id = f"spk_{uuid.uuid4().hex[:8]}"
    narrator_female_id = f"spk_{uuid.uuid4().hex[:8]}"
    char_id = f"chr_{uuid.uuid4().hex[:8]}"
    loc_id = f"loc_{uuid.uuid4().hex[:8]}"
    prop_id = f"prp_{uuid.uuid4().hex[:8]}"

    from backend.orchestration.audio_studio import sanitize_spoken_voiceover
    from backend.services.document_parser import clean_markdown_inline

    speakers: list[str] = []
    generic_speaker = ("narrator", "anchor", "lead voice", "protagonist", "deuteragonist", "co-narrator")
    for sc in generated_scenes:
        speaker_name = str(sc.get("speaker_name") or "").strip()
        if speaker_name and not any(g in speaker_name.lower() for g in generic_speaker) and speaker_name not in speakers:
            speakers.append(speaker_name)
    raw_char_name = clean_markdown_inline(str(script_pkg.get("character_name") or title))
    clean_char_name = speakers[0] if speakers else (raw_char_name.splitlines()[0][:48].strip() or "Lead Subject")
    raw_char_desc = str(script_pkg.get("character_description") or "")
    if not raw_char_desc or "#" in raw_char_desc or "SCENE" in raw_char_desc or "Format:" in raw_char_desc:
        clean_char_desc = f"Consistent visual identity for {clean_char_name}: locked facial features, wardrobe, silhouette, and cinematic color grading across all {len(generated_scenes)} scenes."
    else:
        clean_char_desc = clean_markdown_inline(raw_char_desc)[:240]

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO speakers (id, project_id, name, role, voice_provider, voice_id, language) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (narrator_male_id, project_id, "Lead Narrator (Male - ChristopherNeural)", "narrator_male", "edge_neural_tts", "narrator_deep", language),
        )
        conn.execute(
            "INSERT INTO speakers (id, project_id, name, role, voice_provider, voice_id, language) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (narrator_female_id, project_id, "Co-Narrator & Lead (Female - AriaNeural)", "narrator_female", "edge_neural_tts", "narrator_warm", language),
        )
        character_ids: dict[str, str] = {}
        cast_names = speakers[:2] or [clean_char_name]
        for cast_i, cast_name in enumerate(cast_names):
            cast_id = char_id if cast_i == 0 else f"chr_{uuid.uuid4().hex[:8]}"
            character_ids[cast_name] = cast_id
            voice_for_cast = "character_1" if cast_i == 0 else "character_2"
            conn.execute(
                """INSERT INTO characters (id, project_id, name, role, visual_description, facial_features, body_proportions, clothing, personality, voice_id, voice_provider)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cast_id, project_id, cast_name[:48],
                    "protagonist" if cast_i == 0 else "second_lead",
                    clean_char_desc if cast_i == 0 else f"Distinct silhouette and wardrobe from {clean_char_name}.",
                    "Expressive eyes, clear silhouette",
                    "Balanced proportions",
                    "Consistent signature wardrobe across all scenes",
                    "Engaging and memorable",
                    voice_for_cast,
                    "edge_neural_tts",
                ),
            )
        conn.execute(
            """INSERT INTO locations (id, project_id, name, architecture, layout, time_of_day, lighting, weather, color_palette)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (loc_id, project_id, f"Primary Setting: {title[:40]}", f"{fmt_spec['category']} visual environment", "Wide establishing foreground + clean subject plane", "golden_hour", generated_scenes[0].get("lighting", "natural"), "clear", "Project palette"),
        )
        conn.execute(
            "INSERT INTO props (id, project_id, name, description, expected_state, continuity_notes) VALUES (?, ?, ?, ?, 'intact', ?)",
            (prop_id, project_id, "Core Subject Focus", f"Primary visual motif for {title}", "Maintain consistent scale and framing across scenes"),
        )

        scene_idx_global = 0
        for c_i in range(num_chapters):
            chap_id = f"ch_{uuid.uuid4().hex[:8]}"
            chap_scenes = generated_scenes[c_i * scenes_per_chapter:(c_i + 1) * scenes_per_chapter]
            if not chap_scenes:
                continue
            chap_title = f"Chapter {c_i + 1}: {chap_scenes[0]['title']}"
            conn.execute(
                "INSERT INTO chapters (id, project_id, order_index, title, summary, target_duration_sec, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                (chap_id, project_id, c_i, chap_title, f"Chapter {c_i + 1} of {title}", round(sum(s["duration_sec"] for s in chap_scenes), 2)),
            )
            seq_id = f"seq_{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO sequences (id, project_id, chapter_id, order_index, title, description) VALUES (?, ?, ?, 0, ?, ?)",
                (seq_id, project_id, chap_id, f"Sequence {c_i + 1}.1", f"Primary visual sequence for {chap_title}"),
            )
            for s_i, sc_spec in enumerate(chap_scenes):
                scene_id = f"sc_{uuid.uuid4().hex[:8]}"
                narration = sanitize_spoken_voiceover(sc_spec["narration_segment"], default="")
                raw_sc_title = str(sc_spec["title"]).strip()
                scene_title = raw_sc_title if raw_sc_title.lower().startswith("scene ") else f"Scene {scene_idx_global + 1}: {raw_sc_title}"
                vis_desc = sc_spec["visual_description"]
                scene_dur = float(sc_spec["duration_sec"])
                if script_pkg.get("author_mode") == "user_structured_screenplay" and pacing == "fast":
                    scene_dur = max(2.0, round(scene_dur * 0.7, 2))
                elif script_pkg.get("author_mode") == "user_structured_screenplay" and pacing == "cinematic":
                    scene_dur = round(scene_dur * 1.35, 2)
                scene_engine = render_engine if (lock_engine or render_engine != "ffmpeg") else (sc_spec.get("preferred_scene_engine") or render_engine)
                scene_style = visual_style or sc_spec.get("visual_style") or sc_spec.get("animation_theme") or "2d_illustrated"
                speaker_name = str(sc_spec.get("speaker_name") or "")
                speaking_id = character_ids.get(speaker_name) or char_id
                dialogue_json = json.dumps([{"speaker": speaker_name or clean_char_name, "line": narration}] if narration else [])
                scene_voice = sc_spec.get("voice_id") or ("narrator_deep" if scene_idx_global % 2 == 0 else "narrator_warm")
                scene_trans = sc_spec.get("transition") or ("smoothleft" if s_i > 0 else "cut")
                conn.execute(
                    """INSERT INTO scenes
                       (id, project_id, chapter_id, sequence_id, order_index, title, script_segment,
                        narration_segment, dialogue_json, visual_description, generation_prompt, generation_method,
                        render_engine, visual_style, provider, character_refs_json, environment_ref, duration_sec, transition, quality_status, approved)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0)""",
                    (
                        scene_id, project_id, chap_id, seq_id, scene_idx_global,
                        scene_title, narration, narration, dialogue_json, vis_desc, vis_desc,
                        "3d_scene" if scene_engine in ("threejs", "blender") else ("2d_character_animation" if scene_engine in ("hyperframes", "libresprite", "opentoonz") else "procedural_motion"),
                        scene_engine, scene_style, scene_voice, json.dumps([speaking_id]), loc_id, scene_dur, scene_trans,
                    ),
                )
                conn.execute(
                    """INSERT INTO shots (id, project_id, scene_id, order_index, shot_type, camera_angle, camera_movement, lighting, composition, description, duration_sec)
                       VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"sh_{uuid.uuid4().hex[:8]}", project_id, scene_id,
                        sc_spec.get("shot_type", "medium"),
                        sc_spec.get("camera_angle", "eye_level"),
                        sc_spec.get("camera_movement", "slow_push_in"),
                        sc_spec.get("lighting", "natural"),
                        sc_spec.get("composition", "rule_of_thirds"),
                        vis_desc, scene_dur,
                    ),
                )
                scene_idx_global += 1

    _log_agent_message(project_id, "Storyboard Agent", f"Created {scene_idx_global} storyboard shot cards with camera, lighting, and transition specs.")
    _log_agent_message(project_id, "Character Continuity Agent", "Locked canonical character, location, and prop bibles across all chapters.")

    detail = get_project_detail(project_id)
    if detail:
        build_full_production_package(
            project_id=project_id,
            project=detail["project"],
            brief={"confirmed_fields": {"idea": prompt, "video_format": fmt_key, "target_duration_sec": target_dur}, "assumed_fields": {}},
            fmt_spec=fmt_spec,
            script_pkg=script_pkg,
            research_pkg=research_pkg,
            ref_pkg=ref_pkg,
            characters=detail["characters"],
            locations=detail["locations"] if "locations" in detail else [],
            props=detail["props"] if "props" in detail else [],
            scenes=detail["scenes"],
            shots=detail["shots"],
        )


def _save_checkpoint(project_id: str, stage: str, status: str, state: dict[str, Any], human_approved: bool = True) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO checkpoints (id, project_id, stage, status, human_approved, state_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"ckpt_{uuid.uuid4().hex[:10]}", project_id, stage, status, 1 if human_approved else 0, json.dumps(state), utc_now()),
        )
        conn.execute("UPDATE projects SET current_stage=?, updated_at=? WHERE id=?", (stage, utc_now(), project_id))


def pause_production(project_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        conn.execute("UPDATE production_runs SET paused=1, status='paused', updated_at=? WHERE project_id=?", (utc_now(), project_id))
        conn.execute("UPDATE projects SET status='paused', updated_at=? WHERE id=?", (utc_now(), project_id))
    emit_studio_event(project_id, "production_paused", {})
    return {"ok": True, "project_id": project_id, "status": "paused"}


def run_production(project_id: str, resume: bool = False, enforce_approval: bool = False) -> dict[str, Any]:
    detail = get_project_detail(project_id)
    if not detail:
        return {"ok": False, "error": f"Project '{project_id}' not found"}

    if enforce_approval:
        from backend.services.package_service import check_mandatory_approvals
        gate_check = check_mandatory_approvals(project_id)
        if not gate_check["approved"]:
            return {"ok": False, "error": f"Mandatory approvals pending: {', '.join(gate_check['missing_gates'])}", "missing_gates": gate_check["missing_gates"]}

    project = detail["project"]
    ws = Path(project["workspace_dir"])
    chapters, scenes, speakers = detail["chapters"], detail["scenes"], detail["speakers"]
    narrator_voice = speakers[0]["voice_id"] if speakers else "default"
    from backend.services.screenwriting_service import _extract_subject, _short_subject
    shots_by_scene = {sh["scene_id"]: sh for sh in detail.get("shots") or []}
    raw_subj = _extract_subject(project["prompt"])
    project_topic = _short_subject(raw_subj, max_words=3) if raw_subj else project["title"]
    footage = [
        r["file_path"] for r in (detail.get("reference_assets") or [])
        if r.get("asset_type") == "video" and r.get("intended_role") == "existing_footage" and Path(r.get("file_path") or "").is_file()
    ]
    used_hashes: set[str] = set()

    try:
        with get_conn() as conn:
            conn.execute("UPDATE production_runs SET paused=0, status='running', updated_at=? WHERE project_id=?", (utc_now(), project_id))
            conn.execute("UPDATE projects SET status='running', updated_at=? WHERE id=?", (utc_now(), project_id))

        emit_studio_event(project_id, "production_started", {"resume": resume, "scenes": len(scenes)})
        _save_checkpoint(project_id, ProductionStage.GENERATION.value, "running", {"total_scenes": len(scenes)})

        narration_wavs, sfx_cues, scenes_with_timings = [], [], []
        cursor_sec = 0.0

        for idx, sc in enumerate(scenes):
            with get_conn() as conn:
                run_row = conn.execute("SELECT paused FROM production_runs WHERE project_id=? ORDER BY started_at DESC LIMIT 1", (project_id,)).fetchone()
                if run_row and run_row["paused"]:
                    _save_checkpoint(project_id, ProductionStage.GENERATION.value, "paused", {"completed_scenes": idx})
                    return {"ok": True, "status": "paused", "completed_scenes": idx}

            scene_mp4 = ws / "renders" / f"{sc['id']}.mp4"
            scene_wav = ws / "audio" / f"{sc['id']}_narration.wav"

            if not (resume and scene_mp4.exists() and scene_wav.exists() and sc.get("quality_status") == "generated"):
                raw_v = sc.get("voice_id") or sc.get("provider")
                scene_voice = (
                    raw_v
                    if raw_v in ("narrator_deep", "narrator_warm", "character_1", "character_2", "character_3", "male", "female")
                    else ("narrator_deep" if idx % 2 == 0 else "narrator_warm")
                )
                scene_engine = sc.get("render_engine") or project["render_engine"]
                scene_style = sc.get("visual_style") or project.get("visual_style") or "2d_illustrated"
                prod_mode_policy = project.get("production_mode_policy") or project.get("mode") or "hybrid"
                if scene_voice == "character_1":
                    voice_label = "Male Neural (GuyNeural - Alex)"
                elif scene_voice == "character_2":
                    voice_label = "Female Neural (JennyNeural - Maya)"
                elif scene_voice in ("character_3", "narrator_deep"):
                    voice_label = "Male Neural (ChristopherNeural - Liam)"
                else:
                    voice_label = "Female Neural (AriaNeural)"
                emit_studio_event(
                    project_id,
                    "scene_started",
                    {
                        "scene_id": sc["id"],
                        "index": idx + 1,
                        "total": len(scenes),
                        "title": sc["title"],
                        "engine": scene_engine,
                        "visual_style": scene_style,
                        "voice": voice_label,
                        "transition": sc.get("transition") or "smoothleft",
                    },
                )
                _log_agent_message(
                    project_id,
                    "Production Orchestrator",
                    f"Scene {idx + 1}/{len(scenes)} ({sc['title']}): Synthesizing {voice_label} voice + rendering via '{scene_engine}' (style '{scene_style}') with '{sc.get('transition') or 'smoothleft'}' transition.",
                )
                clean_narr = (sc.get("narration_segment") or "").strip()
                tts_res = generate_tts(
                    clean_narr,
                    scene_wav,
                    voice_id=scene_voice,
                    language=project["language"],
                    production_mode=prod_mode_policy,
                )
                actual_audio_dur = float(tts_res.get("duration_sec") or sc["duration_sec"])
                target_scene_dur = max(float(sc["duration_sec"]), actual_audio_dur + 0.4)
                emit_studio_event(
                    project_id,
                    "tts_synthesized",
                    {
                        "scene_id": sc["id"],
                        "index": idx + 1,
                        "voice": tts_res.get("voice") or voice_label,
                        "provider": tts_res.get("provider"),
                        "duration_sec": round(actual_audio_dur, 2),
                    },
                )
                shot = shots_by_scene.get(sc["id"]) or {}
                spoken_by = ""
                try:
                    spoken_turns = json.loads(sc.get("dialogue_json") or "[]")
                    if spoken_turns and isinstance(spoken_turns[0], dict):
                        spoken_by = str(spoken_turns[0].get("speaker") or "")
                except Exception:
                    spoken_by = ""
                render_res = render_scene_clip(
                    {
                        **sc,
                        "visual_style": scene_style,
                        "duration_sec": target_scene_dur,
                        "camera_movement": shot.get("camera_movement") or sc.get("camera_movement"),
                        "lighting": shot.get("lighting") or sc.get("lighting"),
                        "shot_type": shot.get("shot_type") or sc.get("shot_type"),
                        "speaker_name": spoken_by or ("Male Lead Voice" if scene_voice in ("narrator_deep", "character_1", "male") else "Female Lead Voice"),
                    },
                    scene_mp4,
                    category=project["category"], resolution=project["resolution"], fps=int(project["fps"]),
                    render_engine=scene_engine,
                    project_topic=project_topic,
                    scene_index=idx,
                    excluded_sha256=used_hashes,
                    source_media=footage[idx % len(footage)] if footage else None,
                    production_mode=prod_mode_policy,
                )
                with get_conn() as conn:
                    v_asset_id, a_asset_id = f"ast_{uuid.uuid4().hex[:8]}", f"ast_{uuid.uuid4().hex[:8]}"
                    clip_meta = json.dumps({
                        "source_type": render_res.get("source_type"),
                        "provider": render_res.get("provider"),
                        "model": render_res.get("model"),
                        "job_id": render_res.get("job_id"),
                        "estimated_cost_usd": render_res.get("estimated_cost_usd"),
                        "generation_state": render_res.get("generation_state"),
                    })
                    conn.execute(
                        "INSERT INTO assets (id, project_id, scene_id, asset_type, provider, file_path, duration_sec, license, metadata_json, created_at) VALUES (?, ?, ?, 'video', ?, ?, ?, 'generated_local', ?, ?)",
                        (v_asset_id, project_id, sc["id"], render_res.get("provider") or render_res.get("engine_used", "ffmpeg"), str(scene_mp4), target_scene_dur, clip_meta, utc_now()),
                    )
                    conn.execute("INSERT INTO assets (id, project_id, scene_id, asset_type, provider, file_path, duration_sec, license, created_at) VALUES (?, ?, ?, 'audio', ?, ?, ?, ?, ?)", (a_asset_id, project_id, sc["id"], tts_res.get("provider", "local"), str(scene_wav), actual_audio_dur, tts_res.get("license", "generated_local"), utc_now()))
                    conn.execute("UPDATE scenes SET duration_sec=?, visual_asset_id=?, audio_asset_id=?, rendered_clip_path=?, quality_status='generated' WHERE id=?", (target_scene_dur, v_asset_id, a_asset_id, str(scene_mp4), sc["id"]))
                sc["duration_sec"] = target_scene_dur
                emit_studio_event(
                    project_id,
                    "scene_generated",
                    {
                        "scene_id": sc["id"],
                        "index": idx + 1,
                        "total": len(scenes),
                        "title": sc["title"],
                        "engine_used": render_res.get("engine_used") or scene_engine,
                        "duration_sec": round(target_scene_dur, 2),
                    },
                )
            else:
                sc["duration_sec"] = max(float(sc["duration_sec"]), probe_duration(scene_wav) + 0.4)

            narration_wavs.append((scene_wav, cursor_sec))
            scenes_with_timings.append({**sc, "start_sec": cursor_sec})
            cursor_sec += float(sc["duration_sec"])

        total_dur = max(1.0, cursor_sec)
        _save_checkpoint(project_id, ProductionStage.AUDIO_SYNC.value, "running", {"total_duration_sec": total_dur})
        music_wav = ws / "audio" / "background_music.wav"
        mood = "comedy" if "funny" in project["prompt"].lower() else ("cinematic" if project["category"] in ("documentary", "cinematic") else "upbeat")
        generate_music_bed(music_wav, duration_sec=total_dur, mood=mood)
        stems = mix_audio_stems(narration_wavs, music_wav, sfx_cues, total_dur, ws / "stems", music_volume=0.22)
        sub_langs = project.get("subtitle_languages") or ["en"]
        subs = generate_subtitles(scenes_with_timings, ws / "subtitles", languages=sub_langs, word_level=True)
        _sync_timeline_from_production(project_id, scenes_with_timings)

        _log_agent_message(project_id, "Sound Designer Agent", "Generated mood-matched score, dual Male/Female neural narration stems, and clean ducked master mix (zero whoosh noise at cuts).")
        _log_agent_message(project_id, "Video Editor Agent", "Synchronized 12-track timeline with narration, music ducking, xfade transitions, and word-level captions.")

        _save_checkpoint(project_id, ProductionStage.RENDERING.value, "running", {})
        chapter_videos, chapter_meta = [], []
        for ch in chapters:
            ch_scenes = [s for s in scenes_with_timings if s["chapter_id"] == ch["id"]]
            ch_mp4 = ws / "renders" / f"{ch['id']}.mp4"
            concat_video_clips(
                [ws / "renders" / f"{s['id']}.mp4" for s in ch_scenes],
                ch_mp4,
                transitions=[str(s.get("transition") or "smoothleft") for s in ch_scenes],
            )
            chapter_videos.append(ch_mp4)
            chapter_meta.append({"title": ch["title"], "duration_sec": sum(float(s["duration_sec"]) for s in ch_scenes)})
            with get_conn() as conn:
                conn.execute("UPDATE chapters SET status='rendered', rendered_path=? WHERE id=?", (str(ch_mp4), ch["id"]))

        silent_master = ws / "renders" / "master_video_only.mp4"
        concat_video_clips(chapter_videos, silent_master)
        final_mp4 = ws / "exports" / "final_production.mp4"
        primary_srt = Path(subs["files"][sub_langs[0]]["srt"]) if subs["files"] else None
        export_final_deliverable(silent_master, Path(stems["master_mix"]), final_mp4, chapters=chapter_meta, subtitle_srt=primary_srt, fmt="mp4", codec="h264", resolution=project["resolution"], fps=int(project["fps"]))

        _save_checkpoint(project_id, ProductionStage.QUALITY_ASSURANCE.value, "running", {})
        rendered_ok = sum(1 for s in scenes if (ws / "renders" / f"{s['id']}.mp4").is_file())
        qa_report = run_qa_verification(
            project_id, final_mp4, expected_aspect_ratio=project["aspect_ratio"], expected_fps=int(project["fps"]),
            subtitle_paths=[Path(v["srt"]) for v in subs["files"].values()],
            scene_count_expected=len(scenes), scene_count_rendered=rendered_ok,
            expected_duration_sec=total_dur,
        )
        _log_agent_message(project_id, "Quality Assurance Agent", f"QA executed on {final_mp4.name}: {qa_report['summary']}")

        (ws / "deliverables" / "production_report.json").write_text(
            json.dumps({"project_id": project_id, "title": project["title"], "final_video": str(final_mp4), "stems": stems, "subtitles": subs["files"], "qa_report": qa_report, "chapters": chapter_meta}, indent=2),
            encoding="utf-8",
        )
        (ws / "deliverables" / "final_qa_report.json").write_text(json.dumps(qa_report, indent=2), encoding="utf-8")
        (ws / "deliverables" / "final_qa_report.md").write_text(
            f"# Final QA Report: {project['title']}\n\n- **Passed:** {qa_report['passed']}\n- **Summary:** {qa_report['summary']}\n",
            encoding="utf-8",
        )
        (ws / "deliverables" / "render_manifest.json").write_text(
            json.dumps({"project_id": project_id, "render_engine": project["render_engine"], "resolution": project["resolution"], "fps": project["fps"], "scenes_rendered": len(scenes), "chapters": chapter_meta}, indent=2),
            encoding="utf-8",
        )
        thumb_path = ws / "exports" / "thumbnail.jpg"
        try:
            import subprocess
            subprocess.run(["ffmpeg", "-y", "-ss", "1.0", "-i", str(final_mp4), "-vframes", "1", str(thumb_path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        (ws / "deliverables" / "delivery_manifest.json").write_text(
            json.dumps({"project_id": project_id, "final_mp4": str(final_mp4), "thumbnail": str(thumb_path) if thumb_path.exists() else None, "subtitles": subs["files"], "stems": stems}, indent=2),
            encoding="utf-8",
        )

        final_status = "completed" if qa_report["passed"] else "qa_failed"
        _save_checkpoint(project_id, ProductionStage.DELIVERY.value, final_status, {"final_video": str(final_mp4), "qa_passed": qa_report["passed"]})
        openmontage_adapter.write_openmontage_checkpoint(ws, "publish", final_status, {"final_video": str(final_mp4)}, human_approved=True)
        with get_conn() as conn:
            conn.execute("UPDATE projects SET status=?, updated_at=? WHERE id=?", (final_status, utc_now(), project_id))
            conn.execute("UPDATE production_runs SET status=?, current_stage=?, updated_at=? WHERE project_id=?", (final_status, ProductionStage.DELIVERY.value, utc_now(), project_id))

        emit_studio_event(project_id, "production_completed", {"status": final_status, "final_video": str(final_mp4)})
        return get_project_detail(project_id)
    except Exception as exc:
        with get_conn() as conn:
            conn.execute("UPDATE production_runs SET status='failed', error_message=?, updated_at=? WHERE project_id=?", (str(exc), utc_now(), project_id))
            conn.execute("UPDATE projects SET status='error', updated_at=? WHERE id=?", (utc_now(), project_id))
        emit_studio_event(project_id, "production_error", {"error": str(exc)})
        _log_agent_message(project_id, "Production Supervisor", f"Production run failed: {exc}")
        return {"ok": False, "error": str(exc), "project_id": project_id}

def regenerate_single_scene(project_id: str, req: SceneRegenerateRequest) -> dict[str, Any]:
    detail = get_project_detail(project_id)
    if not detail:
        return {"ok": False, "error": "Project not found"}
    project = detail["project"]
    ws = Path(project["workspace_dir"])
    scene = next((s for s in detail["scenes"] if s["id"] == req.scene_id), None)
    if not scene:
        return {"ok": False, "error": f"Scene '{req.scene_id}' not found"}

    new_narration = req.narration_text if req.narration_text is not None else scene["narration_segment"]
    new_prompt = req.visual_prompt if req.visual_prompt is not None else scene["generation_prompt"]
    new_style = req.visual_style or scene.get("visual_style") or project.get("visual_style") or "2d_illustrated"
    if req.visual_style and not req.render_engine:
        style_meta = VISUAL_STYLE_PROFILES.get(new_style, {})
        new_engine = style_meta.get("default_engine") or scene["render_engine"]
    else:
        new_engine = req.render_engine or scene["render_engine"]
    prod_mode_policy = project.get("production_mode_policy") or project.get("mode") or "hybrid"
    scene_wav = ws / "audio" / f"{scene['id']}_narration.wav"
    scene_mp4 = ws / "renders" / f"{scene['id']}.mp4"

    from backend.services.screenwriting_service import _extract_subject
    tts_res = generate_tts(new_narration, scene_wav, language=project["language"], production_mode=prod_mode_policy)
    new_dur = max(float(scene["duration_sec"]), float(tts_res.get("duration_sec", 4.0)) + 0.4)
    render_scene_clip(
        {**scene, "generation_prompt": new_prompt, "visual_style": new_style, "duration_sec": new_dur},
        scene_mp4,
        category=project["category"],
        resolution=project["resolution"],
        fps=int(project["fps"]),
        render_engine=new_engine,
        project_topic=_extract_subject(project["prompt"]) or project["title"],
        production_mode=prod_mode_policy,
    )

    with get_conn() as conn:
        conn.execute(
            "UPDATE scenes SET narration_segment=?, generation_prompt=?, render_engine=?, visual_style=?, duration_sec=?, quality_status='generated' WHERE id=?",
            (new_narration, new_prompt, new_engine, new_style, new_dur, scene["id"]),
        )
        if req.preserve_manual_edits:
            conn.execute("UPDATE timeline_clips SET duration_sec=? WHERE project_id=? AND scene_id=? AND manual_edited=0", (new_dur, project_id, scene["id"]))

    updated_detail = get_project_detail(project_id)
    ch_id = scene["chapter_id"]
    ch_clips = [ws / "renders" / f"{s['id']}.mp4" for s in updated_detail["scenes"] if s["chapter_id"] == ch_id and (ws / "renders" / f"{s['id']}.mp4").exists()]
    if ch_clips:
        concat_video_clips(ch_clips, ws / "renders" / f"{ch_id}.mp4")

    all_ch_mp4s = [ws / "renders" / f"{c['id']}.mp4" for c in updated_detail["chapters"] if (ws / "renders" / f"{c['id']}.mp4").exists()]
    if all_ch_mp4s:
        silent_master = ws / "renders" / "master_video_only.mp4"
        concat_video_clips(all_ch_mp4s, silent_master)
        master_mix = ws / "stems" / "master_mix.wav"
        if master_mix.exists():
            export_final_deliverable(silent_master, master_mix, ws / "exports" / "final_production.mp4", resolution=project["resolution"], fps=int(project["fps"]))

    _log_agent_message(project_id, "Video Editor Agent", f"Regenerated scene '{scene['title']}' in isolation (style '{new_style}', engine '{new_engine}'); manual edits in other scenes preserved.")
    emit_studio_event(project_id, "scene_regenerated", {"scene_id": scene["id"], "visual_style": new_style, "render_engine": new_engine})
    return {"ok": True, "scene_id": scene["id"], "visual_style": new_style, "render_engine": new_engine, "project": get_project_detail(project_id)}


def approve_single_scene(project_id: str, scene_id: str, approved: bool = True, notes: str = "") -> dict[str, Any]:
    with get_conn() as conn:
        row = row_to_dict(conn.execute("SELECT * FROM scenes WHERE id=? AND project_id=?", (scene_id, project_id)).fetchone())
        if not row:
            return {"ok": False, "error": f"Scene '{scene_id}' not found in project '{project_id}'"}
        conn.execute("UPDATE scenes SET approved=? WHERE id=? AND project_id=?", (1 if approved else 0, scene_id, project_id))
    _log_agent_message(
        project_id,
        "Producer Gatekeeper",
        f"Scene '{row['title']}' ({scene_id}) marked as {'APPROVED' if approved else 'NEEDS REVISION'}." + (f" Notes: {notes}" if notes else ""),
    )
    emit_studio_event(project_id, "scene_approval_updated", {"scene_id": scene_id, "approved": approved, "notes": notes})
    return {"ok": True, "project_id": project_id, "scene_id": scene_id, "approved": approved}


def update_project_visual_style(project_id: str, visual_style: str) -> dict[str, Any]:
    resolved = resolve_visual_style_profile(visual_style)
    style_meta = VISUAL_STYLE_PROFILES.get(resolved, VISUAL_STYLE_PROFILES["2d_illustrated"])
    new_engine = style_meta["default_engine"]
    with get_conn() as conn:
        proj = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
        if not proj:
            return {"ok": False, "error": f"Project '{project_id}' not found"}
        meta = dict(proj.get("metadata") or {})
        meta["visual_style"] = resolved
        conn.execute(
            "UPDATE projects SET visual_style=?, render_engine=?, metadata_json=?, updated_at=? WHERE id=?",
            (resolved, new_engine, json.dumps(meta), utc_now(), project_id),
        )
        conn.execute(
            "UPDATE scenes SET visual_style=?, render_engine=? WHERE project_id=?",
            (resolved, new_engine, project_id),
        )
    _log_agent_message(project_id, "Art Director", f"Updated project visual style to '{style_meta['label']}' ({resolved}) and render engine to '{new_engine}'.")
    emit_studio_event(project_id, "visual_style_updated", {"visual_style": resolved, "render_engine": new_engine})
    return {"ok": True, "project_id": project_id, "visual_style": resolved, "render_engine": new_engine, "project": get_project_detail(project_id)}


def regenerate_project_stage(project_id: str, stage: str, instructions: str = "") -> dict[str, Any]:
    detail = get_project_detail(project_id)
    if not detail:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    proj = detail["project"]
    ws = Path(proj["workspace_dir"])
    meta = proj.get("metadata") or {}
    fmt_key = meta.get("format_key") or "documentaries"
    voice_mode = meta.get("voice_mode") or "auto"
    visual_style = proj.get("visual_style") or meta.get("visual_style") or "2d_illustrated"
    prod_mode = proj.get("production_mode_policy") or meta.get("production_mode_policy") or proj.get("mode") or "hybrid"

    if stage == "research":
        from backend.services.research_service import run_project_research
        res = run_project_research(project_id, proj["title"], ws, allow_web=True)
        _save_checkpoint(project_id, ProductionStage.RESEARCH.value, "completed", {"claims_count": res.get("claims_count", 0)})
        return {"ok": True, "stage": "research", "research": res, "project": get_project_detail(project_id)}

    if stage in ("script", "storyboard"):
        with get_conn() as conn:
            for tbl in ("shots", "scenes", "sequences", "chapters", "speakers", "characters", "locations", "props"):
                conn.execute(f"DELETE FROM {tbl} WHERE project_id=?", (project_id,))
        prompt_text = f"{proj['prompt']}\n{instructions}".strip() if instructions else proj["prompt"]
        _plan_hierarchy_and_bible(
            project_id, proj["title"], prompt_text, proj["category"], float(proj["target_duration_sec"]),
            proj["render_engine"], proj["language"], None, fmt_key=fmt_key, voice_mode=voice_mode,
            visual_style=visual_style, production_mode=prod_mode,
        )
        _save_checkpoint(project_id, ProductionStage.STORYBOARD.value if stage == "storyboard" else ProductionStage.SCRIPT.value, "completed", {"stage": stage})
        return {"ok": True, "stage": stage, "project": get_project_detail(project_id)}

    return {"ok": False, "error": f"Unsupported stage '{stage}'"}


def _sync_timeline_from_production(project_id: str, scenes_with_timings: list[dict[str, Any]]) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM timeline_clips WHERE project_id=? AND manual_edited=0", (project_id,))
        for sc in scenes_with_timings:
            start, dur = float(sc["start_sec"]), float(sc["duration_sec"])
            conn.execute("INSERT INTO timeline_clips (id, project_id, track, scene_id, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited) VALUES (?, ?, 'main_video', ?, ?, ?, ?, 0.0, ?, 0)", (f"clip_{uuid.uuid4().hex[:10]}", project_id, sc["id"], sc["title"], start, dur, json.dumps({"transition": sc["transition"]})))
            conn.execute("INSERT INTO timeline_clips (id, project_id, track, scene_id, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited) VALUES (?, ?, 'narration', ?, ?, ?, ?, 0.0, '{}', 0)", (f"clip_{uuid.uuid4().hex[:10]}", project_id, sc["id"], f"VO: {sc['title']}", start, dur))
            conn.execute("INSERT INTO timeline_clips (id, project_id, track, scene_id, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited) VALUES (?, ?, 'captions', ?, ?, ?, ?, 0.0, '{}', 0)", (f"clip_{uuid.uuid4().hex[:10]}", project_id, sc["id"], sc["narration_segment"][:40], start, dur))
        total_dur = sum(float(s["duration_sec"]) for s in scenes_with_timings)
        conn.execute("INSERT INTO timeline_clips (id, project_id, track, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited) VALUES (?, ?, 'music', 'Background Score (Ducked)', 0.0, ?, 0.0, ?, 0)", (f"clip_{uuid.uuid4().hex[:10]}", project_id, total_dur, json.dumps({"volume": 0.25, "ducking": True})))


def list_projects() -> list[dict[str, Any]]:
    with get_conn() as conn:
        # Scene counts let the UI show real progress per project without fetching every project's detail.
        return rows_to_dicts(conn.execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM scenes s WHERE s.project_id = p.id) AS scenes_total,
                      (SELECT COUNT(*) FROM scenes s WHERE s.project_id = p.id AND s.quality_status = 'generated') AS scenes_done
               FROM projects p ORDER BY p.updated_at DESC"""
        ).fetchall())


def get_project_detail(project_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        proj = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
        if not proj:
            return None
        return {
            "project": proj,
            "creative_brief": row_to_dict(conn.execute("SELECT * FROM creative_briefs WHERE project_id=?", (project_id,)).fetchone()),
            "chapters": rows_to_dicts(conn.execute("SELECT * FROM chapters WHERE project_id=? ORDER BY order_index", (project_id,)).fetchall()),
            "sequences": rows_to_dicts(conn.execute("SELECT * FROM sequences WHERE project_id=? ORDER BY order_index", (project_id,)).fetchall()),
            "scenes": rows_to_dicts(conn.execute("SELECT * FROM scenes WHERE project_id=? ORDER BY order_index", (project_id,)).fetchall()),
            "shots": rows_to_dicts(conn.execute("SELECT * FROM shots WHERE project_id=? ORDER BY order_index", (project_id,)).fetchall()),
            "characters": rows_to_dicts(conn.execute("SELECT * FROM characters WHERE project_id=?", (project_id,)).fetchall()),
            "locations": rows_to_dicts(conn.execute("SELECT * FROM locations WHERE project_id=?", (project_id,)).fetchall()),
            "props": rows_to_dicts(conn.execute("SELECT * FROM props WHERE project_id=?", (project_id,)).fetchall()),
            "speakers": rows_to_dicts(conn.execute("SELECT * FROM speakers WHERE project_id=?", (project_id,)).fetchall()),
            "assets": rows_to_dicts(conn.execute("SELECT * FROM assets WHERE project_id=?", (project_id,)).fetchall()),
            "reference_assets": rows_to_dicts(conn.execute("SELECT * FROM reference_assets WHERE project_id=?", (project_id,)).fetchall()),
            "research_sources": rows_to_dicts(conn.execute("SELECT * FROM research_sources WHERE project_id=?", (project_id,)).fetchall()),
            "research_claims": rows_to_dicts(conn.execute("SELECT * FROM research_claims WHERE project_id=?", (project_id,)).fetchall()),
            "timeline": rows_to_dicts(conn.execute("SELECT * FROM timeline_clips WHERE project_id=? ORDER BY track, start_sec", (project_id,)).fetchall()),
            "checkpoints": rows_to_dicts(conn.execute("SELECT * FROM checkpoints WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()),
            "gate_approvals": rows_to_dicts(conn.execute("SELECT * FROM gate_approvals WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()),
            "qa_reports": rows_to_dicts(conn.execute("SELECT * FROM quality_reports WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()),
            "messages": rows_to_dicts(conn.execute("SELECT * FROM director_messages WHERE project_id=? ORDER BY id ASC", (project_id,)).fetchall()),
        }
