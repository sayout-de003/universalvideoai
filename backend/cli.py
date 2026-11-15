"""CLI entry point for Antigravity & terminal users to produce, download, and share videos."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from backend.config import ensure_directories
from backend.db import init_db
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project, get_project_detail, run_production


def create_share_bundle(project_id: str) -> Path:
    """Package final video, subtitles, audio stems, and production report into a shareable ZIP."""
    detail = get_project_detail(project_id)
    if not detail:
        raise ValueError(f"Project '{project_id}' not found")
    ws = Path(detail["project"]["workspace_dir"])
    bundle_path = ws / "deliverables" / f"{project_id}_share_bundle.zip"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for folder in ("exports", "subtitles", "stems", "deliverables"):
            sub = ws / folder
            if not sub.exists():
                continue
            for f in sub.rglob("*"):
                if f.is_file() and f.resolve() != bundle_path.resolve():
                    zf.write(f, arcname=f"{folder}/{f.name}")
    return bundle_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Universal AI Video Production Studio CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    prod = sub.add_parser("produce", help="Produce a complete video from a natural-language prompt")
    prod.add_argument("prompt", help="Natural-language video description")
    prod.add_argument("--duration", type=float, default=None, help="Target duration in seconds")
    prod.add_argument("--aspect", default="16:9", choices=["16:9", "9:16", "1:1"])
    prod.add_argument("--engine", default=None, help="Preferred render engine (ffmpeg, hyperframes, threejs, remotion)")
    prod.add_argument("--language", default="en", help="Narration language code")
    prod.add_argument("--subtitles", default="en", help="Comma-separated subtitle language codes")
    prod.add_argument("--bundle", action="store_true", help="Create a shareable ZIP bundle")

    anim = sub.add_parser("animate", help="Compile a painterly 2D Animated Short Film package (/animate)")
    anim.add_argument("idea", help="One-sentence film idea")
    anim.add_argument("--duration", type=int, default=30, choices=[10, 15, 30], help="Duration in seconds (10, 15, or 30)")
    anim.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"], help="Aspect ratio (16:9 or 9:16)")
    anim.add_argument("--project-id", default="animated_short", help="Project folder name under projects/ (creates references/, prompts/, renders/, final/)")
    anim.add_argument("--execute-plates", action="store_true", help="Generate reference plates using configured cloud image provider")

    sk_parser = sub.add_parser("animation", help="Claude Animation Skills Suite")
    sk_sub = sk_parser.add_subparsers(dest="animation_cmd", required=True)

    sk_sub.add_parser("list", help="List all 9 integrated Claude Animation Skills")
    sk_sub.add_parser("styles", help="List 83 styles in Claude Drawing Skill")

    sk_draw = sk_sub.add_parser("draw", help="Procedurally render an illustration in any Claude Drawing style")
    sk_draw.add_argument("style", help="Style slug (e.g. blueprint, artdeco, bauhaus)")
    sk_draw.add_argument("output", help="Output image file path (.png)")
    sk_draw.add_argument("--width", type=int, default=1200)
    sk_draw.add_argument("--height", type=int, default=800)

    sk_rev = sk_sub.add_parser("review", help="Audit motion design plan against Disney & Lottie principles")
    sk_rev.add_argument("--timing", type=float, default=1.0, help="Movement duration in seconds")
    sk_rev.add_argument("--easing", default="easeInOut", help="Easing curve")
    sk_rev.add_argument("--elements", type=int, default=1, help="Simultaneous moving elements")

    args = parser.parse_args()
    ensure_directories()
    init_db()

    if args.command == "animate":
        from backend.services.animated_short_film_service import build_animated_short_package

        pkg = build_animated_short_package(
            idea=args.idea,
            duration_sec=args.duration,
            aspect_ratio=args.aspect,
            project_id=args.project_id,
            execute_plates=args.execute_plates,
        )
        print(json.dumps(pkg, indent=2))
        return

    if args.command == "animation":
        from backend.integrations.animation_skills_adapter import animation_skills_adapter

        if args.animation_cmd == "list":
            skills = animation_skills_adapter.list_skills()
            print(json.dumps({"count": len(skills), "skills": skills}, indent=2))
            return

        if args.animation_cmd == "styles":
            styles = animation_skills_adapter.list_claude_drawing_styles()
            print(json.dumps({"count": len(styles), "styles": styles}, indent=2))
            return

        if args.animation_cmd == "draw":
            res = animation_skills_adapter.render_claude_drawing(
                style=args.style,
                output_path=args.output,
                width=args.width,
                height=args.height,
            )
            print(json.dumps(res, indent=2))
            return

        if args.animation_cmd == "review":
            res = animation_skills_adapter.review_motion_design({
                "timing_sec": args.timing,
                "easing": args.easing,
                "active_elements": args.elements,
            })
            print(json.dumps(res, indent=2))
            return

    if args.command == "produce":
        res_map = {"16:9": "1920x1080", "9:16": "1080x1920", "1:1": "1080x1080"}
        created = create_project(
            ProjectCreateRequest(
                prompt=args.prompt,
                target_duration_sec=args.duration,
                aspect_ratio=args.aspect,
                resolution=res_map[args.aspect],
                preferred_render_engine=args.engine,
                language=args.language,
                subtitle_languages=[s.strip() for s in args.subtitles.split(",") if s.strip()],
            )
        )
        pid = created["project"]["id"]
        done = run_production(pid, resume=False)
        ws = Path(done["project"]["workspace_dir"])
        qa = done["qa_reports"][0] if done["qa_reports"] else {}
        bundle_path = create_share_bundle(pid) if args.bundle else None

        output = {
            "project_id": pid,
            "title": done["project"]["title"],
            "status": done["project"]["status"],
            "category": done["project"]["category"],
            "render_engine": done["project"]["render_engine"],
            "qa_passed": bool(qa.get("passed")),
            "qa_summary": qa.get("summary", ""),
            "final_video": str(ws / "exports" / "final_production.mp4"),
            "subtitles_dir": str(ws / "subtitles"),
            "share_bundle_zip": str(bundle_path) if bundle_path else None,
        }
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
