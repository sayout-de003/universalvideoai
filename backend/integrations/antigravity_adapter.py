"""Antigravity-First Capability Discovery, Invocation & Priority Router."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.config import ROOT_DIR, detect_hardware, get_configured_credentials

PROVIDER_STATES = (
    "READY",
    "NOT_CONFIGURED",
    "AUTH_FAILED",
    "UNAVAILABLE",
    "RATE_LIMITED",
    "QUOTA_EXCEEDED",
    "MODEL_UNAVAILABLE",
    "CAPABILITY_UNSUPPORTED",
)


@dataclass
class CapabilityStatus:
    name: str
    kind: str
    status: str
    provider: str
    details: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "provider": self.provider,
            "details": self.details,
            "metadata": self.metadata,
        }


class AntigravityAdapter:
    """Discovers and routes to Antigravity tools/MCP first, then cloud, local engines, or archival media."""

    def __init__(self) -> None:
        self.mcp_config_paths = [
            Path(os.environ["ANTIGRAVITY_MCP_CONFIG"]) if os.environ.get("ANTIGRAVITY_MCP_CONFIG") else None,
            Path.home() / ".gemini" / "antigravity" / "mcp_config.json",
            ROOT_DIR / ".antigravity" / "mcp.json",
        ]

    def _discover_mcp_servers(self) -> dict[str, Any]:
        servers: dict[str, Any] = {}
        for cfg_path in self.mcp_config_paths:
            if cfg_path and cfg_path.is_file():
                try:
                    data = json.loads(cfg_path.read_text(encoding="utf-8"))
                    found = data.get("mcpServers") or data.get("servers") or {}
                    if isinstance(found, dict):
                        for name, spec in found.items():
                            servers[name] = {
                                "config_path": str(cfg_path),
                                "command": spec.get("command") if isinstance(spec, dict) else None,
                                "url": spec.get("url") if isinstance(spec, dict) else None,
                            }
                except Exception:
                    continue
        return servers

    def discover_capabilities(self) -> dict[str, Any]:
        hw = detect_hardware()
        creds = get_configured_credentials()
        mcp_servers = self._discover_mcp_servers()

        # Check Antigravity-connected media MCPs by common naming conventions
        mcp_names_lower = {k.lower(): k for k in mcp_servers}
        has_veo_mcp = any(t in mcp_names_lower for t in ("veo", "google-veo", "gemini-video"))
        has_image_mcp = any(t in mcp_names_lower for t in ("imagen", "nanobanana", "image-gen", "flux"))
        has_tts_mcp = any(t in mcp_names_lower for t in ("elevenlabs", "voicestudio", "tts"))
        has_blender_mcp = any(t in mcp_names_lower for t in ("blender", "blender-mcp"))

        capabilities = {
            "video_generation": CapabilityStatus(
                name="video_generation",
                kind="antigravity_mcp",
                status="READY" if has_veo_mcp else "UNAVAILABLE",
                provider="antigravity_mcp" if has_veo_mcp else "none",
                details="Connected video MCP server" if has_veo_mcp else "No video generation MCP server connected",
            ).to_dict(),
            "image_generation": CapabilityStatus(
                name="image_generation",
                kind="antigravity_mcp",
                status="READY" if has_image_mcp else "UNAVAILABLE",
                provider="antigravity_mcp" if has_image_mcp else "none",
                details="Connected image MCP server" if has_image_mcp else "No image generation MCP server connected",
            ).to_dict(),
            "voice_synthesis": CapabilityStatus(
                name="voice_synthesis",
                kind="antigravity_mcp",
                status="READY" if has_tts_mcp else "UNAVAILABLE",
                provider="antigravity_mcp" if has_tts_mcp else "none",
                details="Connected TTS MCP server" if has_tts_mcp else "No TTS MCP server connected",
            ).to_dict(),
            "blender_3d": CapabilityStatus(
                name="blender_3d",
                kind="antigravity_mcp",
                status="READY" if (has_blender_mcp or hw.binaries.get("blender")) else "UNAVAILABLE",
                provider="antigravity_mcp" if has_blender_mcp else ("local_blender" if hw.binaries.get("blender") else "none"),
                details="Blender MCP or local binary ready" if (has_blender_mcp or hw.binaries.get("blender")) else "Blender binary and Blender MCP unavailable",
            ).to_dict(),
            "archival_media": CapabilityStatus(
                name="archival_media",
                kind="zero_key_public_domain",
                status="READY",
                provider="wikimedia_nasa_openverse_loc",
                details="Zero-key Wikimedia Commons, NASA, Openverse, and Library of Congress adapters available",
            ).to_dict(),
        }

        return {
            "antigravity_runtime": bool(os.environ.get("ANTIGRAVITY_AGENT") or mcp_servers),
            "mcp_servers": mcp_servers,
            "execution_profile": hw.execution_profile,
            "local_diffusion_eligible": hw.local_diffusion_eligible,
            "configured_cloud_keys": [k for k, v in creds.items() if v],
            "capabilities": capabilities,
        }

    def validate_artifact(self, path: Path, expected_kind: str = "video") -> dict[str, Any]:
        """Verify an artifact exists, is non-empty, and passes ffprobe/image inspection."""
        if not path.exists() or not path.is_file():
            return {"valid": False, "reason": f"Artifact missing: {path}"}
        size = path.stat().st_size
        if size < 512:
            return {"valid": False, "reason": f"Artifact too small ({size} bytes): {path}"}

        if expected_kind in ("video", "audio"):
            if not shutil.which("ffprobe"):
                return {"valid": True, "size_bytes": size, "probed": False}
            try:
                raw = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                    text=True,
                    timeout=20,
                )
                data = json.loads(raw)
                streams = data.get("streams", [])
                want = "video" if expected_kind == "video" else "audio"
                matching = [s for s in streams if s.get("codec_type") == want]
                duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)
                if not matching or duration <= 0.1:
                    return {"valid": False, "reason": f"No valid {want} stream or zero duration in {path}"}
                return {"valid": True, "size_bytes": size, "duration_sec": duration, "streams": len(streams)}
            except Exception as exc:
                return {"valid": False, "reason": f"ffprobe failed: {exc}"}

        if expected_kind == "image":
            try:
                from PIL import Image
                with Image.open(path) as im:
                    w, h = im.size
                    if w < 160 or h < 120:
                        return {"valid": False, "reason": f"Image resolution too low: {w}x{h}"}
                    return {"valid": True, "size_bytes": size, "width": w, "height": h}
            except Exception as exc:
                return {"valid": False, "reason": f"Image validation failed: {exc}"}

        return {"valid": True, "size_bytes": size}

    def route_shot_strategy(self, category: str, requested_engine: str = "auto") -> list[str]:
        """Return ordered fallback chain of real production backends (never Pillow placeholder)."""
        caps = self.discover_capabilities()["capabilities"]
        creds = get_configured_credentials()
        cat = (category or "").lower()

        chain: list[str] = []
        # antigravity_video is discovery-only until an MCP caller exists; do not enqueue a tier nothing runs.
        if any(creds.get(k) for k in ("GOOGLE_API_KEY", "RUNWAY_API_KEY", "KLING_API_KEY", "FAL_KEY", "FAL_AI_API_KEY", "REPLICATE_API_TOKEN", "ARK_API_KEY")):
            chain.append("cloud_video")
        if requested_engine in ("threejs", "blender", "remotion", "hyperframes", "huggingface"):
            chain.append(requested_engine)
        elif requested_engine and (str(requested_engine).startswith("hf_") or any(k in requested_engine.lower() for k in ("hyperflow", "wan", "pan2", "minimax", "dmad"))):
            chain.append("huggingface")
        if requested_engine in ("blender", "hyperframes", "huggingface") or any(k in str(requested_engine).lower() for k in ("hyperflow", "wan", "pan2", "minimax", "dmad", "hf_")):
            # Never silently replace explicitly requested engines with archival footage
            return ["huggingface" if ("huggingface" in chain or "huggingface" in str(requested_engine) or any(k in str(requested_engine).lower() for k in ("hyperflow", "wan", "pan2", "minimax", "dmad", "hf_"))) else requested_engine]
        if cat in ("3d_animation", "3d_render", "architecture", "product_demo"):
            for eng in ("blender", "threejs"):
                if eng not in chain:
                    chain.append(eng)
        if cat in ("explainer", "motion_graphics", "social_reel", "saas_demo"):
            for eng in ("remotion", "hyperframes"):
                if eng not in chain:
                    chain.append(eng)
        if caps["image_generation"]["status"] == "READY" or any(creds.get(k) for k in ("OPENAI_API_KEY", "FAL_KEY", "FAL_AI_API_KEY", "GOOGLE_API_KEY", "REPLICATE_API_TOKEN")):
            chain.append("cloud_image_kenburns")
        # Zero-key archival media is always available for real photography/footage
        chain.append("archival_media")
        return chain
