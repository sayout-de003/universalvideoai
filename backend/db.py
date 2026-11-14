"""SQLite persistence layer for Universal AI Video Production Studio."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from backend.config import DB_PATH


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    prompt TEXT NOT NULL,
    category TEXT NOT NULL,
    mode TEXT NOT NULL,
    pipeline_name TEXT NOT NULL,
    render_engine TEXT NOT NULL,
    target_duration_sec REAL NOT NULL,
    aspect_ratio TEXT NOT NULL,
    resolution TEXT NOT NULL,
    fps INTEGER NOT NULL,
    language TEXT NOT NULL,
    subtitle_languages_json TEXT NOT NULL,
    status TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    budget_limit_usd REAL NOT NULL,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    actual_cost_usd REAL NOT NULL DEFAULT 0.0,
    workspace_dir TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    paused INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    target_duration_sec REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'pending',
    rendered_path TEXT
);

CREATE TABLE IF NOT EXISTS sequences (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    sequence_id TEXT NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    script_segment TEXT NOT NULL DEFAULT '',
    narration_segment TEXT NOT NULL DEFAULT '',
    dialogue_json TEXT NOT NULL DEFAULT '[]',
    visual_description TEXT NOT NULL DEFAULT '',
    generation_prompt TEXT NOT NULL DEFAULT '',
    generation_method TEXT NOT NULL DEFAULT 'procedural_animation',
    render_engine TEXT NOT NULL DEFAULT 'ffmpeg',
    provider TEXT NOT NULL DEFAULT 'local',
    character_refs_json TEXT NOT NULL DEFAULT '[]',
    environment_ref TEXT NOT NULL DEFAULT '',
    duration_sec REAL NOT NULL DEFAULT 5.0,
    transition TEXT NOT NULL DEFAULT 'crossfade',
    visual_asset_id TEXT,
    audio_asset_id TEXT,
    rendered_clip_path TEXT,
    quality_status TEXT NOT NULL DEFAULT 'pending',
    approved INTEGER NOT NULL DEFAULT 0,
    manual_locked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shots (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    shot_type TEXT NOT NULL DEFAULT 'medium',
    camera_angle TEXT NOT NULL DEFAULT 'eye_level',
    camera_movement TEXT NOT NULL DEFAULT 'static',
    lighting TEXT NOT NULL DEFAULT 'natural',
    composition TEXT NOT NULL DEFAULT 'rule_of_thirds',
    description TEXT NOT NULL DEFAULT '',
    duration_sec REAL NOT NULL DEFAULT 5.0,
    asset_id TEXT
);

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'supporting',
    visual_description TEXT NOT NULL DEFAULT '',
    facial_features TEXT NOT NULL DEFAULT '',
    body_proportions TEXT NOT NULL DEFAULT '',
    clothing TEXT NOT NULL DEFAULT '',
    accessories TEXT NOT NULL DEFAULT '',
    personality TEXT NOT NULL DEFAULT '',
    voice_id TEXT NOT NULL DEFAULT 'default',
    voice_provider TEXT NOT NULL DEFAULT 'local',
    reference_image_path TEXT,
    relationships_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS speakers (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'narrator',
    voice_provider TEXT NOT NULL DEFAULT 'local',
    voice_id TEXT NOT NULL DEFAULT 'default',
    language TEXT NOT NULL DEFAULT 'en',
    sample_audio_path TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id TEXT,
    asset_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    file_path TEXT NOT NULL,
    duration_sec REAL,
    license TEXT NOT NULL DEFAULT 'generated_local',
    source_url TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_tracks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id TEXT,
    track_role TEXT NOT NULL,
    speaker_id TEXT,
    file_path TEXT NOT NULL,
    start_sec REAL NOT NULL DEFAULT 0.0,
    duration_sec REAL NOT NULL DEFAULT 0.0,
    volume REAL NOT NULL DEFAULT 1.0,
    ducking_db REAL NOT NULL DEFAULT 0.0,
    license TEXT NOT NULL DEFAULT 'generated_local',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS timeline_clips (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    track TEXT NOT NULL,
    scene_id TEXT,
    asset_id TEXT,
    label TEXT NOT NULL DEFAULT '',
    start_sec REAL NOT NULL DEFAULT 0.0,
    duration_sec REAL NOT NULL DEFAULT 5.0,
    in_point_sec REAL NOT NULL DEFAULT 0.0,
    properties_json TEXT NOT NULL DEFAULT '{}',
    manual_edited INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS timeline_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL,
    is_undone INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id TEXT,
    job_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    result_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS render_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id TEXT,
    engine TEXT NOT NULL,
    output_path TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0.0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    human_approved INTEGER NOT NULL DEFAULT 0,
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    approval_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS quality_reports (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    target_path TEXT NOT NULL,
    passed INTEGER NOT NULL,
    checks_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cost_entries (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    operation TEXT NOT NULL,
    estimated_usd REAL NOT NULL DEFAULT 0.0,
    actual_usd REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'estimated',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS director_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    agent_name TEXT NOT NULL DEFAULT 'AI Director',
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creative_briefs (
    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    intake_stage TEXT NOT NULL DEFAULT 'awaiting_type_and_duration',
    video_format TEXT,
    target_duration_sec REAL,
    platform TEXT,
    audience TEXT,
    purpose TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    tone TEXT,
    visual_style TEXT,
    confirmed_fields_json TEXT NOT NULL DEFAULT '{}',
    assumed_fields_json TEXT NOT NULL DEFAULT '{}',
    pending_questions_json TEXT NOT NULL DEFAULT '[]',
    qa_history_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    artifact_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'json',
    content_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT 'system',
    input_versions_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    validation_json TEXT NOT NULL DEFAULT '{}',
    approval_state TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact_comments (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    artifact_name TEXT NOT NULL,
    section_ref TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT 'user',
    comment_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gate_approvals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    gate_name TEXT NOT NULL,
    artifact_name TEXT NOT NULL,
    artifact_version INTEGER NOT NULL,
    artifact_hash TEXT NOT NULL,
    decision TEXT NOT NULL,
    approved_by TEXT NOT NULL DEFAULT 'user',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    publisher TEXT NOT NULL DEFAULT '',
    publication_date TEXT NOT NULL DEFAULT '',
    retrieval_date TEXT NOT NULL,
    source_tier INTEGER NOT NULL DEFAULT 5,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS research_claims (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    source_id TEXT REFERENCES research_sources(id) ON DELETE SET NULL,
    supporting_passage TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.7,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    conflicting_evidence TEXT NOT NULL DEFAULT '',
    fact_check_decision TEXT NOT NULL DEFAULT 'QUALIFY',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reference_assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    intended_role TEXT NOT NULL DEFAULT 'visual_inspiration',
    permissions TEXT NOT NULL DEFAULT 'user_owned',
    analysis_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    architecture TEXT NOT NULL DEFAULT '',
    layout TEXT NOT NULL DEFAULT '',
    time_of_day TEXT NOT NULL DEFAULT 'day',
    lighting TEXT NOT NULL DEFAULT 'natural',
    weather TEXT NOT NULL DEFAULT 'clear',
    color_palette TEXT NOT NULL DEFAULT '',
    environmental_features TEXT NOT NULL DEFAULT '',
    reference_image_path TEXT
);

CREATE TABLE IF NOT EXISTS props (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    expected_state TEXT NOT NULL DEFAULT 'intact',
    continuity_notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS dependency_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_key TEXT NOT NULL,
    dependent_key TEXT NOT NULL,
    invalidated INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for k in list(d.keys()):
        if k.endswith("_json") and isinstance(d[k], str):
            try:
                d[k[:-5]] = json.loads(d[k])
            except json.JSONDecodeError:
                d[k[:-5]] = d[k]
    return d


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [d for r in rows if (d := row_to_dict(r)) is not None]
