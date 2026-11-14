# Known Limitations & Tested Scope

1. **8 GB RAM / Apple M1 Host Constraints:** Local video diffusion models (Wan 2.2, Hunyuan, LTX-Video) require 12–24 GB+ RAM/VRAM and are intentionally disabled on 8 GB hosts to prevent OOM crashes. Cloud video providers (Veo, Kling, Runway, Seedance, MiniMax) require user-supplied API keys and explicit cost approval.
2. **Optional External Binaries:** `blender` and `manim` are not installed on this host; when requested, `engine_registry.py` honestly reports their unavailability and routes to the Three.js/FFmpeg 3D projection or HyperFrames/FFmpeg motion engine.
3. **FFmpeg `libfreetype` Absence:** Homebrew `ffmpeg 8.1.1` on this host does not include `drawtext` (`libfreetype`), so typography overlays are rendered via Pillow RGBA compositing (`renderer.py`), which works identically across platforms.
4. **OpenWhispr Desktop Standby:** If the OpenWhispr desktop app is not actively running (`~/.openwhispr/cli-bridge.json` absent), live microphone capture uses the Studio's voice command input and local `whisper-cpp`/`OPENAI_API_KEY` fallback.
5. **Multilingual Subtitle Translation:** Local-first offline mode tags non-English subtitle tracks (`[HI] ...`) when no cloud translation LLM key is configured; full semantic translation activates when an LLM API key is provided.
6. **Electron GUI Launch:** The Electron + React frontend has been TypeScript-checked (`tsc --noEmit`) and Vite-bundled (`vite build`), while interactive GUI clicking in a live macOS window requires launching `./scripts/run_studio.sh` in a desktop session.
