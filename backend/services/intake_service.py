"""Phase 1: Creative Intake Service (Creative Brief Analyst + Format Director)."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from backend.config import PROJECTS_DIR
from backend.db import get_conn, row_to_dict
from backend.models import ProductionStage, utc_now
from backend.services.format_catalog import FORMAT_CATALOG, get_format_spec, resolve_format


def parse_duration_seconds(text: str) -> float | None:
    lower = text.lower()
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
    cleaned = re.sub(
        r"^(?:i want to (?:create|make|produce)|create|make|produce|generate|build)\s+(?:a|an|the)?\s*",
        "",
        prompt.strip(),
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:(?:cinematic|short|long|animated|educational)\s+)*(?:documentary|video|film|reel|short|commercial|ad|explainer|trailer)\s+(?:about|on|for|of)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    words = [w for w in re.split(r"\s+", cleaned.strip().rstrip(".,!?")) if w]
    title = " ".join(words[:9]).strip()
    return title[:1].upper() + title[1:] if title else "Untitled Production"


def start_intake(prompt: str, title: str | None = None, language: str = "en") -> dict[str, Any]:
    """Create a project in guided intake state and ask ONLY video type & duration first."""
    project_id = f"proj_{uuid.uuid4().hex[:10]}"
    ws = PROJECTS_DIR / project_id
    for sub in ("assets", "audio", "stems", "renders", "subtitles", "exports", "deliverables", "package", "references"):
        (ws / sub).mkdir(parents=True, exist_ok=True)

    inferred_fmt = resolve_format(prompt)
    fmt_spec = get_format_spec(inferred_fmt)
    parsed_dur = parse_duration_seconds(prompt)
    clean_title = title or extract_clean_title(prompt)
    now = utc_now()

    confirmed: dict[str, Any] = {"idea": prompt.strip(), "language": language}
    assumed: dict[str, Any] = {"suggested_format": inferred_fmt, "suggested_duration_sec": parsed_dur or fmt_spec["default_duration_sec"]}

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
                budget_limit_usd, workspace_dir, metadata_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id, clean_title, prompt, fmt_spec["category"], "hybrid", fmt_spec["pipeline"],
                "ffmpeg", parsed_dur or fmt_spec["default_duration_sec"],
                fmt_spec["aspect_ratio"], fmt_spec["resolution"], 30, language,
                json.dumps([language]), "intake", ProductionStage.IDEA.value,
                10.0, str(ws), json.dumps({"format_key": inferred_fmt}), now, now,
            ),
        )
        conn.execute(
            "INSERT INTO production_runs (id, project_id, status, current_stage, paused, started_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (f"run_{uuid.uuid4().hex[:10]}", project_id, "intake", ProductionStage.IDEA.value, now, now),
        )
        conn.execute(
            """INSERT INTO creative_briefs
               (project_id, version, intake_stage, video_format, target_duration_sec, language,
                confirmed_fields_json, assumed_fields_json, pending_questions_json, qa_history_json, updated_at)
               VALUES (?, 1, 'awaiting_type_and_duration', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id, inferred_fmt, parsed_dur or fmt_spec["default_duration_sec"], language,
                json.dumps(confirmed), json.dumps(assumed), json.dumps(initial_questions),
                json.dumps([{"role": "user", "text": prompt}]), now,
            ),
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

    for k in ("platform", "audience", "purpose", "language", "tone", "visual_style", "references_note"):
        if answers.get(k):
            confirmed[k] = answers[k]

    fmt_spec = get_format_spec(video_format or "documentaries")
    # Adaptive follow-up questions based on what is still unconfirmed
    pending: list[dict[str, Any]] = []
    if "video_format" not in confirmed:
        pending.append({"id": "video_format", "question": "1. What type of video do you want?", "suggested": fmt_spec["label"]})
    if "target_duration_sec" not in confirmed:
        pending.append({"id": "target_duration_sec", "question": "2. How long should the video be?", "suggested": f"{int(fmt_spec['default_duration_sec'])} seconds"})

    if not pending:
        # Stage 1 confirmed -> ask only relevant follow-ups if not yet answered
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
        # Populate explicit assumptions for any skipped optional fields
        for opt_k, default_v in [
            ("platform", "YouTube" if fmt_spec["aspect_ratio"] == "16:9" else "Instagram Reels / Shorts"),
            ("audience", "General audience"),
            ("purpose", f"Deliver a high-retention {fmt_spec['label']}"),
            ("tone", "Cinematic, authentic, well-paced"),
            ("visual_style", fmt_spec["category"]),
        ]:
            if opt_k not in confirmed:
                assumed[opt_k] = default_v
    else:
        intake_stage = "awaiting_followups" if ("video_format" in confirmed and "target_duration_sec" in confirmed) else "awaiting_type_and_duration"

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
                confirmed.get("visual_style") or assumed.get("visual_style"),
                json.dumps(confirmed), json.dumps(assumed), json.dumps(pending), json.dumps(history), now, project_id,
            ),
        )
        conn.execute(
            """UPDATE projects SET category=?, pipeline_name=?, target_duration_sec=?, aspect_ratio=?, resolution=?,
               language=?, status=?, metadata_json=?, updated_at=? WHERE id=?""",
            (
                fmt_spec["category"], fmt_spec["pipeline"], float(target_dur or fmt_spec["default_duration_sec"]),
                fmt_spec["aspect_ratio"], fmt_spec["resolution"], confirmed.get("language", proj["language"]),
                "brief_confirmed" if intake_stage == "brief_confirmed" else "intake",
                json.dumps({**(proj.get("metadata") or {}), "format_key": fmt_spec["format_key"]}), now, project_id,
            ),
        )

    return get_intake_state(project_id)


def get_intake_state(project_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        brief = row_to_dict(conn.execute("SELECT * FROM creative_briefs WHERE project_id=?", (project_id,)).fetchone())
        proj = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
    if not brief or not proj:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    fmt_spec = get_format_spec(brief.get("video_format") or "documentaries")
    return {
        "ok": True,
        "project_id": project_id,
        "title": proj["title"],
        "intake_stage": brief["intake_stage"],
        "format_spec": fmt_spec,
        "confirmed": brief.get("confirmed_fields", {}),
        "assumed": brief.get("assumed_fields", {}),
        "pending_questions": brief.get("pending_questions", []),
        "brief": brief,
    }
