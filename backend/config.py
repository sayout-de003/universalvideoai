"""Studio configuration, path resolution, and hardware/environment discovery."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
INTEGRATIONS_DIR = ROOT_DIR / "integrations"
OPENMONTAGE_DIR = INTEGRATIONS_DIR / "OpenMontage"
OPENWHISPR_DIR = INTEGRATIONS_DIR / "openwhispr"
PROJECTS_DIR = ROOT_DIR / "projects"
MEDIA_LIBRARY_DIR = ROOT_DIR / "media_library"
MODEL_CACHE_DIR = ROOT_DIR / "model_cache"
DB_PATH = ROOT_DIR / "studio.db"

load_dotenv(ROOT_DIR / ".env", override=False)

SECRET_ENV_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "FAL_KEY",
    "FAL_AI_API_KEY",
    "REPLICATE_API_TOKEN",
    "RUNWAY_API_KEY",
    "KLING_API_KEY",
    "ARK_API_KEY",
    "PIKA_API_KEY",
    "LTX_API_KEY",
    "ELEVENLABS_API_KEY",
    "AZURE_SPEECH_KEY",
    "SUNO_API_KEY",
    "PEXELS_API_KEY",
    "PIXABAY_API_KEY",
    "UNSPLASH_ACCESS_KEY",
    "OPENWHISPR_API_KEY",
)


def ensure_directories() -> None:
    for d in (PROJECTS_DIR, MEDIA_LIBRARY_DIR, MODEL_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _detect_ram_gb() -> float:
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return round(int(out) / (1024**3), 2)
        if system == "Linux":
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024**2), 2)
    except Exception:
        pass
    return 0.0


@dataclass
class HardwareProfile:
    os_name: str
    arch: str
    cpu_cores: int
    ram_gb: float
    disk_free_gb: float
    disk_total_gb: float
    gpu_backend: str
    execution_profile: str = "lightweight"
    local_diffusion_eligible: bool = False
    chromium_path: str | None = None
    binaries: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "os_name": self.os_name,
            "arch": self.arch,
            "cpu_cores": self.cpu_cores,
            "ram_gb": self.ram_gb,
            "disk_free_gb": self.disk_free_gb,
            "disk_total_gb": self.disk_total_gb,
            "gpu_backend": self.gpu_backend,
            "execution_profile": self.execution_profile,
            "local_diffusion_eligible": self.local_diffusion_eligible,
            "chromium_path": self.chromium_path,
            "binaries": self.binaries,
        }


def detect_chromium_path() -> str | None:
    candidates = [
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for cand in candidates:
        if cand and Path(cand).is_file():
            return str(cand)
    return None


def detect_hardware() -> HardwareProfile:
    system = platform.system()
    arch = platform.machine().lower()
    usage = shutil.disk_usage(ROOT_DIR)
    ram_gb = _detect_ram_gb()
    disk_free_gb = round(usage.free / (1024**3), 2)

    if system == "Darwin" and "arm" in arch:
        gpu_backend = "apple_silicon_mps"
    elif shutil.which("nvidia-smi"):
        gpu_backend = "cuda"
    else:
        gpu_backend = "cpu"

    binary_names = [
        "ffmpeg", "ffprobe", "node", "npx", "python3", "blender",
        "manim", "piper", "whisper-cpp", "whisper", "ollama", "yt-dlp", "say",
    ]
    binaries = {name: shutil.which(name) is not None for name in binary_names}
    chromium_path = detect_chromium_path()
    binaries["chromium"] = chromium_path is not None

    local_diffusion_eligible = ram_gb >= 24.0 and disk_free_gb >= 40.0 and gpu_backend in ("cuda", "apple_silicon_mps")
    if local_diffusion_eligible:
        execution_profile = "full_local"
    elif ram_gb >= 16.0:
        execution_profile = "professional_hybrid"
    else:
        execution_profile = "lightweight"

    return HardwareProfile(
        os_name=f"{system} {platform.release()}",
        arch=arch,
        cpu_cores=os.cpu_count() or 1,
        ram_gb=ram_gb,
        disk_free_gb=disk_free_gb,
        disk_total_gb=round(usage.total / (1024**3), 2),
        gpu_backend=gpu_backend,
        execution_profile=execution_profile,
        local_diffusion_eligible=local_diffusion_eligible,
        chromium_path=chromium_path,
        binaries=binaries,
    )


def get_configured_credentials() -> dict[str, bool]:
    return {key: bool(os.environ.get(key, "").strip()) for key in SECRET_ENV_KEYS}


def get_studio_settings() -> dict[str, Any]:
    return {
        "mode": os.environ.get("STUDIO_MODE", "local_first"),
        "host": os.environ.get("STUDIO_HOST", "127.0.0.1"),
        "port": int(os.environ.get("STUDIO_PORT", "8420")),
        "backlot_port": int(os.environ.get("BACKLOT_PORT", "4750")),
        "budget_mode": os.environ.get("STUDIO_BUDGET_MODE", "cap"),
        "budget_usd": float(os.environ.get("STUDIO_BUDGET_USD", "10.00")),
        "single_action_approval_usd": float(os.environ.get("STUDIO_SINGLE_ACTION_APPROVAL_USD", "0.50")),
    }
