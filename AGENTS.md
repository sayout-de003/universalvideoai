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

## 4. Claude Animation Skills Suite

The studio integrates 9 open-source Claude Animation Skills for deterministic code-driven and hand-drawn animation:

| Skill | Tech | Use Case |
|---|---|---|
| **HandDraw** | Remotion + SVG + Edge TTS | Whiteboard & hand-drawn explainer videos |
| **ClaudeAnimationBase** | p5.js + p5.brush | Hand-painted cartoon character acting (Clawd, 31 emotions) |
| **Claude Drawing Skill** | Python (numpy + Pillow) | 83 procedural illustration styles & draw-on timelapses |
| **AniDoodle** | Canvas / WebGL / Web Audio | 32 code-drawn styles with acoustic scores |
| **Motion Skill** | Prompt Compiler + Kling/Nano Banana | Retro collage-style animated videos |
| **Motion Design** | Rules / LottieFiles | Disney animation principles & easing review |
| **Manim Skill** | Manim CE / Python | 3Blue1Brown mathematical & educational animations |
| **JavaScript Animation** | HTML5 Canvas + Web Audio | Zero-asset canvas films with code-synthesized audio |
| **Huashu Art Motion** | Canvas / Multi-track | 36 traditional & contemporary art styles, 9 grammars |

### CLI Commands:
```bash
# List all 9 skills and readiness
PYTHONPATH=. .venv/bin/python -m backend.cli animation list

# List all 83 Claude Drawing styles
PYTHONPATH=. .venv/bin/python -m backend.cli animation styles

# Procedurally render in any style (e.g. blueprint, artdeco, ukiyo-e)
PYTHONPATH=. .venv/bin/python -m backend.cli animation draw blueprint output.png

# Review an animation plan for timing & Disney principles
PYTHONPATH=. .venv/bin/python -m backend.cli animation review --timing 0.8 --easing easeInOut
```

