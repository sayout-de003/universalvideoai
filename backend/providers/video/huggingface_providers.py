"""Hugging Face Video Providers for Universal Video AI Studio.

Integrates:
- VideoRebirthAI/hyperflow-h3-flash
- Wan-AI/Wan2.2-TI2V-5B
- Comfy-Org/PAN2
- Wan-AI/Wan2.2-T2V-A14B
- larryvrh/MiniMax-H3-Turbo-Lora
- ZhengmingYu/DMAD
- Wan-AI/Wan2.1-T2V-1.3B
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.config import detect_hardware
from backend.providers.jobs.status import record_generation_job, update_generation_job
from backend.providers.video.base import VideoRequest, VideoResult
from backend.providers.video.openmontage_video import OpenMontageVideoProvider
from backend.services.huggingface_video_service import (
    get_model_local_cache_info,
    get_model_spec,
    generate_video_with_huggingface_model,
)


class BaseHuggingFaceVideoProvider(OpenMontageVideoProvider):
    """Base provider for Hugging Face open-weight video models."""

    repo_id: str = ""
    estimated_cost_usd: float = 0.0

    def active_tool(self) -> str | None:
        return self.tool_name

    def readiness(self) -> dict[str, Any]:
        hw = detect_hardware()
        cache = get_model_local_cache_info(self.repo_id)
        spec = get_model_spec(self.repo_id) or {}
        vram_rec = spec.get("vram_recommended_gb", 16.0)

        is_ready = True
        state = "configured"
        detail = (
            f"Hugging Face model {self.repo_id} integrated. "
            f"VRAM req: {vram_rec}GB | Host: {hw.ram_gb}GB RAM | Cached locally: {cache['cached']}"
        )
        return {
            "id": self.provider_id,
            "state": state,
            "tool": self.tool_name,
            "model": self.model,
            "repo_id": self.repo_id,
            "authenticated": True,
            "production_ready": True,
            "estimated_cost_usd": self.estimated_cost_usd,
            "detail": detail,
            "local_cached": cache["cached"],
            "cached_size_mb": cache["size_mb"],
        }

    def generate(self, request: VideoRequest) -> VideoResult:
        job = record_generation_job(
            provider=self.provider_id,
            tool_name=self.tool_name,
            state="running",
            prompt=request.prompt,
            output_path=str(request.output_path),
            estimated_cost_usd=0.0,
            params={"repo_id": self.repo_id, "duration": request.duration_sec},
        )
        try:
            res = generate_video_with_huggingface_model(
                model_key_or_repo=self.repo_id,
                prompt=request.prompt,
                output_mp4=request.output_path,
                duration_sec=request.duration_sec,
                aspect_ratio=request.aspect_ratio,
            )
            if res.get("ok") and Path(res["output"]).is_file():
                update_generation_job(job["id"], state="ready", output_path=str(request.output_path))
                return VideoResult(
                    ok=True,
                    state="ready",
                    provider_id=self.provider_id,
                    tool_name=self.tool_name,
                    model=self.model,
                    estimated_cost_usd=0.0,
                    job_id=job["id"],
                    output_path=str(request.output_path),
                )
            err = res.get("reason", "Generation failed")
            update_generation_job(job["id"], state="failed", error=err)
            return VideoResult(
                ok=False,
                state="failed",
                provider_id=self.provider_id,
                tool_name=self.tool_name,
                model=self.model,
                estimated_cost_usd=0.0,
                error=err,
                job_id=job["id"],
            )
        except Exception as exc:
            update_generation_job(job["id"], state="failed", error=str(exc))
            return VideoResult(
                ok=False,
                state="failed",
                provider_id=self.provider_id,
                tool_name=self.tool_name,
                model=self.model,
                estimated_cost_usd=0.0,
                error=str(exc),
                job_id=job["id"],
            )


class HyperflowH3FlashProvider(BaseHuggingFaceVideoProvider):
    provider_id = "hf_hyperflow_h3_flash"
    tool_name = "hyperflow_video"
    repo_id = "VideoRebirthAI/hyperflow-h3-flash"
    model = "VideoRebirthAI/hyperflow-h3-flash"


class WanTI2V5BProvider(BaseHuggingFaceVideoProvider):
    provider_id = "hf_wan2_2_ti2v_5b"
    tool_name = "wan_ti2v_video"
    repo_id = "Wan-AI/Wan2.2-TI2V-5B"
    model = "Wan-AI/Wan2.2-TI2V-5B"


class ComfyPan2Provider(BaseHuggingFaceVideoProvider):
    provider_id = "hf_pan2"
    tool_name = "pan2_video"
    repo_id = "Comfy-Org/PAN2"
    model = "Comfy-Org/PAN2"


class WanT2VA14BProvider(BaseHuggingFaceVideoProvider):
    provider_id = "hf_wan2_2_t2v_a14b"
    tool_name = "wan_a14b_video"
    repo_id = "Wan-AI/Wan2.2-T2V-A14B"
    model = "Wan-AI/Wan2.2-T2V-A14B"


class MiniMaxTurboLoraProvider(BaseHuggingFaceVideoProvider):
    provider_id = "hf_minimax_turbo_lora"
    tool_name = "minimax_turbo_video"
    repo_id = "larryvrh/MiniMax-H3-Turbo-Lora"
    model = "larryvrh/MiniMax-H3-Turbo-Lora"


class DmadLoraProvider(BaseHuggingFaceVideoProvider):
    provider_id = "hf_dmad"
    tool_name = "dmad_video"
    repo_id = "ZhengmingYu/DMAD"
    model = "ZhengmingYu/DMAD"


class WanT2V13BProvider(BaseHuggingFaceVideoProvider):
    provider_id = "hf_wan2_1_t2v_1_3b"
    tool_name = "wan_1_3b_video"
    repo_id = "Wan-AI/Wan2.1-T2V-1.3B"
    model = "Wan-AI/Wan2.1-T2V-1.3B"
