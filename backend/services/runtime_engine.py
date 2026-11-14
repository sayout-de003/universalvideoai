"""Phase 3: Duration & Runtime Intelligence Engine."""

from __future__ import annotations

from typing import Any


def estimate_spoken_seconds(text: str, wpm: int = 145) -> float:
    words = [w for w in text.strip().split() if w]
    if not words:
        return 0.0
    return round((len(words) / max(80, wpm)) * 60.0, 2)


def calculate_runtime_report(
    scenes: list[dict[str, Any]],
    target_duration_sec: float,
    wpm: int = 145,
    tolerance_pct: float = 0.20,
    credits_sec: float = 0.0,
) -> dict[str, Any]:
    """Calculate realistic runtime from spoken text, silent action, pauses, montage, and transitions."""
    scene_timings: list[dict[str, Any]] = []
    total_spoken = 0.0
    total_silent = 0.0
    total_pauses = 0.0
    total_transitions = 0.0

    for idx, sc in enumerate(scenes):
        narration = (sc.get("narration_segment") or "").strip()
        dialogue = sc.get("dialogue") or []
        dialogue_text = " ".join(d.get("line", "") for d in dialogue if isinstance(d, dict))
        spoken = estimate_spoken_seconds(f"{narration} {dialogue_text}".strip(), wpm=wpm)
        silent_action = float(sc.get("silent_action_sec", 0.5))
        pause_sec = float(sc.get("pause_sec", 0.35))
        trans_sec = 0.35 if idx > 0 else 0.0

        est_dur = round(max(2.0, spoken + silent_action + pause_sec), 2)
        total_spoken += spoken
        total_silent += silent_action
        total_pauses += pause_sec
        total_transitions += trans_sec

        scene_timings.append({
            "scene_index": idx,
            "scene_id": sc.get("id", f"sc_{idx}"),
            "title": sc.get("title", ""),
            "word_count": len(f"{narration} {dialogue_text}".split()),
            "spoken_sec": spoken,
            "silent_action_sec": silent_action,
            "pause_sec": pause_sec,
            "estimated_duration_sec": est_dur,
        })

    estimated_total = round(sum(s["estimated_duration_sec"] for s in scene_timings) + credits_sec, 2)
    diff_sec = round(estimated_total - target_duration_sec, 2)
    ratio_err = abs(diff_sec) / max(1.0, target_duration_sec)
    within_tolerance = ratio_err <= tolerance_pct

    return {
        "target_duration_sec": round(target_duration_sec, 2),
        "estimated_total_sec": estimated_total,
        "difference_sec": diff_sec,
        "tolerance_pct": tolerance_pct,
        "within_tolerance": within_tolerance,
        "wpm_assumed": wpm,
        "breakdown": {
            "spoken_sec": round(total_spoken, 2),
            "silent_action_sec": round(total_silent, 2),
            "pauses_sec": round(total_pauses, 2),
            "transitions_sec": round(total_transitions, 2),
            "credits_sec": round(credits_sec, 2),
        },
        "scenes": scene_timings,
    }
