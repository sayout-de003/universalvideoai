"""Pick one configured video provider. A miss is recorded and does not write a stand-in file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.providers.jobs.status import record_generation_job
from backend.providers.video.base import VideoRequest
from backend.providers.video.registry import list_video_providers, video_provider_readiness


def generate_cloud_shot(
    prompt: str,
    output_path: Path,
    duration_sec: float,
    aspect_ratio: str,
) -> dict[str, Any]:
    snapshot = video_provider_readiness()
    chosen = next((provider for provider in list_video_providers() if provider.readiness()["state"] == "configured"), None)
    if chosen is None:
        detail = "No video provider is configured. A fallback clip is not counted as generated footage."
        job = record_generation_job(provider="none", tool_name="", state="not_configured", prompt=prompt, error=detail)
        return {
            "ok": False,
            "status": "NOT_CONFIGURED",
            "generation_state": "not_configured",
            "source_type": "cloud_ai_video",
            "provider": None,
            "model": None,
            "job_id": job["id"],
            "estimated_cost_usd": 0.0,
            "reason": detail,
            "providers": snapshot,
        }

    result = chosen.generate(VideoRequest(
        prompt=prompt,
        output_path=output_path,
        duration_sec=duration_sec,
        aspect_ratio=aspect_ratio,
    ))
    result.attempts = snapshot
    return result.as_shot()
