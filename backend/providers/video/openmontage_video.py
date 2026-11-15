"""One OpenMontage tool call per provider. No file is kept unless the tool returns a real video."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from backend.integrations.openmontage_adapter import openmontage_adapter
from backend.providers.jobs.status import record_generation_job, update_generation_job
from backend.providers.video.base import VideoRequest, VideoResult

# A provider id lands here only after a generate() call kept a real file.
_PROVEN: set[str] = set()


def cloud_duration(tool_name: str, duration_sec: float) -> str | int:
    seconds = max(4, min(10, int(round(duration_sec))))
    if tool_name == "veo_video":
        return "8s" if seconds >= 6 else "4s"
    if tool_name in ("kling_video", "kling_official_video"):
        return "10" if seconds >= 8 else "5"
    return seconds


def _claim_output(res: dict[str, Any], output_path: Path) -> bool:
    if output_path.is_file() and output_path.stat().st_size > 1024:
        return True
    candidates: list[str] = []
    artifacts = res.get("artifacts") or []
    if isinstance(artifacts, dict):
        candidates.extend(str(v) for v in artifacts.values())
    elif isinstance(artifacts, list):
        candidates.extend(str(v) for v in artifacts)
    meta = res.get("metadata") or {}
    if isinstance(meta, dict):
        for key in ("output", "output_path", "path"):
            if meta.get(key):
                candidates.append(str(meta[key]))
    for raw in candidates:
        src = Path(raw)
        if src.is_file() and src.stat().st_size > 1024:
            if src.resolve() != output_path.resolve():
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, output_path)
            return output_path.is_file() and output_path.stat().st_size > 1024
    return False


def discard_unproven_output(path: Path) -> None:
    if path.is_file():
        path.unlink(missing_ok=True)


def validate_video_with_ffprobe(path: Path) -> dict[str, Any]:
    """Verify a downloaded cloud video has a valid video stream and positive duration."""
    if not path.is_file() or path.stat().st_size < 1024:
        return {"ok": False, "reason": f"Video file missing or too small: {path}"}
    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            text=True,
            timeout=20,
        )
        data = json.loads(raw)
        v_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
        dur = float(data.get("format", {}).get("duration", 0.0) or 0.0)
        if not v_streams or dur <= 0.1:
            return {"ok": False, "reason": "No valid video stream or zero duration"}
        return {"ok": True, "duration_sec": dur, "width": v_streams[0].get("width"), "height": v_streams[0].get("height")}
    except Exception as exc:
        return {"ok": False, "reason": f"ffprobe validation failed: {exc}"}


def _is_transient_error(err: str) -> bool:
    low = (err or "").lower()
    return any(k in low for k in ("timeout", "timed out", "rate limit", "429", "502", "503", "504", "temporarily"))


class OpenMontageVideoProvider:
    provider_id = ""
    tool_name = ""
    env_any: tuple[str, ...] = ()
    model = ""
    estimated_cost_usd = 0.0

    def active_tool(self) -> str | None:
        if any(os.environ.get(key, "").strip() for key in self.env_any):
            return self.tool_name
        return None

    def readiness(self) -> dict[str, Any]:
        tool = self.active_tool()
        if not tool:
            return self._status("not_configured", self.tool_name, f"Set one of: {', '.join(self.env_any)}")
        if not openmontage_adapter.is_available():
            return self._status("not_installed", tool, "OpenMontage tool registry is not on disk.")
        proven = self.provider_id in _PROVEN
        return self._status(
            "configured",
            tool,
            "Credential is set. The provider has not been authenticated by a successful render in this process.",
            production_ready=proven,
        )

    def _status(self, state: str, tool: str, detail: str, production_ready: bool = False) -> dict[str, Any]:
        return {
            "id": self.provider_id,
            "state": state,
            "tool": tool,
            "model": self.model,
            "authenticated": production_ready,
            "production_ready": production_ready,
            "estimated_cost_usd": self.estimated_cost_usd,
            "detail": detail,
        }

    def generate(self, request: VideoRequest) -> VideoResult:
        ready = self.readiness()
        tool = self.active_tool() or self.tool_name
        if ready["state"] != "configured" or not tool:
            job = record_generation_job(
                provider=self.provider_id, tool_name=tool, state=ready["state"],
                prompt=request.prompt, estimated_cost_usd=0.0, error=ready["detail"],
            )
            return VideoResult(
                ok=False, state=ready["state"], provider_id=self.provider_id, tool_name=tool,
                model=self.model, estimated_cost_usd=0.0, error=ready["detail"], job_id=job["id"],
            )

        params = {
            "prompt": request.prompt,
            "duration": cloud_duration(tool, request.duration_sec),
            "aspect_ratio": request.aspect_ratio,
            "output_path": str(request.output_path),
            "operation": "text_to_video",
        }
        job = record_generation_job(
            provider=self.provider_id, tool_name=tool, state="running", prompt=request.prompt,
            output_path=str(request.output_path), estimated_cost_usd=self.estimated_cost_usd, params=params,
        )
        last_error = ""
        res: dict[str, Any] = {}
        for attempt in range(2):
            try:
                res = openmontage_adapter.execute_tool(tool, params)
            except Exception as exc:
                last_error = str(exc)
                if attempt == 0 and _is_transient_error(last_error):
                    time.sleep(0.5)
                    continue
                discard_unproven_output(request.output_path)
                update_generation_job(job["id"], state="failed", error=last_error)
                return VideoResult(
                    ok=False, state="failed", provider_id=self.provider_id, tool_name=tool,
                    model=self.model, estimated_cost_usd=self.estimated_cost_usd, error=last_error, job_id=job["id"],
                )

            if res.get("success") and _claim_output(res, request.output_path):
                _PROVEN.add(self.provider_id)
                update_generation_job(job["id"], state="ready", output_path=str(request.output_path))
                return VideoResult(
                    ok=True, state="ready", provider_id=self.provider_id, tool_name=tool, model=self.model,
                    estimated_cost_usd=self.estimated_cost_usd, job_id=job["id"], output_path=str(request.output_path),
                )

            last_error = str(res.get("error") or "provider returned no video file")
            if attempt == 0 and _is_transient_error(last_error):
                time.sleep(0.5)
                continue
            break

        discard_unproven_output(request.output_path)
        update_generation_job(job["id"], state="failed", error=last_error)
        return VideoResult(
            ok=False, state="failed", provider_id=self.provider_id, tool_name=tool, model=self.model,
            estimated_cost_usd=self.estimated_cost_usd, error=last_error, job_id=job["id"],
        )
