# Universal AI Film & Video Production Studio (`universalvideoai`)

Production-grade hybrid AI film studio supporting **AI cloud video generation** (Veo, Kling, Runway, Seedance, MiniMax, Wan), **headless Blender 3D character & environment production**, **Remotion React motion graphics**, **multi-speaker voice & phoneme lip-sync**, **multi-engine screenplay shot orchestration**, **automated FFprobe/FFmpeg/continuity QA**, and **native Antigravity MCP + plugin integration**.

---

## 1. Prerequisites

Ensure the following tools are installed on your machine:

| Tool | Purpose | macOS (Homebrew) | Ubuntu / Debian |
|---|---|---|---|
| **Python 3.12+** | Backend, orchestrator, MCP server | `brew install python` | `sudo apt install python3 python3-venv` |
| **Node.js 20+ & npm** | Remotion renderer & Desktop UI | `brew install node` | `sudo apt install nodejs npm` |
| **FFmpeg & FFprobe** | Compositing, stem mixing, QA probes | `brew install ffmpeg` | `sudo apt install ffmpeg` |
| **Blender 4.x / 5.x** | Headless 3D character & set rendering | `brew install --cask blender` | `sudo snap install blender --classic` |

Verify binaries:
```bash
python3 --version
node --version
ffmpeg -version | head -n 1
ffprobe -version | head -n 1
blender --version | head -n 1
```
*(If Blender is installed at `/Applications/Blender.app/Contents/MacOS/Blender` or a custom path, the studio detects it automatically or via `BLENDER_PATH=/path/to/blender` in `.env`.)*

---

## 2. Full Setup Guide (From Download to Ready)

### Step 1: Clone & Run the One-Command Installer
```bash
cd "video generations"
chmod +x scripts/install.sh scripts/run_studio.sh
./scripts/install.sh
```
What `./scripts/install.sh` does:
1. Clones upstream integrations into `integrations/` (`OpenMontage`, `openwhispr`, `voicestudio`) if not already present.
2. Creates `.venv` and installs all Python dependencies.
3. Installs and builds the Electron/React Desktop UI (`desktop/`).
4. Runs `npm install` inside `integrations/OpenMontage/remotion-composer` for React motion-graphics rendering.
5. Downloads the default MIT-licensed rigged humanoid character (`media_library/characters/soldier_rigged.glb`).
6. Copies `.env.example` to `.env` if `.env` does not exist.

### Step 2: Manual Setup (If Installing Step-by-Step)
```bash
# 1. Python environment
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r integrations/OpenMontage/requirements.txt \
                      -r integrations/OpenMontage/requirements-dev.txt \
                      python-multipart

# 2. Remotion React renderer
cd integrations/OpenMontage/remotion-composer && npm install && cd ../../..

# 3. Desktop UI
cd desktop && npm install && npm run build && cd ..

# 4. Default rigged 3D humanoid character (MIT license)
mkdir -p media_library/characters
curl -fsSL "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Soldier.glb" \
  -o media_library/characters/soldier_rigged.glb

# 5. Environment file
cp -n .env.example .env
```

---

## 3. Configuring Cloud AI & Voice Credentials (`.env`)

Edit `.env` in the repository root. All credentials remain strictly server-side.

```ini
# Studio runtime & budget guardrails
STUDIO_MODE=local_first
STUDIO_HOST=127.0.0.1
STUDIO_PORT=8420
STUDIO_BUDGET_MODE=cap
STUDIO_BUDGET_USD=10.00

# Cloud AI Video Providers (priority order: Veo -> Kling -> Runway -> Seedance -> MiniMax -> Wan)
GOOGLE_API_KEY=                  # Google Veo (veo-3.1) & Google Imagen
KLING_API_KEY=                   # Kling AI official video
RUNWAY_API_KEY=                  # Runway Gen-4 Turbo
ARK_API_KEY=                     # ByteDance Seedance 2.0
FAL_KEY=                         # Fal.ai (Kling / Seedance / MiniMax / Flux / Hunyuan3D image-to-3D)

# Image & Voice / Audio Providers
OPENAI_API_KEY=                  # OpenAI GPT-4o-mini-TTS, Whisper STT & Image
ELEVENLABS_API_KEY=              # ElevenLabs TTS
AZURE_SPEECH_KEY=                # Azure Neural Speech
PEXELS_API_KEY=                  # Optional stock footage
PIXABAY_API_KEY=                 # Optional stock footage
```

> **Zero-Key Local Operation**: Even with zero API keys configured, the studio renders real videos locally using **Blender 3D**, **Remotion**, **Three.js**, **HyperFrames**, **Zero-Key Archival Media (Wikimedia/NASA/Openverse)**, and local **VoiceStudio / macOS TTS + FFmpeg stem mixing**. It never silently substitutes archival still images for a failed cloud video call.

