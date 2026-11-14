"""12-track Multitrack NLE Timeline Manager with Undo/Redo and non-destructive scene sync."""

from __future__ import annotations

import json
import uuid
from typing import Any

from backend.db import get_conn, rows_to_dicts
from backend.models import TimelineClipOp, utc_now


def _save_snapshot(conn: Any, project_id: str) -> None:
    clips = rows_to_dicts(conn.execute("SELECT * FROM timeline_clips WHERE project_id=? ORDER BY track, start_sec", (project_id,)).fetchall())
    conn.execute("DELETE FROM timeline_history WHERE project_id=? AND is_undone=1", (project_id,))
    conn.execute("INSERT INTO timeline_history (project_id, snapshot_json, is_undone, created_at) VALUES (?, ?, 0, ?)", (project_id, json.dumps(clips), utc_now()))


def get_timeline(project_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM timeline_clips WHERE project_id=? ORDER BY track, start_sec", (project_id,)).fetchall())


def apply_timeline_op(project_id: str, op: TimelineClipOp) -> dict[str, Any]:
    with get_conn() as conn:
        _save_snapshot(conn, project_id)
        if op.operation == "add":
            clip_id = f"clip_{uuid.uuid4().hex[:10]}"
            conn.execute(
                """INSERT INTO timeline_clips (id, project_id, track, scene_id, asset_id, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (clip_id, project_id, op.track.value if op.track else "main_video", op.scene_id, op.asset_id, op.label or "Clip", op.start_sec or 0.0, op.duration_sec or 5.0, op.in_point_sec or 0.0, json.dumps(op.properties)),
            )
            return {"ok": True, "clip_id": clip_id, "clips": rows_to_dicts(conn.execute("SELECT * FROM timeline_clips WHERE project_id=? ORDER BY track, start_sec", (project_id,)).fetchall())}

        if not op.clip_id:
            return {"ok": False, "error": "clip_id required"}
        row = conn.execute("SELECT * FROM timeline_clips WHERE id=? AND project_id=?", (op.clip_id, project_id)).fetchone()
        if not row:
            return {"ok": False, "error": f"Clip '{op.clip_id}' not found"}

        if op.operation == "move":
            conn.execute("UPDATE timeline_clips SET start_sec=?, track=?, manual_edited=1 WHERE id=?", (max(0.0, float(op.start_sec if op.start_sec is not None else row["start_sec"])), op.track.value if op.track else row["track"], op.clip_id))
        elif op.operation == "trim":
            conn.execute("UPDATE timeline_clips SET duration_sec=?, in_point_sec=?, manual_edited=1 WHERE id=?", (max(0.2, float(op.duration_sec if op.duration_sec is not None else row["duration_sec"])), max(0.0, float(op.in_point_sec if op.in_point_sec is not None else row["in_point_sec"])), op.clip_id))
        elif op.operation == "split":
            split_at = float(op.split_at_sec if op.split_at_sec is not None else row["duration_sec"] / 2.0)
            if split_at <= 0.1 or split_at >= row["duration_sec"] - 0.1:
                return {"ok": False, "error": "split_at_sec must be inside clip duration"}
            conn.execute("UPDATE timeline_clips SET duration_sec=?, manual_edited=1 WHERE id=?", (split_at, op.clip_id))
            conn.execute(
                """INSERT INTO timeline_clips (id, project_id, track, scene_id, asset_id, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (f"clip_{uuid.uuid4().hex[:10]}", project_id, row["track"], row["scene_id"], row["asset_id"], f"{row['label']} (B)", row["start_sec"] + split_at, row["duration_sec"] - split_at, row["in_point_sec"] + split_at, row["properties_json"]),
            )
        elif op.operation == "duplicate":
            conn.execute(
                """INSERT INTO timeline_clips (id, project_id, track, scene_id, asset_id, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (f"clip_{uuid.uuid4().hex[:10]}", project_id, row["track"], row["scene_id"], row["asset_id"], f"{row['label']} (Copy)", row["start_sec"] + row["duration_sec"], row["duration_sec"], row["in_point_sec"], row["properties_json"]),
            )
        elif op.operation == "delete":
            conn.execute("DELETE FROM timeline_clips WHERE id=?", (op.clip_id,))
        elif op.operation == "ripple_delete":
            conn.execute("DELETE FROM timeline_clips WHERE id=?", (op.clip_id,))
            conn.execute("UPDATE timeline_clips SET start_sec = MAX(0.0, start_sec - ?), manual_edited=1 WHERE project_id=? AND track=? AND start_sec > ?", (row["duration_sec"], project_id, row["track"], row["start_sec"]))
        elif op.operation == "update_props":
            props = json.loads(row["properties_json"] or "{}")
            props.update(op.properties)
            conn.execute("UPDATE timeline_clips SET properties_json=?, manual_edited=1 WHERE id=?", (json.dumps(props), op.clip_id))
        else:
            return {"ok": False, "error": f"Unknown timeline operation '{op.operation}'"}

        clips = rows_to_dicts(conn.execute("SELECT * FROM timeline_clips WHERE project_id=? ORDER BY track, start_sec", (project_id,)).fetchall())
        return {"ok": True, "clips": clips}


def undo_timeline(project_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        last = conn.execute("SELECT * FROM timeline_history WHERE project_id=? AND is_undone=0 ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
        if not last:
            return {"ok": False, "error": "Nothing to undo"}
        snapshot = json.loads(last["snapshot_json"])
        conn.execute("UPDATE timeline_history SET is_undone=1 WHERE id=?", (last["id"],))
        conn.execute("DELETE FROM timeline_clips WHERE project_id=?", (project_id,))
        for c in snapshot:
            conn.execute(
                """INSERT INTO timeline_clips (id, project_id, track, scene_id, asset_id, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (c["id"], c["project_id"], c["track"], c.get("scene_id"), c.get("asset_id"), c["label"], c["start_sec"], c["duration_sec"], c["in_point_sec"], json.dumps(c.get("properties", {})), c.get("manual_edited", 0)),
            )
        return {"ok": True, "clips": snapshot}


def redo_timeline(project_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        nxt = conn.execute("SELECT * FROM timeline_history WHERE project_id=? AND is_undone=1 ORDER BY id ASC LIMIT 1", (project_id,)).fetchone()
        if not nxt:
            return {"ok": False, "error": "Nothing to redo"}
        snapshot = json.loads(nxt["snapshot_json"])
        conn.execute("UPDATE timeline_history SET is_undone=0 WHERE id=?", (nxt["id"],))
        conn.execute("DELETE FROM timeline_clips WHERE project_id=?", (project_id,))
        for c in snapshot:
            conn.execute(
                """INSERT INTO timeline_clips (id, project_id, track, scene_id, asset_id, label, start_sec, duration_sec, in_point_sec, properties_json, manual_edited)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (c["id"], c["project_id"], c["track"], c.get("scene_id"), c.get("asset_id"), c["label"], c["start_sec"], c["duration_sec"], c["in_point_sec"], json.dumps(c.get("properties", {})), c.get("manual_edited", 0)),
            )
        return {"ok": True, "clips": snapshot}
