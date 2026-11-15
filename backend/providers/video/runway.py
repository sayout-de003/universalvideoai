from backend.providers.video.openmontage_video import OpenMontageVideoProvider


class RunwayProvider(OpenMontageVideoProvider):
    provider_id = "runway"
    tool_name = "runway_video"
    env_any = ("RUNWAY_API_KEY",)
    model = "gen4_turbo"
    estimated_cost_usd = 0.50
