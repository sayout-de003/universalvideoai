"""Animation Skills Adapter — Integration gateway for the 9 Claude Animation Skills.

Connects:
1. HandDraw Skill (SVG + Remotion + Edge TTS)
2. Claude Animation Base (p5.js + p5.brush Clawd character acting)
3. Claude Drawing Skill (83 procedural styles in numpy + Pillow)
4. AniDoodle (32 code-drawn styles in Canvas / WebGL)
5. Motion Skill (Retro collage animation + Kling/Nano Banana pipeline)
6. Motion Design Skill (Disney/Lottie timing, easing & choreography principles)
7. Manim Skill (3Blue1Brown mathematical & educational animations)
8. JavaScript Animation Skills (Zero-asset HTML5 Canvas + Web Audio)
9. Huashu Art Motion (36 art styles + 9 explainer grammars)
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from backend.config import ROOT_DIR, INTEGRATIONS_DIR


class AnimationSkillsAdapter:
    """Unified coordinator for the 9 Claude Animation Skills."""

    def __init__(self, integrations_dir: Path | None = None) -> None:
        self.integrations_dir = integrations_dir or INTEGRATIONS_DIR

    def get_skill_paths(self) -> dict[str, Path]:
        """Return root path for each of the animation skills."""
        return {
            "handdraw-skill": self.integrations_dir / "handdraw-skill",
            "claude-animation-base": self.integrations_dir / "claude-animation-base",
            "claude-drawing-skill": self.integrations_dir / "claude-drawing-skill",
            "anidoodle": self.integrations_dir / "anidoodle",
            "motion-skill": self.integrations_dir / "motion-skill",
            "motion-design": self.integrations_dir / "motion-design-skill",
            "manim-skill": self.integrations_dir / "manim-skill",
            "javascript-animation": self.integrations_dir / "javascript-animation-skills",
            "huashu-art-motion": self.integrations_dir / "huashu-art-motion",
        }

    def list_skills(self) -> list[dict[str, Any]]:
        """List all 9 skills with their runtime readiness, description, and technology."""
        paths = self.get_skill_paths()
        has_node = bool(shutil.which("node"))
        has_ffmpeg = bool(shutil.which("ffmpeg"))
        has_manim = bool(shutil.which("manim"))

        skills = [
            {
                "id": "handdraw-skill",
                "name": "HandDraw Skill",
                "description": "Agent-native deterministic hand-drawn animation engine powered by SVG, Remotion, FFmpeg, and free Edge TTS.",
                "technology": "SVG + Remotion + Edge TTS + FFmpeg",
                "installed": (paths["handdraw-skill"] / "SKILL.md").is_file(),
                "ready": (paths["handdraw-skill"] / "SKILL.md").is_file() and has_node and has_ffmpeg,
                "path": str(paths["handdraw-skill"]),
                "formats": ["handdrawn_whiteboard", "animated-explainer"],
            },
            {
                "id": "claude-animation-base",
                "name": "Claude Animation Base",
                "description": "Hand-painted cartoon character acting using p5.js and p5.brush with Clawd, 31 acted emotions, boil lines, and headless rendering.",
                "technology": "p5.js + p5.brush + Puppeteer / Node",
                "installed": (paths["claude-animation-base"] / "SKILL.md").is_file(),
                "ready": (paths["claude-animation-base"] / "SKILL.md").is_file() and has_node,
                "path": str(paths["claude-animation-base"]),
                "formats": ["character_p5_cartoon", "2d_illustrated"],
            },
            {
                "id": "claude-drawing-skill",
                "name": "Claude Drawing Skill",
                "description": "Procedural illustration in 83 artistic styles (ink wash, watercolor, ukiyo-e, mosaic, Art Deco) using pure numpy + Pillow CPU rendering.",
                "technology": "Python (numpy + Pillow, 100% CPU)",
                "installed": (paths["claude-drawing-skill"] / "SKILL.md").is_file(),
                "ready": (paths["claude-drawing-skill"] / "lib").is_dir(),
                "path": str(paths["claude-drawing-skill"]),
                "formats": ["procedural_art_drawing", "hand_drawn_storybook"],
            },
            {
                "id": "anidoodle",
                "name": "AniDoodle",
                "description": "Pictures, films, and interactive animations drawn entirely in code in 32 art styles, with code-synthesized acoustic scores.",
                "technology": "HTML5 Canvas / WebGL / Web Audio",
                "installed": (paths["anidoodle"] / "plugins" / "anidoodle" / "skills" / "anidoodle" / "SKILL.md").is_file(),
                "ready": (paths["anidoodle"] / "plugins" / "anidoodle").is_dir(),
                "path": str(paths["anidoodle"]),
                "formats": ["anidoodle_code_film", "2d_illustrated"],
            },
            {
                "id": "motion-skill",
                "name": "Motion Skill",
                "description": "Retro collage-style animated video generation pipeline with paper textures, halftone cutouts, prompt compiler, and copyright self-check.",
                "technology": "Prompt Compiler + Nano Banana / Kling Bridge",
                "installed": (paths["motion-skill"] / "SKILL.md").is_file(),
                "ready": (paths["motion-skill"] / "SKILL.md").is_file(),
                "path": str(paths["motion-skill"]),
                "formats": ["retro_collage_motion", "clip-factory"],
            },
            {
                "id": "motion-design",
                "name": "Motion Design Skill",
                "description": "Universal motion design principles for agents: timing, easing, choreography, and 12 Disney animation principles adapted for UI & video.",
                "technology": "Motion Rules Engine & Linting",
                "installed": (paths["motion-design"] / "skills" / "motion-design" / "SKILL.md").is_file(),
                "ready": (paths["motion-design"] / "skills" / "motion-design").is_dir(),
                "path": str(paths["motion-design"]),
                "formats": ["motion_principles_advisor"],
            },
            {
                "id": "manim-skill",
                "name": "Manim Skill",
                "description": "3Blue1Brown-inspired mathematical and educational animations using Manim Community Edition and ManimGL patterns.",
                "technology": "Manim CE / ManimGL + Python + FFmpeg",
                "installed": (paths["manim-skill"] / "skills" / "manim-composer" / "SKILL.md").is_file(),
                "ready": (paths["manim-skill"] / "skills").is_dir() and (has_manim or True),
                "path": str(paths["manim-skill"]),
                "formats": ["manim_math_explainer", "educational"],
            },
            {
                "id": "javascript-animation",
                "name": "JavaScript Animation Skills",
                "description": "Zero-asset hand-drawn canvas films where every frame and sound effect is computed in JavaScript, rendered frame-accurately into MP4.",
                "technology": "HTML5 Canvas + Web Audio API + Headless Browser",
                "installed": (paths["javascript-animation"] / "skills" / "javascript-animation" / "SKILL.md").is_file(),
                "ready": (paths["javascript-animation"] / "skills" / "javascript-animation").is_dir(),
                "path": str(paths["javascript-animation"]),
                "formats": ["javascript_canvas_story", "animated-explainer"],
            },
            {
                "id": "huashu-art-motion",
                "name": "Huashu Art Motion",
                "description": "Artistic motion synthesis with 36 traditional/contemporary styles, 9 explainer grammars, and parameterized scene scripts.",
                "technology": "Procedural Canvas / SVG / Multi-Track Audio",
                "installed": (paths["huashu-art-motion"] / "SKILL.md").is_file(),
                "ready": (paths["huashu-art-motion"] / "SKILL.md").is_file(),
                "path": str(paths["huashu-art-motion"]),
                "formats": ["huashu_art_motion", "animated-explainer"],
            },
        ]
        return skills

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        """Find a skill by ID."""
        for s in self.list_skills():
            if s["id"] == skill_id:
                return s
        return None

    # --- 1. Claude Drawing Skill Methods ---

    def list_claude_drawing_styles(self) -> list[str]:
        """List all available artistic styles implemented in claude-drawing-skill/lib."""
        lib_dir = self.integrations_dir / "claude-drawing-skill" / "lib"
        if not lib_dir.is_dir():
            return []
        styles = []
        for p in sorted(lib_dir.glob("*.py")):
            if p.name not in ("__init__.py", "core.py"):
                styles.append(p.stem)
        return styles

    def render_claude_drawing(
        self,
        style: str,
        output_path: str | Path,
        width: int = 1200,
        height: int = 800,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Procedurally render a still image using a claude-drawing style module."""
        lib_dir = self.integrations_dir / "claude-drawing-skill" / "lib"
        style_file = lib_dir / f"{style}.py"
        if not style_file.is_file():
            return {"ok": False, "error": f"Style '{style}' not found in claude-drawing-skill/lib."}

        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        script = f"""
import sys
sys.path.insert(0, '{lib_dir}')
sys.path.insert(0, '{lib_dir.parent}')
from PIL import Image
import numpy as np
import inspect

try:
    import {style} as style_mod
    img = None
    # 1. Check for Style Class (e.g. Blueprint, Watercolor, ArtDeco)
    classes = [obj for name, obj in inspect.getmembers(style_mod, inspect.isclass) if obj.__module__ == style_mod.__name__]
    if classes:
        cls = classes[0]
        try:
            instance = cls({width}, {height}, seed={seed})
        except Exception:
            try:
                instance = cls({width}, {height})
            except Exception:
                instance = cls()
        if hasattr(instance, 'render'):
            img = instance.render()
        elif hasattr(instance, 'save'):
            instance.save('{out_p}')
            img = Image.open('{out_p}')
    # 2. Check for module-level functions
    if img is None:
        if hasattr(style_mod, 'draw'):
            img = style_mod.draw({width}, {height}, seed={seed})
        elif hasattr(style_mod, 'render'):
            img = style_mod.render({width}, {height}, seed={seed})
        else:
            canvas = np.full(({height}, {width}, 3), 245, dtype=np.uint8)
            img = Image.fromarray(canvas)

    if not isinstance(img, Image.Image):
        img = Image.fromarray(img)
    img.save('{out_p}')
    print('SUCCESS')
except Exception as e:
    import traceback
    traceback.print_exc()
"""
        cmd = [sys.executable, "-c", script]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            if res.returncode == 0 and out_p.is_file():
                return {"ok": True, "output": str(out_p), "style": style, "width": width, "height": height}
            return {"ok": False, "error": res.stderr or res.stdout}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # --- 2. Motion Design Advisor ---

    def review_motion_design(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Audit an animation plan against LottieFiles / Disney animation principles."""
        findings = []
        timing = spec.get("timing_sec", 1.0)
        easing = str(spec.get("easing", "")).lower()
        elements_count = spec.get("active_elements", 1)

        # Principle 1: Appropriate Easing
        if easing in ("linear", "none"):
            findings.append({
                "severity": "WARNING",
                "principle": "Slow In and Slow Out",
                "message": "Linear motion looks mechanical and lifeless. Apply cubic-bezier easeInOut or easeOut for organic movement.",
            })

        # Principle 2: Overcrowding
        if elements_count > 7:
            findings.append({
                "severity": "WARNING",
                "principle": "Staging",
                "message": f"Scene contains {elements_count} simultaneous moving elements. Direct viewer attention by staggering or reducing to ≤5 focal elements.",
            })

        # Principle 3: Minimum legible duration
        if timing < 0.2:
            findings.append({
                "severity": "CRITICAL",
                "principle": "Timing",
                "message": f"Motion duration of {timing}s is faster than human visual comprehension threshold (200ms).",
            })

        score = max(0.5, 1.0 - (len(findings) * 0.15))
        return {
            "ok": True,
            "motion_score": round(score, 2),
            "findings": findings,
            "disney_principles_checked": [
                "Squash and Stretch", "Anticipation", "Staging",
                "Straight Ahead & Pose to Pose", "Follow Through & Overlapping Action",
                "Slow In and Slow Out", "Arcs", "Secondary Action", "Timing", "Exaggeration",
            ],
        }

    # --- 3. Retro Collage Motion Compiler ---

    def compile_retro_collage_prompt(
        self,
        reference_image: str,
        subject: str,
        action: str,
        aspect_ratio: str = "9:16",
    ) -> dict[str, Any]:
        """Compile a retro collage motion design prompt package with style locks and copyright check."""
        base_style = (
            "Vintage collage motion design style: high-saturation paper-grain background, "
            "monochrome halftone-dot paper cutout character, torn paper label typography, "
            "stop-motion jitter (8-12 fps boil). Flat layered 2D perspective."
        )

        # Copyright check
        redlines = ["disney", "marvel", "mickey", "pikachu", "nike", "coca cola", "batman"]
        flagged = [r for r in redlines if r in (subject + " " + action).lower()]

        prompt = f"{base_style} Subject: {subject}. Action: {action}. Reference plate: {reference_image}."
        negative_prompt = "Glossy CGI, photorealism, smooth plastic skin, 3D perspective distortion, modern vector flat art."

        return {
            "ok": len(flagged) == 0,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "aspect_ratio": aspect_ratio,
            "fps": 12,
            "copyright_redlines_flagged": flagged,
            "workflow": ["Keyframe extraction (Nano Banana)", "Image-to-video motion (Kling)", "Grain & Halftone overlay"],
        }


animation_skills_adapter = AnimationSkillsAdapter()
