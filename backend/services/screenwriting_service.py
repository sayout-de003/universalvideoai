"""Phase 3: Story Architect, 10 Specialist Screenwriters, Script Doctor & Audience Retention Editor."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
from typing import Any

import requests

from backend.services.format_catalog import get_format_spec
from backend.services.runtime_engine import calculate_runtime_report
from backend.services.script_evaluator import evaluate_screenplay

SPECIALIST_PROMPTS: dict[str, str] = {
    "short_form_social": "Write a high-retention vertical short-form script with a 0-2s visual hook, tight narrative compression, pattern interrupts, on-screen text, and a sharp payoff.",
    "youtube_longform": "Write a chaptered YouTube long-form script with an opening promise, curiosity loops without clickbait, structured evidence, and B-roll/visual cues.",
    "documentary": "Write an evidence-led documentary screenplay with a central narrative thesis, chronology, human perspective, archival/B-roll direction, and cited factual narration.",
    "historical": "Write a historical documentary screenplay distinguishing verified historical events from historical interpretation and reconstructed scenes.",
    "fiction_short_film": "Write a cinematic fiction screenplay with character objectives, conflict, stakes, subtext, visual storytelling, and scene-to-scene causality.",
    "commercial": "Write a commercial script grounded in brand positioning, emotional motivation, product truth, demonstration, differentiation, and CTA.",
    "corporate_saas": "Write a corporate/SaaS explainer script focused on workflow pain points, product UI accuracy, proof, and business outcomes.",
    "educational": "Write an educational screenplay with clear learning objectives, prerequisite anchoring, concrete examples, visual demonstrations, and recap.",
    "music_video": "Write a music video treatment and beat-mapped visual script with motifs, choreography/movement, and rhythmic transitions.",
    "existing_footage": "Write an edit-decision screenplay strictly grounded in the user's uploaded source media inventory.",
}


def _extract_subject(prompt: str) -> str:
    s = re.sub(
        r"^(?:i want to (?:create|make|produce)|create|make|produce|generate|build)\s+(?:a|an|the)?\s*",
        "",
        prompt.strip(),
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"^(?:(?:cinematic|short|long|animated|educational|30-second|10-second|60-second|10-minute|5-minute)\s+)*"
        r"(?:documentary|video|film|reel|short|commercial|ad|explainer|trailer|story)\s+(?:about|on|for|of)\s+",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\b\d+\s*-\s*(?:second|sec|minute|min|hour|hr)s?\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\b(?:faceless|youtube|shorts?|reels?|explaining|explain|how|with|word-by-word|captions?|about)\b",
        " ",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\s+", " ", s).strip().rstrip(".!?")
    return s if len(s) >= 3 else prompt.strip().rstrip(".!?")


def _trim_to_word_budget(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    trimmed_words = words[:max_words]
    while len(trimmed_words) > 4 and trimmed_words[-1].lower().rstrip(".,;:") in ("for", "of", "the", "a", "an", "to", "in", "on", "with", "and", "or", "by", "from"):
        trimmed_words.pop()
    trimmed = " ".join(trimmed_words).rstrip(",;:")
    if not trimmed.endswith((".", "!", "?")):
        trimmed += "."
    return trimmed


def _try_llm_screenplay(
    subject: str,
    fmt_spec: dict[str, Any],
    brief: dict[str, Any],
    research_claims: list[dict[str, Any]],
    style_guide: str,
    num_scenes: int,
    words_per_scene: int,
) -> list[dict[str, Any]] | None:
    """Use configured OpenAI / Anthropic / Ollama LLM if available; return None if offline."""
    writer_type = fmt_spec["writer_type"]
    sys_prompt = SPECIALIST_PROMPTS.get(writer_type, SPECIALIST_PROMPTS["documentary"])
    claims_text = "\n".join(f"- {c['claim_text']}" for c in research_claims[:6]) or "None provided."
    user_msg = (
        f"Format: {fmt_spec['label']} ({fmt_spec['aspect_ratio']})\n"
        f"Subject: {subject}\n"
        f"Target duration: {brief.get('target_duration_sec', fmt_spec['default_duration_sec'])}s\n"
        f"Audience: {brief.get('audience', 'General')}\n"
        f"Tone: {brief.get('tone', 'Cinematic')}\n"
        f"Verified facts:\n{claims_text}\n"
        f"Style guide:\n{style_guide[:400]}\n"
        f"Return STRICT JSON array of {num_scenes} scenes. Each item must have keys: "
        f"title, purpose, narration_segment (~{words_per_scene} words), visual_description, "
        f"shot_type, camera_angle, camera_movement, lighting, on_screen_text, sound_cue."
    )

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_msg}],
                    "temperature": 0.6,
                },
                timeout=25,
            )
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"]
                m = re.search(r"\[.*\]", raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    if isinstance(parsed, list) and len(parsed) >= 2:
                        return parsed
        except Exception:
            pass

    if shutil.which("ollama"):
        try:
            r = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={"model": "llama3.2", "prompt": f"{sys_prompt}\n\n{user_msg}", "stream": False},
                timeout=20,
            )
            if r.status_code == 200:
                raw = r.json().get("response", "")
                m = re.search(r"\[.*\]", raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    if isinstance(parsed, list) and len(parsed) >= 2:
                        return parsed
        except Exception:
            pass
    return None


# shortcut: 48-shot cap matches this host's sequential render budget; raise it when shots render in parallel.
_SHOT_CAP = 48


def plan_scene_count(target_dur: float, shot_density_sec: float) -> int:
    """Plan enough shots that a scene stays near the format's shot length, never a handful of multi-minute slabs."""
    density = max(4.0, float(shot_density_sec or 8.0))
    count = max(3, int(round(max(5.0, target_dur) / density)))
    if count < _SHOT_CAP and target_dur / count > 12.0:
        count = min(_SHOT_CAP, int(math.ceil(target_dur / 12.0)))
    return min(_SHOT_CAP, count)


