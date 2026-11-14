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

echo "==> Setting up Python virtual environment..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r integrations/OpenMontage/requirements.txt -r integrations/OpenMontage/requirements-dev.txt python-multipart

echo "==> Setting up Desktop (Electron + React + TypeScript)..."
cd desktop
npm install
npm run build
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "==> Setup complete!"
echo "    • Produce via CLI:  .venv/bin/python -m backend.cli produce \"Your video prompt\""
echo "    • Launch Desktop:   ./scripts/run_studio.sh"
