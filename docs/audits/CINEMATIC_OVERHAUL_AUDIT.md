# Cinematic Overhaul — Repository, Hardware & Environment Audit

**Date:** 2026-11-14
**Workspace:** `/Users/sayantande/Downloads/video generations`

## 1. Hardware & OS Profile
- **OS / Arch:** `Darwin 25.6.0` (`arm64`, Apple Silicon)
- **CPU / RAM:** `8` cores, `8.0 GB RAM` (`apple_silicon_mps`)
- **Disk:** `~29.5 GB` free
- **Recommended Execution Profile:** **`lightweight`** (hybrid cloud/API + archival media + lightweight local FFmpeg/WebGL/TTS; local video diffusion models such as Wan/CogVideo/LTX/ComfyUI are **ineligible** due to 8 GB unified memory and 29.5 GB disk constraints).

## 2. Host Binaries & Python/Node Environment
| Capability / Binary | Status | Path / Notes |
|---|---|---|
| `ffmpeg` / `ffprobe` | **READY** | `/opt/homebrew/bin/ffmpeg`, `/opt/homebrew/bin/ffprobe` (8.1.1; has `xfade`, `overlay`, `zoompan`, `eq`, `noise`, `loudnorm`, `sidechaincompress`; lacks `libfreetype` `drawtext` and `libass` `subtitles`) |
| `node` / `npx` | **READY** | `/opt/homebrew/bin/node` (`v24.4.1`), `/opt/homebrew/bin/npx` |
| `python3` / `.venv` | **READY** | `PIL 13.0.0`, `httpx 0.28.1`, `fastapi 0.162.7`, `uvicorn 0.54.0`, `pytest 9.2.0`; `playwright` Python package is **NOT INSTALLED** |
| Headless Browser | **PARTIAL** | `/Applications/Google Chrome.app` and `/Applications/Brave Browser.app` are installed; `playwright` / `chromium` CLI not on `PATH` |
| `remotion` | **NOT_INSTALLED** | `integrations/OpenMontage/remotion-composer/package.json` exists (`remotion ^4.0.484`), but `node_modules/` is not installed |
| `blender` | **UNAVAILABLE** | Not installed on host (`shutil.which("blender") is None`) |
| `manim` / `ollama` / `whisper` | **UNAVAILABLE** | Not installed on host |
| `say` (macOS TTS) | **READY** | `/usr/bin/say` (legacy fallback only; must not be treated as studio-grade voice) |
| Cloud API Keys (19 keys) | **NOT_CONFIGURED** | All 19 keys (`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `FAL_KEY`, `RUNWAY_API_KEY`, `KLING_API_KEY`, `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`, etc.) are unset |

## 3. Antigravity Runtime & MCP Discovery
- **Active Session Tools:** Filesystem, command execution, web search (`search_web`), URL reader (`read_url_content`), image generation (`generate_image`), and subagent orchestration.
- **External Media MCP Servers:** None currently connected in this session (e.g., no Blender MCP, Veo MCP, or ElevenLabs MCP).
- **Implication:** `AntigravityAdapter` must discover connected capabilities dynamically, route to Antigravity tools/MCP when available, and fall back cleanly to configured cloud providers, local engines (Chrome/WebGL Three.js, Remotion/HyperFrames when installed, FFmpeg), or **zero-key public-domain/archival media** without ever faking success.

## 4. Existing Codebase Gaps Identified
1. **`backend/orchestration/renderer.py` (Primary Root Cause):**
   - `render_scene_clip()` never invokes `openmontage_adapter.execute_tool()`.
   - `threejs` writes a dummy HTML stub and renders a Pillow wireframe octahedron.
   - `hyperframes` and `remotion` fall back to Pillow motion-graphics frames.
   - `_draw_caption_and_hud()` unconditionally stamps a dark card, category pill badge, and progress bar onto every frame, even for historical documentaries and films.
2. **`backend/orchestration/engine_registry.py` & `backend/config.py`:**
   - Lacks hardware execution profiles (`lightweight`, `professional_hybrid`, `full_local`) and granular provider health states (`NOT_CONFIGURED`, `AUTH_FAILED`, `UNAVAILABLE`, `RATE_LIMITED`, `QUOTA_EXCEEDED`, `MODEL_UNAVAILABLE`, `CAPABILITY_UNSUPPORTED`, `READY`).
3. **Zero-Key Archival Media Underutilized:**
   - `integrations/OpenMontage/tools/video/stock_sources/` already contains `wikimedia.py`, `nasa.py`, `openverse.py`, `loc.py`, `archive_org.py`, etc., but `backend/` never uses them to fetch real photography/footage for zero-key documentaries and films.
4. **`backend/orchestration/audio_studio.py`:**
   - `generate_music_bed()` synthesizes 4 raw sine waves via `aevalsrc` when `SUNO_API_KEY` is absent.
   - `generate_tts()` falls back to robotic macOS `say` or `ffmpeg_cadence_fallback` without flagging quality degradation.
5. **`backend/orchestration/qa.py`:**
   - Only checks FFprobe stream presence, aspect ratio, black frames, and `volumedetect`. Performs no visual continuity, character consistency, prompt adherence, or multi-axis scoring.

## 5. Overhaul Plan
1. **Antigravity-First Adapter, Hardware Profiles & Provider Health Registry:** `backend/integrations/antigravity_adapter.py`, `backend/config.py`, `backend/orchestration/engine_registry.py`.
2. **Zero-Key Archival Media & Real Shot Dispatcher:** `backend/services/archival_media_service.py`, `backend/services/shot_generation_service.py`, and full rewrite of `backend/orchestration/renderer.py` (format-aware visual policy + FFmpeg Ken Burns/color grade/film grain + real provider/engine routing, zero silent Pillow masking).
3. **Real Engine Adapters (Three.js via Headless Chrome WebGL, Remotion CLI, HyperFrames, Blender):** `backend/integrations/blender_adapter.py`, `backend/services/threejs_renderer.py`, `backend/services/remotion_renderer.py`, `backend/services/hyperframes_renderer.py`.
4. **Audio Studio & Multi-Axis QA Upgrade:** `backend/orchestration/audio_studio.py`, `backend/orchestration/qa.py`, `backend/orchestration/director.py`.
5. **Verification & Documentation:** Run Tests A–H, verify frontend build, and produce `ARCHITECTURE.md`, `PROVIDER_MATRIX.md`, `BLENDER_SETUP.md`, `HARDWARE_COMPATIBILITY.md`, and `TEST_REPORT.md`.