def _build_specialist_scenes_offline(
    subject: str,
    fmt_spec: dict[str, Any],
    brief: dict[str, Any],
    research_claims: list[dict[str, Any]],
    num_scenes: int,
    words_per_scene: int,
) -> list[dict[str, Any]]:
    """Deterministic, format-authentic, research-grounded scene writer (zero boilerplate)."""
    beats = fmt_spec["structure"]
    wtype = fmt_spec["writer_type"]
    if "animation" in fmt_spec["label"].lower():
        wtype = "animation_piece"
    verified_facts = [
        c["claim_text"]
        for c in research_claims
        if c.get("fact_check_decision") in ("PASS", "QUALIFY") and c.get("source_id")
    ]
    tone = brief.get("tone") or "cinematic"
    audience = brief.get("audience") or "curious viewers"

    scenes: list[dict[str, Any]] = []
    for i in range(num_scenes):
        beat = beats[i % len(beats)]
        fact_line = verified_facts[i % len(verified_facts)] if verified_facts else ""

        if wtype == "short_form_social":
            if i == 0:
                narr = f"How did {subject} reshape history in less than two decades?"
                vis = f"Vertical 9:16 extreme close-up reveal of {subject}, rapid whip-pan into crisp kinetic typography, high-contrast rim light."
                shot, cam, light = "close_up", "low_angle", "high_contrast_neon"
            elif i == num_scenes - 1:
                narr = f"And that is why {subject} still defines ambition and strategy today."
                vis = f"Vertical 9:16 hero wide shot of {subject} resolving into a bold closing title card and payoff badge."
                shot, cam, light = "medium_wide", "eye_level", "clean_studio"
            elif i == 1:
                narr = fact_line or f"It started with an unlikely rise—turning chaos into unprecedented momentum."
                vis = f"Dynamic vertical motion graphic illustrating the origins and early rise of {subject}, punch-in zoom on key visual detail."
                shot, cam, light = "medium", "eye_level", "vibrant_key"
            else:
                narr = fact_line or f"At the peak of power, one decisive turning point changed everything."
                vis = f"High-contrast dramatic split-screen highlighting the climax and turning point of {subject}, kinetic data callout."
                shot, cam, light = "medium_close", "low_angle", "dramatic_side_key"
        elif wtype in ("documentary", "historical"):
            if i == 0:
                narr = f"How did {subject} transform from a quiet experiment into a defining force of our era? {fact_line}".strip()
                vis = f"Sweeping atmospheric wide establishing shot depicting {subject}, golden-hour directional light, slow dolly push-in, subtle film grain."
                shot, cam, light = "extreme_wide", "eye_level", "golden_hour_cinematic"
            elif i == num_scenes - 1:
                narr = f"Today, the trajectory of {subject} stands as both a milestone and an open question for what comes next."
                vis = f"Reflective dusk wide shot over the evolving landscape of {subject}, slow crane pull-back, warm amber practicals."
                shot, cam, light = "wide", "high_angle", "twilight_ambient"
            else:
                narr = fact_line or f"Behind the headlines of {subject}, engineers, communities, and policy decisions collided at a decisive turning point."
                vis = f"Archival-inspired medium shot paired with crisp data-timeline overlay tracing {subject}, motivated side-lighting and slow pan."
                shot, cam, light = "medium", "low_angle", "chiaroscuro_documentary"
        elif wtype in ("commercial", "corporate_saas"):
            if i == 0:
                narr = f"Every team dealing with {subject} hits the same bottleneck—until the workflow itself is reimagined."
                vis = f"Clean modern hero frame introducing {subject} tension, shallow depth of field, crisp architectural shadows, smooth slider move."
                shot, cam, light = "medium_close", "eye_level", "soft_commercial_key"
            elif i == num_scenes - 1:
                narr = f"Built for {audience}, {subject} turns complexity into measurable momentum from day one."
                vis = f"Polished brand lockup and hero product showcase for {subject}, luminous rim lighting, confident push-in."
                shot, cam, light = "wide", "eye_level", "bright_brand_key"
            else:
                narr = f"With {subject}, every step becomes visible, verifiable, and faster in real-world operation."
                vis = f"Focused macro and UI/workflow demonstration of {subject} in action, clean accent highlights and smooth tracking shot."
                shot, cam, light = "medium", "eye_level", "bright_studio"
        elif wtype == "youtube_longform":
            if i == 0:
                narr = f"By the end of this, you will see exactly how {subject} works, and where the usual explanation stops. {fact_line}".strip()
                vis = f"Open on a clear hero frame of {subject}, title held for a beat, then a motivated push-in toward the detail that carries the chapter."
                shot, cam, light = "wide", "eye_level", "clean_studio"
            elif i == num_scenes - 1:
                narr = f"That is the through-line of {subject}: the promise from the opening, now tied to a specific takeaway."
                vis = f"Return to the opening frame of {subject}, same grade and wardrobe, with the takeaway set in large type beside the subject."
                shot, cam, light = "medium_wide", "eye_level", "balanced_natural"
            else:
                narr = fact_line or f"Chapter beat: {beat}. Here is the next concrete piece of {subject}, shown before it is named."
                vis = f"B-roll and a diagram of {subject} for '{beat}', same palette as the opening, lateral move across the evidence."
                shot, cam, light = "medium", "eye_level", "bright_studio"
        elif wtype == "music_video":
            if i == 0:
                narr = f"{subject}."
                vis = f"Performance-wide of the artist in the world of {subject}, hard front light, a move that lands on the first downbeat."
                shot, cam, light = "wide", "low_angle", "high_contrast_neon"
            elif i == num_scenes - 1:
                narr = f"{subject}."
                vis = f"Final pose of the same performer in {subject}, same costume, light blooming out as the last hit lands."
                shot, cam, light = "medium_wide", "eye_level", "high_contrast_neon"
            else:
                narr = f"{beat}."
                vis = f"Cut on the beat: {beat} inside {subject}, same costume and set, camera move changes while the wardrobe does not."
                shot, cam, light = "medium", "eye_level", "dramatic_side_key"
        elif wtype == "existing_footage":
            narr = fact_line or f"Use the supplied footage for {beat}: keep the original action of {subject} and cut only for clarity."
            vis = f"Edit the user's clip of {subject} for '{beat}'. Match the source framing. Do not replace it with a generated scene when the file is present."
            shot, cam, light = "medium", "eye_level", "match_source"
        elif wtype == "animation_piece":
            if i == 0:
                narr = f"This is {subject}."
                vis = f"Character intro of {subject} in a held pose, full silhouette readable, flat consistent colors, a small anticipatory settle before the action."
                shot, cam, light = "medium_wide", "eye_level", "clean_toon_key"
            elif i == num_scenes - 1:
                narr = f"And that is how {subject} lands."
                vis = f"Payoff pose of the same character design for {subject}, same colors and proportions, held for the button."
                shot, cam, light = "medium", "eye_level", "clean_toon_key"
            else:
                narr = fact_line or f"{subject} — {beat.lower()}."
                vis = f"The same character performs '{beat}' in {subject}. One action, same model sheet, background holds while the pose changes."
                shot, cam, light = "medium", "eye_level", "clean_toon_key"
        elif wtype == "fiction_short_film":
            if i == 0:
                narr = f"Before dawn breaks over {subject}, a single choice sets an irreversible chain of events in motion."
                vis = f"Anamorphic wide shot establishing the world of {subject}, cool blue ambient shadows contrasting a single warm practical lamp."
                shot, cam, light = "wide", "low_angle", "moody_practical"
            elif i == num_scenes - 1:
                narr = f"In the quiet aftermath of {subject}, everything that once seemed certain now looks unmistakably different."
                vis = f"Intimate close-up on the protagonist within {subject}, slow rack focus, lingering atmospheric light."
                shot, cam, light = "close_up", "eye_level", "soft_cinematic_key"
            else:
                narr = f"As pressure mounts around {subject}, unspoken tension surfaces and forces a decisive confrontation."
                vis = f"Over-the-shoulder medium tracking shot inside {subject}, dramatic motivated side light, deliberate camera push."
                shot, cam, light = "medium", "eye_level", "dramatic_side_key"
        else:
            if i == 0:
                narr = f"To truly understand {subject}, start with the single mechanism that makes the entire system work."
                vis = f"Crisp visual diagram and atmospheric hero stage introducing {subject}, clean geometric framing and smooth zoom."
                shot, cam, light = "wide", "eye_level", "clean_studio"
            elif i == num_scenes - 1:
                narr = f"Put together, these principles of {subject} give {audience} a clear mental model you can apply immediately."
                vis = f"Structured visual recap card summarizing {subject} with animated callouts and warm closing gradient."
                shot, cam, light = "medium_wide", "eye_level", "balanced_natural"
            else:
                narr = fact_line or f"Watch how each component of {subject} interacts under real conditions to produce the outcome."
                vis = f"Step-by-step animated breakdown of {subject}, high-contrast vector callouts, smooth lateral camera glide."
                shot, cam, light = "medium", "eye_level", "bright_studio"

        narr = _trim_to_word_budget(narr, max(8, words_per_scene))
        narr = f"{narr} ({beat}, {i + 1}.)".replace("..", ".")
        vis = f"{vis} Continuity: {subject} keeps the same identity, wardrobe, and grade. Shot {i + 1}, {beat}."
        scenes.append({
            "title": f"{beat}",
            "purpose": f"Deliver '{beat}' for {fmt_spec['label']}",
            "narration_segment": narr,
            "visual_description": vis,
            "shot_type": shot,
            "camera_angle": cam,
            "camera_movement": "slow_push_in" if "cinematic" in tone or wtype in ("documentary", "fiction_short_film") else "smooth_pan",
            "lighting": light,
            "composition": "rule_of_thirds",
            "on_screen_text": beat[:48],
            "sound_cue": "ambient_swell" if i == 0 else ("whoosh_transition" if i < num_scenes - 1 else "warm_resolve"),
            "silent_action_sec": 0.45,
            "pause_sec": 0.35,
        })
    return scenes


