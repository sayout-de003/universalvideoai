"""Preferred order is cinematic cloud first. Wan is last because this host usually cannot run it."""

from __future__ import annotations

from backend.providers.video.kling import KlingProvider
from backend.providers.video.minimax import MinimaxProvider
from backend.providers.video.openmontage_video import OpenMontageVideoProvider
from backend.providers.video.runway import RunwayProvider
from backend.providers.video.seedance import SeedanceProvider
from backend.providers.video.veo import VeoProvider
from backend.providers.video.wan import WanProvider

_PROVIDERS: tuple[OpenMontageVideoProvider, ...] = (
    VeoProvider(),
    KlingProvider(),
    RunwayProvider(),
    SeedanceProvider(),
    MinimaxProvider(),
    WanProvider(),
)


def list_video_providers() -> tuple[OpenMontageVideoProvider, ...]:
    return _PROVIDERS


def video_provider_readiness() -> list[dict]:
    return [provider.readiness() for provider in _PROVIDERS]
