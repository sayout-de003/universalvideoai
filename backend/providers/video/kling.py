import os

from backend.providers.video.openmontage_video import OpenMontageVideoProvider


class KlingProvider(OpenMontageVideoProvider):
    provider_id = "kling"
    tool_name = "kling_video"
    env_any = ("KLING_API_KEY", "FAL_KEY", "FAL_AI_API_KEY")
    model = "kling-v2"
    estimated_cost_usd = 0.35

    def active_tool(self) -> str | None:
        if os.environ.get("KLING_API_KEY", "").strip():
            return "kling_official_video"
        if os.environ.get("FAL_KEY", "").strip() or os.environ.get("FAL_AI_API_KEY", "").strip():
            return "kling_video"
        return None
