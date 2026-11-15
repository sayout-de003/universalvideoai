"""One still-image call. No key means no file."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.integrations.openmontage_adapter import openmontage_adapter
from backend.providers.jobs.status import record_generation_job
from backend.providers.video.openmontage_video import _claim_output, discard_unproven_output

_IMAGE_PROVIDERS = (
    ("google_imagen", "imagen", 0.04, ("GOOGLE_API_KEY",)),
    ("flux_image", "flux", 0.05, ("FAL_KEY", "FAL_AI_API_KEY")),
    ("openai_image", "openai_image", 0.04, ("OPENAI_API_KEY",)),
)


def _configured_image() -> tuple[str, str, float] | None:
    for tool_name, provider_id, cost, keys in _IMAGE_PROVIDERS:
        if any(os.environ.get(key, "").strip() for key in keys):
            return tool_name, provider_id, cost
    return None


def image_provider_readiness() -> list[dict[str, Any]]:
    chosen = _configured_image()
    rows = []
    for tool_name, provider_id, cost, keys in _IMAGE_PROVIDERS:
        configured = chosen is not None and chosen[0] == tool_name
        rows.append({
            "id": provider_id,
            "tool": tool_name,
            "state": "configured" if configured else "not_configured",
            "authenticated": False,
            "production_ready": False,
            "estimated_cost_usd": cost if configured else 0.0,
            "detail": "Credential is set." if configured else f"Set one of: {', '.join(keys)}",
        })
    return rows


def generate_cloud_image(prompt: str, output_path: Path) -> dict[str, Any]:
    chosen = _configured_image()
    if chosen is None or not openmontage_adapter.is_available():
        state = "not_installed" if chosen and not openmontage_adapter.is_available() else "not_configured"
        detail = "No image provider is configured." if state == "not_configured" else "OpenMontage is not on disk."
        job = record_generation_job(provider="none", tool_name="", state=state, prompt=prompt, error=detail)
        return {"ok": False, "status": "NOT_CONFIGURED" if state == "not_configured" else "UNAVAILABLE", "reason": detail, "job_id": job["id"]}

    tool_name, provider_id, cost = chosen
    params = {"prompt": prompt, "output_path": str(output_path)}
    try:
        res = openmontage_adapter.execute_tool(tool_name, params)
    except Exception as exc:
        discard_unproven_output(output_path)
        job = record_generation_job(
            provider=provider_id, tool_name=tool_name, state="failed", prompt=prompt,
            output_path=str(output_path), estimated_cost_usd=cost, error=str(exc), params=params,
        )
        return {"ok": False, "status": "UNAVAILABLE", "reason": str(exc), "job_id": job["id"], "provider": provider_id}

    if res.get("success") and _claim_output(res, output_path):
        job = record_generation_job(
            provider=provider_id, tool_name=tool_name, state="ready", prompt=prompt,
            output_path=str(output_path), estimated_cost_usd=cost, params=params,
        )
        return {
            "ok": True, "status": "READY", "provider": provider_id, "model": tool_name,
            "estimated_cost_usd": cost, "job_id": job["id"], "output": str(output_path),
        }

    discard_unproven_output(output_path)
    error = str(res.get("error") or "image provider returned no file")
    job = record_generation_job(
        provider=provider_id, tool_name=tool_name, state="failed", prompt=prompt,
        output_path=str(output_path), estimated_cost_usd=cost, error=error, params=params,
    )
    return {"ok": False, "status": "UNAVAILABLE", "reason": error, "job_id": job["id"], "provider": provider_id}
