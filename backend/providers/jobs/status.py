"""Persist one generation attempt. A missing table is created. A database error does not invent a file."""

from __future__ import annotations

import json
import uuid
from typing import Any

from backend.models import utc_now


def record_generation_job(
    *,
    provider: str,
    tool_name: str,
    state: str,
    prompt: str,
    output_path: str = "",
    estimated_cost_usd: float | None = None,
    error: str = "",
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    job = {
        "id": f"job_{uuid.uuid4().hex[:12]}",
        "provider": provider,
        "tool_name": tool_name,
        "state": state,
        "prompt": prompt[:2000],
        "output_path": output_path,
        "estimated_cost_usd": estimated_cost_usd,
        "error": (error or "")[:1000],
        "persisted": False,
    }
    try:
        from backend.db import get_conn, init_db

        init_db()
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO generation_jobs
                   (id, provider, tool_name, state, prompt, output_path, estimated_cost_usd, error, params_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job["id"], provider, tool_name, state, job["prompt"], output_path,
                    estimated_cost_usd, job["error"], json.dumps(params or {}), utc_now(),
                ),
            )
        job["persisted"] = True
    except Exception as exc:
        job["error"] = job["error"] or str(exc)
    return job


def update_generation_job(
    job_id: str,
    *,
    state: str,
    output_path: str | None = None,
    estimated_cost_usd: float | None = None,
    error: str | None = None,
) -> None:
    """Update an existing generation job's async state, output path, cost, or error."""
    try:
        from backend.db import get_conn, init_db

        init_db()
        with get_conn() as conn:
            conn.execute(
                """UPDATE generation_jobs
                   SET state=?, output_path=COALESCE(?, output_path),
                       estimated_cost_usd=COALESCE(?, estimated_cost_usd),
                       error=COALESCE(?, error)
                   WHERE id=?""",
                (state, output_path, estimated_cost_usd, (error or "")[:1000] if error is not None else None, job_id),
            )
    except Exception:
        pass