---

## 4. Setting Up with Antigravity

### Option A: Open Workspace Directly in Antigravity
1. Open the `video generations` folder in **Antigravity**.
2. Antigravity automatically reads [AGENTS.md](file:///Users/sayantande/Actual%20Video%20Genarations/video%20generations/AGENTS.md) and the bundled plugin in `plugins/universal-video-studio/`.

### Option B: Connect the Studio MCP Server to Antigravity
Add the `universal-video-studio` stdio MCP server to `~/.gemini/antigravity/mcp_config.json` (or `.antigravity/mcp.json` in your workspace):

```json
{
  "mcpServers": {
    "universal-video-studio": {
      "command": "/ABSOLUTE/PATH/TO/video generations/.venv/bin/python",
      "args": ["-m", "backend.mcp_server"],
      "env": {
        "PYTHONPATH": "/ABSOLUTE/PATH/TO/video generations"
      }
    }
  }
}
```

### Exposed MCP Tools (14 Operational Tools)
Once connected, Antigravity can invoke these tools directly:
- **Project & Package Workflow**:
  - `studio_list_formats` — List all 25 supported video formats and rules.
  - `studio_start_intake` — Start guided creative intake (asks format & duration).
  - `studio_answer_intake` — Submit intake answers.
  - `studio_create_project` — Generate the 28-artifact production package (screenplay, storyboard, character bible, shot list).
  - `studio_get_package` — Inspect project details and artifacts.
  - `studio_approve_gates` — Approve mandatory screenplay, storyboard, and production plan gates.
  - `studio_produce_video` — Render scenes, mix audio stems, and run automated QA.
- **Blender 3D Character & Scene Tools**:
  - `blender_validate_mesh` — Inspect vertex/face/armature/animation stats and clean up `.glb`/`.fbx`/`.obj`/`.blend` meshes in headless Blender.
  - `blender_auto_rig_mesh` — Attach a humanoid armature with automatic weights to an unrigged mesh and export `.glb`.
  - `blender_register_character_asset` — Validate and register a 3D character asset with a cryptographic continuity hash.
  - `blender_apply_animation` — Bind an animation (`walk`, `idle`, `run`, `talk`, `wave`) from the character's action library and export `.glb`.
  - `blender_render_character_shot` — Render an animated 3D character shot in a `room` or `outdoor` environment with 3-point lighting and tracked camera to MP4.
- **Multi-Engine Screenplay Orchestration**:
  - `studio_orchestrate_screenplay` — Route every shot in a screenplay to `ai_video`, `blender`, `remotion`, `licensed_footage`, or `hybrid` (`blender` + `remotion`) and optionally render all shots.
  - `studio_regenerate_shot` — Regenerate a single shot (with optional engine or prompt override) while preserving all other shot assets.

---

## 5. Complete Video Creation Guide

### A. One-Command Full Video Production (CLI)
Produce a complete, narrated, scored, subtitled, and QA-verified MP4 + shareable ZIP bundle from any prompt:
```bash
PYTHONPATH=. .venv/bin/python -m backend.cli produce \
  "Create a 30-second animated explainer about how quantum computers work with charts and captions" \
  --bundle
```
Outputs are written to `projects/<project_id>/`:
- Final MP4: `projects/<project_id>/renders/final_master.mp4`
- Audio stems: `projects/<project_id>/stems/{narration,music,sfx,master_mix}.wav`
- Subtitles: `projects/<project_id>/subtitles/subtitles_en.{srt,vtt}`
- Shareable bundle: `projects/<project_id>/deliverables/share_bundle.zip`

### B. Launch the Desktop Studio UI & FastAPI Server
```bash
./scripts/run_studio.sh
```
Or run the FastAPI backend directly on `http://127.0.0.1:8420`:
```bash
PYTHONPATH=. .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8420
```

### C. Blender 3D Character Production & Rendering
Render a rigged humanoid character walking in a 3D room or outdoor set via Python or MCP:
```bash
PYTHONPATH=. .venv/bin/python -c '
from pathlib import Path
from backend.integrations.blender_adapter import render_blender_scene

res = render_blender_scene(
    scene={
        "title": "Agent Walk",
        "character_mesh_path": "media_library/characters/soldier_rigged.glb",
        "animation_name": "walk",
        "environment_type": "room",
        "duration_sec": 3.0,
    },
    output_mp4=Path("projects/demo_blender_walk.mp4"),
    work_dir=Path("projects/demo_blender_work"),
    width=1280,
    height=720,
    fps=24,
)
print(res)
'
```

### D. Remotion Motion Graphics, Charts & Word Captions
Render React-based animated charts, kinetic typography, and word-by-word captions:
```bash
PYTHONPATH=. .venv/bin/python -c '
from pathlib import Path
from backend.services.remotion_renderer import render_remotion_scene

res = render_remotion_scene(
    scene={
        "title": "Revenue Growth",
        "on_screen_text": "Q4 Studio Output",
        "narration_segment": "Automated multi-engine rendering scales video output across every format.",
        "duration_sec": 3.0,
        "chart_type": "bar_chart",
        "chart_data": [
            {"label": "Q1", "value": 32},
            {"label": "Q2", "value": 58},
            {"label": "Q3", "value": 91},
        ],
    },
    output_mp4=Path("projects/demo_remotion_chart.mp4"),
    width=1280,
    height=720,
    fps=30,
)
print(res)
'
```

### E. Multi-Speaker Voice, Lip-Sync & Audio Mixing
Assign distinct voices per character, extract per-frame phoneme/viseme mouth openness from real WAV audio, and mix dialogue onto video:
```bash
PYTHONPATH=. .venv/bin/python -c '
from pathlib import Path
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project
from backend.services.voice_lip_sync_service import assign_character_voice, synthesize_dialogue_lines

proj = create_project(ProjectCreateRequest(prompt="Dialogue scene", target_duration_sec=10))
pid = proj["project"]["id"]
assign_character_voice(pid, "Elena", "narrator_warm")
assign_character_voice(pid, "Marcus", "character_1")

dlg = synthesize_dialogue_lines(
    project_id=pid,
    dialogue_lines=[
        {"speaker": "Elena", "text": "Camera one is locked on the corridor.", "expression": "focused"},
        {"speaker": "Marcus", "text": "Cue the character walk animation now.", "expression": "confident"},
    ],
    output_dir=Path(f"projects/{pid}/audio/dialogue"),
)
print("Tracks:", len(dlg["tracks"]), "Lip-sync frames:", len(dlg["lip_sync_frames"]))
'
```

### F. Multi-Engine Screenplay Orchestration & Single-Shot Regeneration
Route a multi-shot screenplay across `blender`, `remotion`, `ai_video`, `licensed_footage`, and `hybrid` (`blender` + `remotion` PIP overlay), then regenerate a single shot without touching the rest:
```bash
# Via REST API when server is running:
curl -X POST http://127.0.0.1:8420/api/projects/<PROJECT_ID>/screenplay/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Hybrid Launch Film",
    "render": true,
    "shots": [
      {"title": "Hero Walk", "description": "3D humanoid character walking down a studio corridor", "duration_sec": 2.5},
      {"title": "Metrics Overlay", "description": "Animated bar chart showing Q4 KPI metrics", "duration_sec": 2.5},
      {"title": "Combined Shot", "description": "3D character walking next to an animated KPI chart", "duration_sec": 2.5}
    ]
  }'

# Regenerate only one shot:
curl -X POST http://127.0.0.1:8420/api/projects/<PROJECT_ID>/shots/<SHOT_ID>/regenerate \
  -H "Content-Type: application/json" \
  -d '{"engine_override": "remotion", "description_override": "Updated KPI callout card"}'
```

### G. Automated Production QA & Human Visual Approval
Automated QA (`run_qa_verification`) checks:
1. File existence & FFprobe stream integrity
2. Video & audio stream presence
3. Aspect ratio & exact resolution
4. Black frame detection (`blackdetect`)
5. Audio loudness & clipping (`volumedetect`)
6. Scene completeness & edit duration match
7. 3D character continuity hash & wardrobe consistency
8. Dialogue WAV completeness & lip-sync timing span
9. Failed scene render status

Automated QA sets `approval_status = "PENDING_HUMAN_VISUAL_REVIEW"`. Record human visual sign-off separately:
```bash
curl -X POST http://127.0.0.1:8420/api/projects/<PROJECT_ID>/qa/human-approve \
  -H "Content-Type: application/json" \
  -d '{"report_id": "<QA_REPORT_ID>", "approved": true, "reviewer_notes": "Checked lighting and lip sync"}'
```

---

## 6. Running the Test Suite

Run all verification suites from the `video generations` directory:
```bash
PYTHONPATH=. .venv/bin/pytest \
  tests/test_video_providers.py \
  tests/test_studio_scenarios.py \
  tests/test_blender_pipeline.py \
  tests/test_remotion_renderer.py \
  tests/test_voice_lipsync.py \
  tests/test_shot_orchestrator.py \
  tests/test_qa_production.py -v
```
