import os

from backend.providers.video.openmontage_video import OpenMontageVideoProvider


class SeedanceProvider(OpenMontageVideoProvider):
    provider_id = "seedance"
    tool_name = "seedance_video"
    env_any = ("ARK_API_KEY", "FAL_KEY", "FAL_AI_API_KEY")
    model = "seedance-2.0"
    estimated_cost_usd = 0.30

    def active_tool(self) -> str | None:
        if os.environ.get("ARK_API_KEY", "").strip():
            return "seedance_ark"
        if os.environ.get("FAL_KEY", "").strip() or os.environ.get("FAL_AI_API_KEY", "").strip():
            return "seedance_video"
        return None
