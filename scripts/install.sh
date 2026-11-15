#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Checking upstream integrations..."
mkdir -p integrations
if [ ! -d "integrations/OpenMontage/.git" ]; then
  git clone --depth 1 https://github.com/OpenMontageInc/OpenMontage.git integrations/OpenMontage
fi
if [ ! -d "integrations/openwhispr/.git" ]; then
  git clone --depth 1 https://github.com/OpenWhispr/openwhispr.git integrations/openwhispr
fi
if [ ! -d "integrations/voicestudio/.git" ]; then
  git clone --depth 1 https://github.com/debpalash/voicestudio.git integrations/voicestudio
fi
if [ ! -d "integrations/lemo-opuscar/.git" ]; then
  git clone --depth 1 https://github.com/lemomo-ai/lemo-opuscar.git integrations/lemo-opuscar
fi

echo "==> Setting up Python virtual environment..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r integrations/OpenMontage/requirements.txt -r integrations/OpenMontage/requirements-dev.txt python-multipart

echo "==> Setting up Desktop (Electron + React + TypeScript)..."
cd desktop
npm install
npm run build
cd "$ROOT_DIR"

echo "==> Setting up Remotion Composer & Lemo-Opuscar..."
if [ -d "integrations/OpenMontage/remotion-composer" ]; then
  (cd integrations/OpenMontage/remotion-composer && npm install)
fi
if [ -d "integrations/lemo-opuscar" ]; then
  (cd integrations/lemo-opuscar && npm install --no-audit --no-fund)
fi

echo "==> Ensuring default licensed 3D humanoid asset..."
mkdir -p media_library/characters
if [ ! -f "media_library/characters/soldier_rigged.glb" ]; then
  curl -fsSL "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Soldier.glb" \
    -o "media_library/characters/soldier_rigged.glb" || true
fi

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "==> Setup complete!"
echo "    • Produce via CLI:  .venv/bin/python -m backend.cli produce \"Your video prompt\""
echo "    • Launch Desktop:   ./scripts/run_studio.sh"
