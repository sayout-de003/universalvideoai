#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INTEGRATIONS_DIR="$BASE_DIR/integrations"

mkdir -p "$INTEGRATIONS_DIR"

REPOS=(
  "handdraw-skill https://github.com/ToBeWin/HandDraw-Skill.git"
  "claude-animation-base https://github.com/JohnHeibel/ClaudeAnimationBase.git"
  "claude-drawing-skill https://github.com/cloveric/claude-drawing-skill.git"
  "anidoodle https://github.com/alexgreensh/anidoodle.git"
  "motion-skill https://github.com/LunaAI519/motion-skill.git"
  "motion-design-skill https://github.com/LottieFiles/motion-design-skill.git"
  "manim-skill https://github.com/adithya-s-k/manim_skill.git"
  "javascript-animation-skills https://github.com/iart-ai/javascript-animation-skills.git"
  "huashu-art-motion https://github.com/alchaincyf/huashu-art-motion.git"
)

echo "=== Fetching / Updating 9 Animation Skill Repositories ==="
for item in "${REPOS[@]}"; do
  set -- $item
  name="$1"
  url="$2"
  target="$INTEGRATIONS_DIR/$name"
  if [ -d "$target/.git" ]; then
    echo "Updating $name in $target..."
    git -C "$target" pull --ff-only || true
  else
    echo "Cloning $name from $url..."
    git clone --depth 1 "$url" "$target" || git clone "$url" "$target"
  fi
done

echo "=== Repositories Ready in $INTEGRATIONS_DIR ==="
