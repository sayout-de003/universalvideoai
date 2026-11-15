from backend.providers.video.openmontage_video import OpenMontageVideoProvider


class VeoProvider(OpenMontageVideoProvider):
    provider_id = "veo"
    tool_name = "veo_video"
    env_any = ("GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "FAL_KEY", "FAL_AI_API_KEY")
    model = "veo-3.1"
    estimated_cost_usd = 0.40
