import os

from backend.providers.video.openmontage_video import OpenMontageVideoProvider


class MinimaxProvider(OpenMontageVideoProvider):
    provider_id = "minimax"
    tool_name = "minimax_video"
    env_any = ("MINIMAX_API_KEY", "FAL_KEY", "FAL_AI_API_KEY")
    model = "video-01"
    estimated_cost_usd = 0.25

    def active_tool(self) -> str | None:
        if os.environ.get("MINIMAX_API_KEY", "").strip():
            return "minimax_video"
        if os.environ.get("FAL_KEY", "").strip() or os.environ.get("FAL_AI_API_KEY", "").strip():
            return "minimax_fal_video"
        return None
