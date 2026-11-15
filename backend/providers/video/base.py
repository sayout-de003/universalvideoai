"""Shared request and result for every cloud or local video provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VideoRequest:
    prompt: str
    output_path: Path
    duration_sec: float
    aspect_ratio: str


@dataclass
class VideoResult:
    ok: bool
    state: str
    provider_id: str
    tool_name: str
    model: str
    estimated_cost_usd: float
    error: str = ""
    job_id: str = ""
    output_path: str = ""
    attempts: list[dict[str, Any]] = field(default_factory=list)

    def as_shot(self) -> dict[str, Any]:
        status = "READY" if self.ok else ("NOT_CONFIGURED" if self.state == "not_configured" else "UNAVAILABLE")
        if self.state == "capability_unsupported":
            status = "CAPABILITY_UNSUPPORTED"
        shot: dict[str, Any] = {
            "ok": self.ok,
            "status": status,
            "generation_state": self.state,
            "source_type": "cloud_ai_video",
            "provider": self.provider_id or None,
            "model": self.model or None,
            "tool_name": self.tool_name or None,
            "estimated_cost_usd": self.estimated_cost_usd,
            "job_id": self.job_id or None,
            "reason": self.error or None,
            "providers": self.attempts,
        }
        if self.ok:
            shot["engine"] = self.provider_id
            shot["output"] = self.output_path
        return shot
