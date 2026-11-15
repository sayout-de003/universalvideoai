import os

from backend.config import detect_hardware
from backend.providers.video.openmontage_video import OpenMontageVideoProvider


class WanProvider(OpenMontageVideoProvider):
    provider_id = "wan"
    tool_name = "wan_video"
    env_any = ("FAL_KEY", "FAL_AI_API_KEY")
    model = "wan2.2"
    estimated_cost_usd = 0.0

    def active_tool(self) -> str | None:
        if detect_hardware().local_diffusion_eligible:
            return "wan_video"
        if os.environ.get("FAL_KEY", "").strip() or os.environ.get("FAL_AI_API_KEY", "").strip():
            return "wan_fal_video"
        return None

    def readiness(self) -> dict:
        if self.active_tool():
            return super().readiness()
        hw = detect_hardware()
        return self._status(
            "capability_unsupported",
            "wan_video",
            f"Local Wan needs at least 24 GB RAM and 40 GB free disk. This host has {hw.ram_gb} GB RAM. Cloud Wan needs FAL_KEY.",
        )
