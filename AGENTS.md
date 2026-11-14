# Universal AI Video Production Studio — Antigravity Agent Instructions

When a user provides this repository to **Antigravity** (or any AI coding agent), follow these steps automatically:

## 1. One-Command Setup (First Run)

If `.venv/` or `integrations/OpenMontage` does not exist yet, run:
```bash
chmod +x scripts/install.sh scripts/run_studio.sh
./scripts/install.sh
```

## 2. Produce a Video Directly from an Antigravity Prompt

When the user asks Antigravity to make any video (e.g. *"Make a 30-second animated video about..."* or *"Create a documentary about..."*), run the Studio CLI:
```bash
PYTHONPATH=. .venv/bin/python -m backend.cli produce "<USER_PROMPT>" --bundle
```
This will:
1. Classify the video category, OpenMontage pipeline, and optimal rendering engine (`ffmpeg`, `hyperframes`, `threejs`, `remotion`).
2. Generate the hierarchical script, storyboard, character/speaker bible, TTS narration, mood-matched music, SFX, and subtitles.
3. Render all scenes & chapters, mix audio stems with sidechain ducking, and run real FFprobe/FFmpeg QA.
4. Package a downloadable/shareable ZIP bundle (`deliverables/share_bundle.zip`) and print the exact paths to the final MP4, subtitles, and bundle.

Always present the resulting MP4 path and `share_bundle.zip` path to the user so they can play, download, or share it immediately.

## 3. Launch the Full Desktop Studio UI

If the user wants the visual multitrack editor, Backlot monitor, storyboard, or Export Center:
```bash
./scripts/run_studio.sh
```
