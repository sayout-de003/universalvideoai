"""Phase 1: Shared Creative Intake Service (Creative Brief Analyst + Format & Visual Style Director)."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from backend.config import PROJECTS_DIR
from backend.db import get_conn, row_to_dict, rows_to_dicts
from backend.models import ProductionStage, utc_now
from backend.orchestration.engine_registry import (
    VISUAL_STYLE_PROFILES,
    is_free_open_source_mode,
    resolve_visual_style_profile,
)
from backend.services.format_catalog import FORMAT_CATALOG, get_format_spec, resolve_format


def parse_duration_seconds(text: str) -> float | None:
    from backend.services.document_parser import parse_structured_screenplay

    parsed = parse_structured_screenplay(text)
    if parsed.get("is_structured") and parsed.get("duration_sec"):
        return max(5.0, float(parsed["duration_sec"]))

    lower = text.lower()
    m_rt = re.search(r"runtime\s*:\s*(\d+(?:\.\d+)?)\s*s", lower)
    if m_rt:
        return max(5.0, float(m_rt.group(1)))
    m_hr = re.search(r"(\d+(?:\.\d+)?)[\s-]*(?:hour|hr)s?", lower)
    m_min = re.search(r"(\d+(?:\.\d+)?)[\s-]*(?:minute|min)s?", lower)
    m_sec = re.search(r"(\d+(?:\.\d+)?)[\s-]*(?:second|sec)s?", lower)
    if m_hr:
        return max(5.0, float(m_hr.group(1)) * 3600.0)
    if m_min:
        return max(5.0, float(m_min.group(1)) * 60.0)
    if m_sec:
        return max(5.0, float(m_sec.group(1)))
    return None


def extract_clean_title(prompt: str) -> str:
    from backend.services.document_parser import parse_structured_screenplay

    parsed = parse_structured_screenplay(prompt)
    if parsed.get("title"):
        return str(parsed["title"])[:80]

    first_line = prompt.strip().splitlines()[0] if prompt.strip() else ""
    cleaned = re.sub(r"^[#*\s]+", "", first_line)
    cleaned = re.sub(r"\*Format:.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(
        r"^(?:i want to (?:create|make|produce)|create|make|produce|generate|build)\s+(?:a|an|the)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:(?:\d+[\s-]*(?:minute|min|second|sec|hour|hr)s?\s+)|(?:cinematic|short|long|animated|educational)\s+)*(?:documentary|video|film|reel|short|commercial|ad|explainer|trailer|screenplay|animation)\s*(?::|about|on|for|of)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    words = [w for w in re.split(r"\s+", cleaned.strip().rstrip(".,!?*#")) if w]
    title = " ".join(words[:9]).strip()
    return title[:1].upper() + title[1:] if title else "Untitled Production"


def interpret_prompt_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Interpret a prompt + preferences + reference count into a structured production configuration preview."""
    prompt = str(payload.get("prompt") or "").strip()
    prefs = dict(payload.get("preferences") or {})
    refs = list(payload.get("references") or [])
    uploads = list(payload.get("uploads") or [])

    inferred_fmt = resolve_format(str(prefs.get("format") or payload.get("video_format") or prompt))
    fmt_spec = get_format_spec(inferred_fmt)
    parsed_dur = (
        float(prefs["target_duration_sec"])
        if prefs.get("target_duration_sec")
        else (
            float(payload["target_duration_sec"])
            if payload.get("target_duration_sec")
            else parse_duration_seconds(prompt)
        )
    )
    effective_dur = parsed_dur or float(fmt_spec["default_duration_sec"])
    visual_style = resolve_visual_style_profile(
        str(prefs.get("visual_style") or payload.get("visual_style") or prompt)
    )
    style_spec = VISUAL_STYLE_PROFILES.get(visual_style, VISUAL_STYLE_PROFILES["2d_illustrated"])
    prod_mode = str(payload.get("production_mode") or prefs.get("production_mode") or "hybrid")
    platform = str(
        prefs.get("target_platform")
        or ("YouTube" if fmt_spec["aspect_ratio"] == "16:9" else "Instagram Reels / YouTube Shorts")
    )
    audience = str(prefs.get("audience") or "General audience")
    language = str(prefs.get("language") or payload.get("language") or "en")
    research_req = bool(
        prefs.get("research_required")
        if "research_required" in prefs
        else (fmt_spec.get("requires_research") or any(k in prompt.lower() for k in ("documentary", "history", "fact", "science", "accurate")))
    )

    missing_questions: list[dict[str, Any]] = []
    if parsed_dur is None:
        missing_questions.append({
            "id": "target_duration_sec",
            "question": "How long should the finished video be?",
            "suggested": f"{int(effective_dur)} seconds",
        })

    return {
        "ok": True,
        "title": payload.get("title") or extract_clean_title(prompt),
        "summary": {
            "format_key": inferred_fmt,
            "format_label": fmt_spec["label"],
            "target_duration_sec": effective_dur,
            "duration_missing_in_prompt": parsed_dur is None,
            "audience": audience,
            "platform": platform,
            "language": language,
            "visual_style": visual_style,
            "visual_style_label": style_spec["label"],
            "narration_style": "Cinematic documentary" if fmt_spec["category"] == "documentary" else "Dynamic Dual Human Neural",
            "research_required": research_req,
            "reference_links_count": len(refs),
            "uploads_count": len(uploads),
            "production_mode": prod_mode,
            "free_open_source_enforced": is_free_open_source_mode(prod_mode),
            "quality_target": "High",
        },
        "missing_questions": missing_questions,
    }


