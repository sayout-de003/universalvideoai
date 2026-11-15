"""Adapter for Lemo-Opuscar (99 Code-Drawn Film Styles, Director/Technique Guides & Frame-Deterministic Renderer)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.config import LEMO_OPUSCAR_DIR, detect_chromium_path


class LemoOpuscarAdapter:
    def __init__(self, root_dir: Path = LEMO_OPUSCAR_DIR) -> None:
        self.root_dir = root_dir

    def is_available(self) -> bool:
        return (self.root_dir / "AGENTS.md").is_file() and (self.root_dir / "styles").is_dir()

    def get_status(self) -> dict[str, Any]:
        avail = self.is_available()
        has_node_modules = (self.root_dir / "node_modules" / "playwright-core").is_dir()
        styles = self.list_styles()["styles"] if avail else []
        return {
            "available": avail,
            "root_dir": str(self.root_dir),
            "renderer_ready": avail and has_node_modules and shutil.which("node") is not None,
            "style_count": len(styles),
            "guides": {
                "agents": str(self.root_dir / "AGENTS.md"),
                "director": str(self.root_dir / "DIRECTOR.md"),
                "technique": str(self.root_dir / "TECHNIQUE.md"),
                "my_styles": str(self.root_dir / "MY-STYLES.md"),
            },
        }

    def list_styles(self, category: str | None = None, query: str | None = None) -> dict[str, Any]:
        if not self.is_available():
            return {"total": 0, "categories": [], "styles": []}

        styles_dir = self.root_dir / "styles"
        items: list[dict[str, Any]] = []
        categories: set[str] = set()
        cat_filter = (category or "").strip().lower()
        q_filter = (query or "").strip().lower()

        for sj in sorted(styles_dir.glob("*/style.json")):
            if sj.parent.name.startswith("_"):
                continue
            try:
                data = json.loads(sj.read_text(encoding="utf-8"))
            except Exception:
                continue
            cat_en = str(data.get("category_en") or "")
            if cat_en:
                categories.add(cat_en)
            if cat_filter and cat_filter not in cat_en.lower() and cat_filter not in str(data.get("category_cn") or "").lower():
                continue
            if q_filter:
                haystack = " ".join([
                    str(data.get("slug") or ""),
                    str(data.get("en") or ""),
                    str(data.get("cn") or ""),
                    cat_en,
                    str(data.get("line") or ""),
                    " ".join(data.get("uses") or []),
                ]).lower()
                if q_filter not in haystack:
                    continue
            items.append({
                "slug": data.get("slug", sj.parent.name),
                "num": data.get("num"),
                "en": data.get("en"),
                "cn": data.get("cn"),
                "category_en": cat_en,
                "category_cn": data.get("category_cn"),
                "line": data.get("line"),
                "uses": data.get("uses", []),
                "needs": data.get("needs", []),
                "style_md_path": str(sj.parent / "STYLE.md"),
            })

        return {
            "total": len(items),
            "categories": sorted(categories),
            "styles": items,
        }

    def get_style(self, slug_or_name: str) -> dict[str, Any]:
        if not self.is_available():
            return {"ok": False, "error": "Lemo-Opuscar library is not installed in integrations/lemo-opuscar"}

        needle = slug_or_name.strip().lower()
        styles_dir = self.root_dir / "styles"
        matched_dir: Path | None = None
        if (styles_dir / needle / "STYLE.md").is_file():
            matched_dir = styles_dir / needle
        else:
            for sj in sorted(styles_dir.glob("*/style.json")):
                if sj.parent.name.startswith("_"):
                    continue
                try:
                    data = json.loads(sj.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if needle in (
                    str(data.get("slug") or "").lower(),
                    str(data.get("en") or "").lower(),
                    str(data.get("cn") or "").lower(),
                ):
                    matched_dir = sj.parent
                    break

        if not matched_dir:
            return {"ok": False, "error": f"Style '{slug_or_name}' not found"}

        style_json = {}
        sj_path = matched_dir / "style.json"
        if sj_path.is_file():
            style_json = json.loads(sj_path.read_text(encoding="utf-8"))
        style_md = (matched_dir / "STYLE.md").read_text(encoding="utf-8") if (matched_dir / "STYLE.md").is_file() else ""
        demo_md = (matched_dir / "DEMO.md").read_text(encoding="utf-8") if (matched_dir / "DEMO.md").is_file() else ""
        return {
            "ok": True,
            "slug": matched_dir.name,
            "metadata": style_json,
            "style_md": style_md,
            "demo_md": demo_md,
            "paths": {
                "style_dir": str(matched_dir),
                "style_md": str(matched_dir / "STYLE.md"),
                "demo_md": str(matched_dir / "DEMO.md"),
                "director_md": str(self.root_dir / "DIRECTOR.md"),
                "technique_md": str(self.root_dir / "TECHNIQUE.md"),
                "core_dir": str(self.root_dir / "core"),
            },
        }

    def render_page_to_video(
        self,
        page_dir: Path,
        output_mp4: Path,
        fps: int = 24,
        size: str = "1280x720",
        workers: int = 2,
    ) -> dict[str, Any]:
        """Render an Opuscar HTML/Canvas/WebGL film directory (with window.READY & window.render(t)) to MP4."""
        if not self.is_available():
            return {"ok": False, "reason": "Lemo-Opuscar library unavailable"}
        page_path = Path(page_dir).resolve()
        if not (page_path / "index.html").is_file():
            return {"ok": False, "reason": f"index.html not found in {page_path}"}

        output_mp4 = Path(output_mp4).resolve()
        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        if not env.get("PLAYWRIGHT_CHROME"):
            chrome = detect_chromium_path()
            if chrome:
                env["PLAYWRIGHT_CHROME"] = chrome

        cmd = [
            "node",
            "core/render/video.mjs",
            str(page_path),
            "--fps",
            str(fps),
            "--size",
            size,
            "--workers",
            str(workers),
            "--out",
            str(output_mp4),
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.root_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0 or not output_mp4.is_file():
                return {"ok": False, "reason": (proc.stderr or proc.stdout)[-400:]}
            return {"ok": True, "output": str(output_mp4), "engine": "lemo_opuscar"}
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}


lemo_opuscar_adapter = LemoOpuscarAdapter()
