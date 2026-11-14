"""Phase 3: Independent Screenplay Quality Evaluator with format-weighted rubrics and hard rejections."""

from __future__ import annotations

from typing import Any

from backend.services.format_catalog import get_format_spec
from backend.services.runtime_engine import calculate_runtime_report

BOILERPLATE_PHRASES = (
    "advancing the narrative with clear visual storytelling",
    "in this opening chapter, we explore the core story behind",
    "come together into a lasting takeaway",
)


def evaluate_screenplay(
    format_key: str,
    brief: dict[str, Any],
    scenes: list[dict[str, Any]],
    research_claims: list[dict[str, Any]] | None = None,
    characters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    spec = get_format_spec(format_key)
    rubric = spec["rubric"]
    target_dur = float(brief.get("target_duration_sec") or spec["default_duration_sec"])
    runtime = calculate_runtime_report(scenes, target_dur, wpm=spec["wpm"])

    hard_rejections: list[str] = []
    failed_scenes: list[dict[str, Any]] = []
    revisions: list[str] = []

    if not scenes or len(scenes) < 2:
        hard_rejections.append("Incomplete screenplay: fewer than 2 scenes generated.")

    if not runtime["within_tolerance"]:
        hard_rejections.append(
            f"Runtime outside tolerance: estimated {runtime['estimated_total_sec']}s vs target {runtime['target_duration_sec']}s."
        )
        revisions.append("Adjust narration word count per scene to match target runtime without artificial padding.")

    if spec["requires_research"] and research_claims:
        rejected_claims = [c for c in research_claims if c.get("fact_check_decision") == "REJECT"]
        if rejected_claims:
            hard_rejections.append(f"{len(rejected_claims)} unresolved critical factual claim(s) marked REJECT.")

    for idx, sc in enumerate(scenes):
        narr = (sc.get("narration_segment") or "").strip()
        vis = (sc.get("visual_description") or "").strip()
        if any(bp in narr.lower() for bp in BOILERPLATE_PHRASES):
            hard_rejections.append(f"Scene {idx + 1} contains generic boilerplate prose.")
            failed_scenes.append({"scene_index": idx, "title": sc.get("title"), "reason": "Generic boilerplate narration"})
        if len(vis) < 20:
            hard_rejections.append(f"Scene {idx + 1} visual description is too vague to translate into shots.")
            failed_scenes.append({"scene_index": idx, "title": sc.get("title"), "reason": "Insufficient visual direction"})

    # Score each rubric criterion deterministically from structural & content signals
    scores: dict[str, float] = {}
    first_narr = (scenes[0].get("narration_segment", "") if scenes else "")
    hook_ok = len(first_narr.split()) >= 6 and "?" in first_narr or len(first_narr) >= 40
    for criterion, weight in rubric.items():
        if criterion == "runtime_accuracy":
            err = abs(runtime["difference_sec"]) / max(1.0, target_dur)
            scores[criterion] = round(max(0.0, 1.0 - err * 2.0), 3)
        elif "hook" in criterion or "opening" in criterion:
            scores[criterion] = 0.88 if hook_ok else 0.50
        elif "factual" in criterion or "source" in criterion:
            has_sources = bool(research_claims and any(c.get("source_id") for c in research_claims))
            scores[criterion] = 0.86 if has_sources else 0.68
        else:
            avg_vis = sum(len((s.get("visual_description") or "").split()) for s in scenes) / max(1, len(scenes))
            scores[criterion] = 0.85 if avg_vis >= 8 else 0.60

    weighted_score = round(sum(scores[k] * w for k, w in rubric.items()), 3)
    passed = (not hard_rejections) and weighted_score >= spec["min_quality_score"]

    return {
        "passed": passed,
        "format_key": spec["format_key"],
        "weighted_score": weighted_score,
        "min_required_score": spec["min_quality_score"],
        "criterion_scores": scores,
        "hard_rejections": hard_rejections,
        "failed_scenes": failed_scenes,
        "suggested_revisions": revisions,
        "runtime_report": runtime,
    }