def develop_and_write_screenplay(
    prompt: str,
    format_key: str,
    brief: dict[str, Any],
    research_claims: list[dict[str, Any]] | None = None,
    style_guide_md: str = "",
) -> dict[str, Any]:
    """Run Story Architect -> Specialist Screenwriter -> Script Doctor -> Evaluator."""
    fmt_spec = get_format_spec(format_key)
    subject = _extract_subject(prompt)
    target_dur = float(brief.get("target_duration_sec") or fmt_spec["default_duration_sec"])

    num_scenes = plan_scene_count(target_dur, float(fmt_spec.get("shot_density_sec") or 8.0))

    per_scene_sec = max(2.5, target_dur / num_scenes)
    spoken_budget_sec = max(1.5, per_scene_sec - 0.8)
    words_per_scene = max(6, int(round((spoken_budget_sec / 60.0) * fmt_spec["wpm"])))

    claims = research_claims or []
    scenes = _try_llm_screenplay(subject, fmt_spec, brief, claims, style_guide_md, num_scenes, words_per_scene)
    author_mode = "llm_specialist" if scenes else "deterministic_specialist"
    if not scenes:
        scenes = _build_specialist_scenes_offline(subject, fmt_spec, brief, claims, num_scenes, words_per_scene)

    # Script Doctor + Audience Retention Editor: verify runtime & tighten/expand narration to hit target tolerance
    evaluation = evaluate_screenplay(fmt_spec["format_key"], {**brief, "target_duration_sec": target_dur}, scenes, claims)
    if not evaluation["runtime_report"]["within_tolerance"]:
        # Proportional Script Doctor pacing pass
        actual = max(1.0, evaluation["runtime_report"]["estimated_total_sec"])
        scale = target_dur / actual
        for sc in scenes:
            sc["silent_action_sec"] = round(max(0.25, min(2.5, float(sc.get("silent_action_sec", 0.45)) * scale)), 2)
            if scale < 0.85:
                cur_words = len(sc["narration_segment"].split())
                sc["narration_segment"] = _trim_to_word_budget(sc["narration_segment"], max(6, int(cur_words * scale)))
        evaluation = evaluate_screenplay(fmt_spec["format_key"], {**brief, "target_duration_sec": target_dur}, scenes, claims)

    # Assign exact scene durations from runtime report
    for idx, sc in enumerate(scenes):
        sc["duration_sec"] = evaluation["runtime_report"]["scenes"][idx]["estimated_duration_sec"]
        sc["order_index"] = idx

    logline = f"A {fmt_spec['label'].lower()} exploring {subject} through {fmt_spec['structure'][0].lower()} to {fmt_spec['structure'][-1].lower()}."
    treatment = (
        f"# Story Treatment: {subject}\n\n"
        f"**Format:** {fmt_spec['label']} ({fmt_spec['aspect_ratio']})\n"
        f"**Target Runtime:** {target_dur:.0f}s (Estimated: {evaluation['runtime_report']['estimated_total_sec']:.1f}s)\n"
        f"**Narrative Arc:** {' -> '.join(fmt_spec['structure'])}\n\n"
        f"**Logline:** {logline}\n"
    )

    screenplay_md_lines = [f"# SCREENPLAY: {subject.upper()}", f"*Format: {fmt_spec['label']} | Runtime: {evaluation['runtime_report']['estimated_total_sec']:.1f}s*", ""]
    for idx, sc in enumerate(scenes):
        screenplay_md_lines.extend([
            f"## SCENE {idx + 1}: {sc['title'].upper()} ({sc['duration_sec']:.1f}s)",
            f"**VISUAL:** {sc['visual_description']}",
            f"**CAMERA:** {sc.get('shot_type', 'medium')} / {sc.get('camera_angle', 'eye_level')} / {sc.get('camera_movement', 'slow_push_in')} | **LIGHTING:** {sc.get('lighting', 'natural')}",
            f"**NARRATION / VO:** {sc['narration_segment']}",
            f"**ON-SCREEN TEXT:** {sc.get('on_screen_text', '')} | **SOUND:** {sc.get('sound_cue', '')}",
            "",
        ])

    return {
        "subject": subject,
        "format_spec": fmt_spec,
        "author_mode": author_mode,
        "logline": logline,
        "treatment_md": treatment,
        "screenplay_md": "\n".join(screenplay_md_lines),
        "scenes": scenes,
        "evaluation": evaluation,
        "runtime_report": evaluation["runtime_report"],
    }
