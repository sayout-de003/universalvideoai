---
name: universal-video-studio
description: Setup, run, and produce any type of video using the Universal AI Video Production Studio (OpenMontage + OpenWhispr) from Antigravity, CLI, or Desktop UI.
---

# Universal AI Video Production Studio Skill

1. **Setup check:** If `.venv` or `integrations/OpenMontage` is missing, run `./scripts/install.sh`.
2. **Generate video from user prompt:**
   ```bash
   PYTHONPATH=. .venv/bin/python -m backend.cli produce "<prompt>" --bundle
   ```
   Optional flags: `--duration <sec>`, `--aspect 16:9|9:16|1:1`, `--engine ffmpeg|hyperframes|threejs|remotion`, `--subtitles en,hi`.
3. **Verify & Deliver:** Confirm `qa_passed: true` in the CLI JSON output and give the user the direct file links to `final_production.mp4` and `share_bundle.zip`.
4. **Launch Desktop App:** Run `./scripts/run_studio.sh`.