def start_intake(
    prompt: str,
    title: str | None = None,
    language: str = "en",
    preferences: dict[str, Any] | None = None,
    references: list[dict[str, Any]] | None = None,
    uploads: list[dict[str, Any]] | None = None,
    production_mode: str | None = None,
) -> dict[str, Any]:
    """Create a project in guided intake state, ingest any initial references, and identify missing decisions."""
    from backend.services.reference_service import register_and_analyze_reference, register_url_reference

    prefs = dict(preferences or {})
    project_id = f"proj_{uuid.uuid4().hex[:10]}"
    ws = PROJECTS_DIR / project_id
    for sub in ("assets", "audio", "stems", "renders", "subtitles", "exports", "deliverables", "package", "references"):
        (ws / sub).mkdir(parents=True, exist_ok=True)

    inferred_fmt = resolve_format(str(prefs.get("format") or prompt))
    fmt_spec = get_format_spec(inferred_fmt)
    parsed_dur = float(prefs["target_duration_sec"]) if prefs.get("target_duration_sec") else parse_duration_seconds(prompt)
    visual_style = resolve_visual_style_profile(str(prefs.get("visual_style") or prompt))
    prod_mode = str(production_mode or prefs.get("production_mode") or "hybrid")
    clean_title = title or extract_clean_title(prompt)
    now = utc_now()

    confirmed: dict[str, Any] = {
        "idea": prompt.strip(),
        "language": prefs.get("language") or language,
        "visual_style": visual_style,
        "production_mode": prod_mode,
    }
    if prefs.get("format"):
        confirmed["video_format"] = inferred_fmt
    if parsed_dur is not None:
        confirmed["target_duration_sec"] = parsed_dur
    if prefs.get("target_platform"):
        confirmed["platform"] = prefs["target_platform"]
    if prefs.get("audience"):
        confirmed["audience"] = prefs["audience"]

    assumed: dict[str, Any] = {
        "suggested_format": inferred_fmt,
        "suggested_duration_sec": parsed_dur or fmt_spec["default_duration_sec"],
        "visual_style": visual_style,
    }

    initial_questions = [
        {
            "id": "video_format",
            "question": "1. What type of video do you want?",
            "suggested": fmt_spec["label"],
            "options": [v["label"] for k, v in list(FORMAT_CATALOG.items())[:10]],
        },
        {
            "id": "target_duration_sec",
            "question": "2. How long should the video be?",
            "suggested": f"{int(parsed_dur or fmt_spec['default_duration_sec'])} seconds",
        },
    ]

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO projects
               (id, title, prompt, category, mode, pipeline_name, render_engine, target_duration_sec,
                aspect_ratio, resolution, fps, language, subtitle_languages_json, status, current_stage,
                budget_limit_usd, workspace_dir, visual_style, production_mode_policy, metadata_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id, clean_title, prompt, fmt_spec["category"], prod_mode, fmt_spec["pipeline"],
                "ffmpeg", parsed_dur or fmt_spec["default_duration_sec"],
                fmt_spec["aspect_ratio"], fmt_spec["resolution"], 30, language,
                json.dumps([language]), "intake", ProductionStage.IDEA.value,
                0.0 if is_free_open_source_mode(prod_mode) else 10.0,
                str(ws), visual_style, prod_mode,
                json.dumps({"format_key": inferred_fmt, "visual_style": visual_style, "production_mode": prod_mode}),
                now, now,
            ),
        )
        conn.execute(
            "INSERT INTO production_runs (id, project_id, status, current_stage, paused, started_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (f"run_{uuid.uuid4().hex[:10]}", project_id, "intake", ProductionStage.IDEA.value, now, now),
        )
        conn.execute(
            """INSERT INTO creative_briefs
               (project_id, version, intake_stage, video_format, target_duration_sec, platform, audience, language,
                visual_style, confirmed_fields_json, assumed_fields_json, pending_questions_json, qa_history_json, updated_at)
               VALUES (?, 1, 'awaiting_type_and_duration', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id, inferred_fmt, parsed_dur or fmt_spec["default_duration_sec"],
                confirmed.get("platform"), confirmed.get("audience"), language, visual_style,
                json.dumps(confirmed), json.dumps(assumed), json.dumps(initial_questions),
                json.dumps([{"role": "user", "text": prompt}]), now,
            ),
        )

    for ref in references or []:
        url = str(ref.get("url") or "").strip() if isinstance(ref, dict) else str(ref).strip()
        if url:
            register_url_reference(
                project_id,
                ws,
                url,
                roles=ref.get("roles") if isinstance(ref, dict) else None,
                intended_role=str(ref.get("purpose") or ref.get("role") or "VISUAL_STYLE") if isinstance(ref, dict) else "VISUAL_STYLE",
                user_notes=str(ref.get("user_notes") or "") if isinstance(ref, dict) else "",
            )

    for up in uploads or []:
        if isinstance(up, dict) and up.get("file_path"):
            fp = Path(str(up["file_path"]))
            if fp.is_file():
                register_and_analyze_reference(
                    project_id,
                    ws,
                    fp,
                    intended_role=str(up.get("purpose") or up.get("role") or "VISUAL_STYLE"),
                    roles=up.get("roles"),
                    user_notes=str(up.get("user_notes") or ""),
                )

    return get_intake_state(project_id)


def submit_intake_answers(project_id: str, answers: dict[str, Any]) -> dict[str, Any]:
    """Advance conversational intake: confirm video type + duration, then ask only relevant follow-ups."""
    with get_conn() as conn:
        brief = row_to_dict(conn.execute("SELECT * FROM creative_briefs WHERE project_id=?", (project_id,)).fetchone())
        proj = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
    if not brief or not proj:
        return {"ok": False, "error": f"Project '{project_id}' not found"}

    confirmed = dict(brief.get("confirmed_fields") or {})
    assumed = dict(brief.get("assumed_fields") or {})
    history = list(brief.get("qa_history") or [])
    history.append({"role": "user", "answers": answers})

    video_format = brief.get("video_format")
    if "video_format" in answers and answers["video_format"]:
        video_format = resolve_format(str(answers["video_format"]))
        confirmed["video_format"] = video_format
        assumed.pop("suggested_format", None)

    target_dur = brief.get("target_duration_sec")
    if "target_duration_sec" in answers and answers["target_duration_sec"] is not None:
        raw_dur = answers["target_duration_sec"]
        parsed = float(raw_dur) if isinstance(raw_dur, (int, float)) else (parse_duration_seconds(str(raw_dur)) or 60.0)
        target_dur = max(5.0, parsed)
        confirmed["target_duration_sec"] = target_dur
        assumed.pop("suggested_duration_sec", None)

    for k in ("platform", "audience", "purpose", "language", "tone", "visual_style", "references_note", "production_mode"):
        if answers.get(k):
            confirmed[k] = answers[k]

    fmt_spec = get_format_spec(video_format or "documentaries")
    pending: list[dict[str, Any]] = []
    if "video_format" not in confirmed:
        pending.append({"id": "video_format", "question": "1. What type of video do you want?", "suggested": fmt_spec["label"]})
    if "target_duration_sec" not in confirmed:
        pending.append({"id": "target_duration_sec", "question": "2. How long should the video be?", "suggested": f"{int(fmt_spec['default_duration_sec'])} seconds"})

    if not pending:
        if "platform" not in confirmed:
            pending.append({"id": "platform", "question": "What is the target platform?", "suggested": "YouTube" if fmt_spec["aspect_ratio"] == "16:9" else "Instagram / Shorts"})
        if "audience" not in confirmed:
            pending.append({"id": "audience", "question": "Who is the intended audience?", "suggested": "General curious viewers"})
        if "tone" not in confirmed:
            pending.append({"id": "tone", "question": "What tone or visual style do you prefer?", "suggested": "Cinematic and authoritative" if fmt_spec["category"] == "documentary" else "Modern and engaging"})
        if "references_note" not in confirmed and "skip_followups" not in answers:
            pending.append({"id": "references_note", "question": "Do you have any references, images, videos, logos, or characters to upload/use?", "suggested": "None yet"})

    if answers.get("confirm_brief") or not pending:
        intake_stage = "brief_confirmed"
        pending = []
        for opt_k, default_v in [
            ("platform", "YouTube" if fmt_spec["aspect_ratio"] == "16:9" else "Instagram Reels / Shorts"),
            ("audience", "General audience"),
            ("purpose", f"Deliver a high-retention {fmt_spec['label']}"),
            ("tone", "Cinematic, authentic, well-paced"),
            ("visual_style", confirmed.get("visual_style") or brief.get("visual_style") or fmt_spec["category"]),
        ]:
            if opt_k not in confirmed:
                assumed[opt_k] = default_v
    else:
        intake_stage = "awaiting_followups" if ("video_format" in confirmed and "target_duration_sec" in confirmed) else "awaiting_type_and_duration"

    visual_style = resolve_visual_style_profile(str(confirmed.get("visual_style") or assumed.get("visual_style") or proj.get("visual_style") or "auto"))
    prod_mode = str(confirmed.get("production_mode") or proj.get("production_mode_policy") or "hybrid")
    now = utc_now()
    with get_conn() as conn:
        conn.execute(
            """UPDATE creative_briefs
               SET version=version+1, intake_stage=?, video_format=?, target_duration_sec=?,
                   platform=?, audience=?, purpose=?, language=?, tone=?, visual_style=?,
                   confirmed_fields_json=?, assumed_fields_json=?, pending_questions_json=?, qa_history_json=?, updated_at=?
               WHERE project_id=?""",
            (
                intake_stage, video_format, target_dur,
                confirmed.get("platform") or assumed.get("platform"),
                confirmed.get("audience") or assumed.get("audience"),
                confirmed.get("purpose") or assumed.get("purpose"),
                confirmed.get("language", brief.get("language", "en")),
                confirmed.get("tone") or assumed.get("tone"),
                visual_style,
                json.dumps(confirmed), json.dumps(assumed), json.dumps(pending), json.dumps(history), now, project_id,
            ),
        )
        conn.execute(
            """UPDATE projects SET category=?, pipeline_name=?, target_duration_sec=?, aspect_ratio=?, resolution=?,
               language=?, status=?, visual_style=?, production_mode_policy=?, metadata_json=?, updated_at=? WHERE id=?""",
            (
                fmt_spec["category"], fmt_spec["pipeline"], float(target_dur or fmt_spec["default_duration_sec"]),
                fmt_spec["aspect_ratio"], fmt_spec["resolution"], confirmed.get("language", proj["language"]),
                "brief_confirmed" if intake_stage == "brief_confirmed" else "intake",
                visual_style, prod_mode,
                json.dumps({**(proj.get("metadata") or {}), "format_key": fmt_spec["format_key"], "visual_style": visual_style, "production_mode": prod_mode}),
                now, project_id,
            ),
        )

    return get_intake_state(project_id)


def approve_production_brief(
    project_id: str,
    overrides: dict[str, Any] | None = None,
    edits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Approve the creative brief and ensure full hierarchy, script, storyboard, and Production Bible exist."""
    from backend.orchestration.director import _plan_hierarchy_and_bible, get_project_detail
    from backend.orchestration.engine_registry import select_render_engine

    merged_overrides = {**(overrides or {}), **(edits or {})}
    payload = {**merged_overrides, "confirm_brief": True, "skip_followups": True}
    state = submit_intake_answers(project_id, payload)
    if not state.get("ok"):
        return state

    detail = get_project_detail(project_id)
    if not detail:
        return {"ok": False, "error": "Project not found"}

    proj = detail["project"]
    brief = detail.get("creative_brief") or {}
    fmt_key = brief.get("video_format") or (proj.get("metadata") or {}).get("format_key") or "documentaries"
    visual_style = proj.get("visual_style") or brief.get("visual_style") or "2d_illustrated"
    prod_mode = proj.get("production_mode_policy") or proj.get("mode") or "hybrid"

    if not detail.get("scenes") or merged_overrides.get("replan"):
        engine, _ = select_render_engine(proj["category"], proj["prompt"], visual_style=visual_style)
        _plan_hierarchy_and_bible(
            project_id=project_id,
            title=proj["title"],
            prompt=proj["prompt"],
            category=proj["category"],
            target_dur=float(proj["target_duration_sec"]),
            render_engine=engine,
            language=proj["language"],
            fmt_key=fmt_key,
            visual_style=visual_style,
            production_mode=prod_mode,
        )
        with get_conn() as conn:
            conn.execute("UPDATE projects SET status='planned', render_engine=?, updated_at=? WHERE id=?", (engine, utc_now(), project_id))

    return {"ok": True, "project_id": project_id, "intake": get_intake_state(project_id), "project": get_project_detail(project_id)}


def get_intake_state(project_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        brief = row_to_dict(conn.execute("SELECT * FROM creative_briefs WHERE project_id=?", (project_id,)).fetchone())
        proj = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
        refs = rows_to_dicts(conn.execute("SELECT * FROM reference_assets WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall())
    if not brief or not proj:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    fmt_spec = get_format_spec(brief.get("video_format") or "documentaries")
    return {
        "ok": True,
        "project_id": project_id,
        "title": proj["title"],
        "intake_stage": brief["intake_stage"],
        "format_spec": fmt_spec,
        "visual_style": proj.get("visual_style") or brief.get("visual_style") or "2d_illustrated",
        "production_mode": proj.get("production_mode_policy") or proj.get("mode") or "hybrid",
        "references_count": len(refs),
        "references": refs,
        "confirmed": brief.get("confirmed_fields", {}),
        "assumed": brief.get("assumed_fields", {}),
        "pending_questions": brief.get("pending_questions", []),
        "brief": brief,
    }
