"""Phase 3: Story Architect, Hollywood Screenplay Architect, Specialist Screenwriters, Script Doctor & Retention Editor."""

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
    "documentary": "Write an evidence-led Hollywood documentary screenplay with a central narrative thesis, chronology, dual male/female human perspective, and cited factual narration.",
    "historical": "Write a historical documentary screenplay distinguishing verified historical events from historical interpretation and reconstructed scenes.",
    "fiction_short_film": "Write a cinematic Hollywood fiction screenplay with character objectives, conflict, stakes, subtext, visual storytelling, and scene-to-scene causality.",
    "commercial": "Write a commercial script grounded in brand positioning, emotional motivation, product truth, demonstration, differentiation, and CTA.",
    "corporate_saas": "Write a corporate/SaaS explainer script focused on workflow pain points, product UI accuracy, proof, and business outcomes.",
    "educational": "Write an educational screenplay with clear learning objectives, prerequisite anchoring, concrete examples, visual demonstrations, and recap.",
    "music_video": "Write a music video treatment and beat-mapped visual script with motifs, choreography/movement, and rhythmic transitions.",
    "existing_footage": "Write an edit-decision screenplay strictly grounded in the user's uploaded source media inventory.",
    "character_animator": "Write a natural 2D character dialogue script with distinct voices, subtext, reactions, and expressive staging.",
    "anime_action": "Write a kinetic anime action script with dynamic stances, speed-lines, dramatic pauses, and decisive clash moments.",
    "scifi_cyberpunk": "Write an atmospheric sci-fi cyberpunk script with neon-drenched cityscapes, flying traffic, high-tech tension, and crisp narration.",
    "pixel_art_retro": "Write a retro 16-bit pixel art story script with crisp stage progression, vivid sprites, and punchy arcade pacing.",
}

_TRANSITION_CYCLE = ("smoothleft", "dissolve", "circleopen", "smoothright")

_DRAMATIC_PERSPECTIVES = (
    ("what everyone assumes at first glance", "the hidden physical mechanism operating beneath the surface"),
    ("the initial breakthrough moment", "the unexpected bottleneck that nearly stopped progress cold"),
    ("the human stakes on the ground", "the split-second decision that turned pressure into momentum"),
    ("the architecture of the system under load", "how each moving part locks together in real time"),
    ("the counter-intuitive truth specialists discovered", "why conventional approaches failed at the critical threshold"),
    ("the turning point where theory met reality", "the measurable ripple effect across the entire field"),
    ("the quiet preparation before the launch", "the irreversible chain reaction set in motion"),
    ("the competing forces colliding in the corridor", "the precision maneuver that cleared the obstacle"),
    ("the unseen telemetry guiding every adjustment", "how small calibration shifts prevented a cascade failure"),
    ("the emotional weight carried by the lead team", "the breakthrough signal that confirmed the new path"),
    ("the structural redesign forged under deadline", "how resilience replaced fragility in the final build"),
    ("the legacy left by that decisive hour", "what the next generation of builders must now confront"),
)


def _extract_subject(prompt: str) -> str:
    from backend.orchestration.audio_studio import sanitize_spoken_voiceover
    from backend.services.document_parser import clean_markdown_inline, parse_structured_screenplay

    parsed = parse_structured_screenplay(prompt)
    if parsed.get("is_structured") and parsed.get("subject") and not str(parsed["subject"]).lower().startswith("untitled"):
        sub = clean_markdown_inline(str(parsed["subject"]))
        # Strip prompt wrappers from parsed subject if any
        sub_cleaned = _strip_prompt_framing(sub)
        if sub_cleaned and len(sub_cleaned) >= 2:
            return sub_cleaned[:80]

    first_line = prompt.strip().splitlines()[0] if prompt.strip() else ""
    s = clean_markdown_inline(first_line)
    s = re.sub(r"^[#*\s]+(?:screenplay\s*:\s*)?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\*Format:.*$", "", s, flags=re.IGNORECASE).split("*")[0].split("|")[0].strip()
    s = _strip_prompt_framing(s)
    s = re.sub(r"\b\d+\s*-\s*(?:second|sec|minute|min|hour|hr)s?\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\b(?:faceless|youtube|shorts?|reels?|explaining|explain|word-by-word|captions?)\b",
        " ",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"^(?:SCREENPLAY\s*:|TITLE\s*:|SCENE\s*\d*\s*[:\-]?)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".!?*#")
    return s[:90] if len(s) >= 3 else "an everyday conversation"


def _strip_prompt_framing(raw: str) -> str:
    s = raw.strip()
    from backend.services.document_parser import clean_markdown_inline

    # Strip guide, guideline, and meta-prompt framing first
    s = re.sub(
        r"(?i)\b(?:\d+\s*-?\s*(?:sec|second|seconds|min|minute|minutes|s)\s*)?(?:screenplay|script|video|animation)?\s*(?:guide|guideline|guidelines|instruction|instructions|breakdown|prompt|template|spec|specification|structure)\b[:\-]?\s*",
        " ",
        s,
    )

    # Check for 'about ...', 'discussing ...', 'regarding ...', 'on the topic of ...'
    m = re.search(r"\b(?:about|discussing|regarding|exploring|on the topic of)\s+([^\n.]+)", s, flags=re.IGNORECASE)
    if m:
        topic = m.group(1).strip()
        topic = re.sub(r"\b(?:in|for|with)?\s*(?:2d|3d|animated|animation|video|film|a script|script|guide)\b", "", topic, flags=re.IGNORECASE).strip()
        topic = re.sub(r"\b(?:three|two|3|2)?\s*(?:people|characters|friends|persons)\s+talking(?:\s+to\s+each\s+other)?\b", "", topic, flags=re.IGNORECASE).strip()
        cleaned_topic = clean_markdown_inline(topic)
        cleaned_topic = re.sub(r"^(?:on|about|for|of|with|in)\s+", "", cleaned_topic, flags=re.IGNORECASE).strip()
        if len(cleaned_topic) >= 3:
            return cleaned_topic

    s = re.sub(r"^(?:i want to (?:create|make|produce)|create|make|produce|generate|build|write|tell)\s+(?:an?|the)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d+\s*-?\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(?:three|two|3|2)?\s*(?:people|characters|friends|persons)\s+talking(?:\s+to\s+each\s+other)?\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(?:2d|3d|pixar|anime|cartoon|animated|hand-drawn|whiteboard)\s*(?:animation|video|film|short)?\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(?:video|film|screenplay|story|animation|explainer|reel|short|documentary|script|a script|guide|guideline)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:on|about|for|of|with|in)\s+", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s+(?:on|about|for|of|with|in)$", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _short_subject(subject: str, max_words: int = 4) -> str:
    from backend.services.document_parser import clean_markdown_inline
    clean = clean_markdown_inline(subject)
    words = [w for w in clean.split() if w.lower() not in ("a", "an", "the", "#", "*")]
    return " ".join(words[:max_words]) or clean[:32] or "the story"


def _trim_to_word_budget(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    trimmed_words = words[:max_words]
    while len(trimmed_words) > 4 and trimmed_words[-1].lower().rstrip(".,;:") in (
        "for", "of", "the", "a", "an", "to", "in", "on", "with", "and", "or", "by", "from", "that", "which", "as",
    ):
        trimmed_words.pop()
    trimmed = " ".join(trimmed_words).rstrip(",;:")
    if not trimmed.endswith((".", "!", "?")):
        trimmed += "."
    return trimmed


def _cast_voice_for_scene(scene_idx: int, total_scenes: int, wtype: str, prompt: str, voice_mode: str = "auto") -> dict[str, str]:
    """Cast real human Male and Female neural voices per scene based on dramatic role and user choice."""
    low = prompt.lower()
    vm = (voice_mode or "auto").lower().strip()
    force_female_only = vm == "female" or "female only" in low or "only female" in low
    force_male_only = vm == "male" or "male only" in low or "only male" in low or "male documentary narration" in low

    if force_female_only:
        return {
            "voice_gender": "female",
            "voice_id": "narrator_warm" if scene_idx % 2 == 0 else "character_2",
            "speaker_name": "Female Narrator (AriaNeural)" if scene_idx % 2 == 0 else "Female Lead (JennyNeural)",
        }
    if force_male_only:
        return {
            "voice_gender": "male",
            "voice_id": "narrator_deep" if scene_idx % 2 == 0 else "character_1",
            "speaker_name": "Male Narrator (ChristopherNeural)" if scene_idx % 2 == 0 else "Male Lead (GuyNeural)",
        }

    # Hollywood dual-voice storytelling: alternate Male Anchor and Female Co-Narrator / Protagonist
    if wtype in ("fiction_short_film", "animation_piece"):
        if scene_idx == 0 or scene_idx == total_scenes - 1:
            return {"voice_gender": "male", "voice_id": "narrator_deep", "speaker_name": "Cinematic Narrator (Male)"}
        if scene_idx % 2 == 1:
            return {"voice_gender": "female", "voice_id": "character_2", "speaker_name": "Protagonist (Female)"}
        return {"voice_gender": "male", "voice_id": "character_1", "speaker_name": "Deuteragonist (Male)"}

    if scene_idx % 2 == 0:
        return {"voice_gender": "male", "voice_id": "narrator_deep", "speaker_name": "Lead Anchor (Male)"}
    return {"voice_gender": "female", "voice_id": "narrator_warm", "speaker_name": "Analytical Co-Narrator (Female)"}


def _select_scene_animation_mode(
    scene_idx: int,
    total_scenes: int,
    wtype: str,
    visual_style: str | None = None,
) -> tuple[str, str]:
    """Select between Pixel Art, 2D Illustrated, 3D Stylized, Hand-Drawn Storybook, Pixar 2D/3D, and Remotion data HUD."""
    vs = (visual_style or "").strip().lower()
    from backend.orchestration.engine_registry import VISUAL_STYLE_PROFILES
    profile = VISUAL_STYLE_PROFILES.get(vs)
    if profile:
        return profile["default_engine"], str(profile.get("hyperframes_theme") or vs)

    if wtype in ("animation_piece", "fiction_short_film"):
        return "hyperframes", "pixar_character_world"
    if wtype in ("commercial", "corporate_saas", "educational"):
        if scene_idx % 2 == 1:
            return "remotion", "kinetic_data_hud"
        return "hyperframes", "pixar_character_world"
    # Documentary / YouTube / Social: weave Pixar 2D/3D animated explainer scenes, Remotion charts, and archival cinema
    if scene_idx == 0:
        return "hyperframes", "pixar_character_world"
    if scene_idx % 3 == 1:
        return "remotion", "kinetic_data_hud"
    if scene_idx % 3 == 2:
        return "hyperframes", "painterly_parallax"
    return "hyperframes", "pixar_character_world"


def _try_llm_screenplay(
    subject: str,
    fmt_spec: dict[str, Any],
    brief: dict[str, Any],
    research_claims: list[dict[str, Any]],
    style_guide: str,
    num_scenes: int,
    words_per_scene: int,
    production_mode: str | None = None,
) -> list[dict[str, Any]] | None:
    """Use configured OpenAI / Anthropic / Ollama LLM if available; return None if offline or in free_open_source mode."""
    from backend.orchestration.engine_registry import is_free_open_source_mode

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
        f"title, purpose, narration_segment (~{words_per_scene} words, natural spoken English, no beat numbers), "
        f"visual_description, shot_type, camera_angle, camera_movement, lighting, on_screen_text, sound_cue, voice_gender (male or female)."
    )

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key and not is_free_open_source_mode(production_mode):
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_msg}],
                    "temperature": 0.65,
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
    prompt: str = "",
    voice_mode: str = "auto",
) -> list[dict[str, Any]]:
    """Hollywood-grade, skill-driven, research-grounded scene writer with Male/Female voice casting and 2D/3D animation cues."""
    beats = fmt_spec["structure"]
    wtype = fmt_spec["writer_type"]
    _preserve_wtypes = {
        "anime_action", "scifi_cyberpunk", "pixel_art_retro", "character_animator",
        "handdraw_explainer", "p5_cartoon_artist", "anidoodle_director",
        "code_animator", "huashu_director", "manim_mathematician",
    }
    if "animation" in fmt_spec["label"].lower() and wtype not in _preserve_wtypes:
        wtype = "animation_piece"
    verified_facts = [
        c["claim_text"]
        for c in research_claims
        if c.get("fact_check_decision") in ("PASS", "QUALIFY") and c.get("claim_text")
    ]
    tone = brief.get("tone") or "cinematic"
    audience = brief.get("audience") or "viewers"
    s_label = _short_subject(subject, 4) if len(subject.split()) > 4 else subject

    scenes: list[dict[str, Any]] = []
    for i in range(num_scenes):
        beat = beats[i % len(beats)]
        surface_angle, deep_mechanism = _DRAMATIC_PERSPECTIVES[i % len(_DRAMATIC_PERSPECTIVES)]
        chapter_num = (i // len(beats)) + 1
        fact_line = verified_facts[i] if i < len(verified_facts) else ""
        voice_cast = _cast_voice_for_scene(i, num_scenes, wtype, prompt or subject, voice_mode=voice_mode)
        anim_engine, anim_theme = _select_scene_animation_mode(i, num_scenes, wtype)
        transition = "cut" if i == 0 else _TRANSITION_CYCLE[(i - 1) % len(_TRANSITION_CYCLE)]

        if wtype == "short_form_social":
            if i == 0:
                narr = f"Why did {s_label} change every rule in seconds?"
                vis = f"Vertical 9:16 Pixar-grade 2D/3D animated hero reveal of {subject}, volumetric rim lighting, kinetic typography card, and fast camera push-in."
                shot, cam, light = "close_up", "low_angle", "high_contrast_neon"
            elif i == num_scenes - 1:
                narr = f"That decisive shift is why {s_label} still leads today."
                vis = f"Vertical 9:16 triumphant wide hero frame of {subject} with animated particle trails and a bold payoff callout."
                shot, cam, light = "medium_wide", "eye_level", "clean_studio"
            else:
                narr = fact_line or f"Even then, {s_label} turns {surface_angle} into momentum."
                vis = f"Dynamic 2D/3D motion-graphics breakdown of {subject} illustrating {deep_mechanism}, smooth parallax layers and spring-animated metrics."
                shot, cam, light = "medium", "eye_level", "vibrant_key"
        elif wtype in ("documentary", "historical"):
            if i == 0:
                narr = f"How did {s_label} evolve from vision into reality? {fact_line}".strip()
                vis = f"Sweeping cinematic establishing shot of {subject} with multi-plane parallax depth, golden-hour volumetric rays, and animated character staging."
                shot, cam, light = "extreme_wide", "eye_level", "golden_hour_cinematic"
            elif i == num_scenes - 1:
                narr = f"Today, the legacy of {s_label} defines what comes next."
                vis = f"Reflective dusk wide tableau over the living world of {subject}, slow crane pull-back across warm amber lights and horizon."
                shot, cam, light = "wide", "high_angle", "twilight_ambient"
            else:
                narr = fact_line or f"Beneath the surface of {s_label}, {deep_mechanism} changed everything."
                vis = f"Pixar-styled 2D/3D animated scene and data-timeline overlay tracing {deep_mechanism} in {subject}, motivated side-lighting and smooth lateral dolly."
                shot, cam, light = "medium", "low_angle", "chiaroscuro_documentary"
        elif wtype in ("commercial", "corporate_saas"):
            if i == 0:
                narr = f"Every team facing {s_label} hits the same wall—until now."
                vis = f"High-craft 2D/3D animated hero stage introducing {subject}, crisp volumetric shadows, glassmorphic HUD telemetry, smooth slider move."
                shot, cam, light = "medium_close", "eye_level", "soft_commercial_key"
            elif i == num_scenes - 1:
                narr = f"Built for {audience}, {s_label} turns complexity into speed."
                vis = f"Polished animated brand showcase for {subject} with kinetic KPI rings, luminous rim lighting, and confident push-in."
                shot, cam, light = "wide", "eye_level", "bright_brand_key"
            else:
                narr = fact_line or f"In practice, {s_label} automates {deep_mechanism} effortlessly."
                vis = f"Animated interactive workflow and metric visualization of {subject} executing {deep_mechanism}, clean accent highlights."
                shot, cam, light = "medium", "eye_level", "bright_studio"
        elif wtype == "youtube_longform":
            if i == 0:
                narr = f"Here is how {s_label} really works beneath the surface. {fact_line}".strip()
                vis = f"Cinematic 2D/3D animated hero stage of {subject}, kinetic chapter title card, then a motivated push-in toward the core mechanism."
                shot, cam, light = "wide", "eye_level", "clean_studio"
            elif i == num_scenes - 1:
                narr = f"Connect every layer of {s_label}, and the blueprint is clear."
                vis = f"Wide synthesis composition of {subject} with animated callout badges summarizing the complete arc."
                shot, cam, light = "medium_wide", "eye_level", "balanced_natural"
            else:
                narr = fact_line or f"Look closely at {s_label}, and you uncover {deep_mechanism}."
                vis = f"Multi-layer 2D/3D animated diagram and character walkthrough of {subject} demonstrating {deep_mechanism}."
                shot, cam, light = "medium", "eye_level", "bright_studio"
        elif wtype == "anime_action":
            if i == 0:
                narr = f"Beneath a burning horizon, steel meets silence as {s_label} begins."
                vis = f"Dynamic 2D anime wide standoff of {subject} at sunset: billowing cloaks, speed-line horizon, and blazing amber rim light."
                shot, cam, light = "wide", "low_angle", "sunset_rim"
            elif i == num_scenes - 1:
                narr = f"When the dust clears, only one blade remains standing."
                vis = f"Dramatic anime closing silhouette of {subject} against glowing embers and drifting petals."
                shot, cam, light = "medium_wide", "low_angle", "golden_ember"
            else:
                narr = fact_line or f"Steel flashes through the air as {s_label} tests every ounce of resolve."
                vis = f"High-energy 2D anime clash in {subject}: sakuga impact frames, camera whip-pan, and sparks across the frame."
                shot, cam, light = "medium", "dutch_angle", "high_contrast_sakuga"
        elif wtype == "scifi_cyberpunk":
            if i == 0:
                narr = f"Neon rain cuts through the midnight skyline of {s_label}."
                vis = f"Cyberpunk neon skyline of {subject} with flying cars weaving between holographic towers, cyan and magenta reflections."
                shot, cam, light = "extreme_wide", "low_angle", "cyberpunk_neon"
            elif i == num_scenes - 1:
                narr = f"Above the glowing towers, the city never truly sleeps."
                vis = f"Sweeping aerial pull-back over {subject} as flying traffic streams into the neon horizon."
                shot, cam, light = "wide", "high_angle", "neon_twilight"
            else:
                narr = fact_line or f"Deep inside the neon grid of {s_label}, every signal hides a secret."
                vis = f"Street-level cyberpunk tracking shot through {subject}: rain-slicked pavement, holographic billboards, and hovering vehicles."
                shot, cam, light = "medium", "eye_level", "magenta_cyan_neon"
        elif wtype == "pixel_art_retro":
            if i == 0:
                narr = f"High above the glowing skyline, {s_label} comes alive in crisp pixels."
                vis = f"16-bit pixel art establishing panorama of {subject}: dithered neon sky, chunky pixel sprites, and parallax city blocks."
                shot, cam, light = "wide", "eye_level", "retro_arcade_palette"
            elif i == num_scenes - 1:
                narr = f"Across every glowing rooftop, the pixel frontier shines bright."
                vis = f"Retro pixel art finale over {subject} with animated starfield, glowing windows, and arcade horizon."
                shot, cam, light = "medium_wide", "eye_level", "pixel_twilight"
            else:
                narr = fact_line or f"Through neon avenues and hovering traffic, {s_label} races forward."
                vis = f"Crisp 16-bit pixel art action view of {subject}: animated flying vehicles, pixel rain, and vibrant CRT glow."
                shot, cam, light = "medium", "eye_level", "neon_pixel_key"
        elif wtype in ("fiction_short_film", "animation_piece"):
            if i == 0:
                narr = f"In the quiet breath before everything changes, {s_label} steps forward."
                vis = f"Expressive 2D/3D animated wide establishing shot of {subject}: lead character in motion, volumetric atmosphere, warm key light against cool shadows."
                shot, cam, light = "wide", "low_angle", "moody_practical"
            elif i == num_scenes - 1:
                narr = f"As the dust settles, the story of {s_label} finds its lasting echo."
                vis = f"Heroic resting wide composition of the protagonist inside {subject}, breathing settling, golden rim light and atmospheric particles."
                shot, cam, light = "medium_wide", "eye_level", "soft_cinematic_key"
            else:
                narr = fact_line or f"With nowhere left to turn, {s_label} confronts {surface_angle} head on."
                vis = f"Expressive 2D/3D character acting and dynamic camera track through {subject}: articulated stride, parallax foreground/background planes, dramatic side key light."
                shot, cam, light = "medium", "eye_level", "dramatic_side_key"
        else:
            if i == 0:
                narr = f"To master {s_label}, start with the force driving the system."
                vis = f"Pixar-styled 2D/3D animated stage and interactive diagram introducing {subject}, volumetric lighting and smooth camera dolly."
                shot, cam, light = "wide", "eye_level", "clean_studio"
            elif i == num_scenes - 1:
                narr = f"Together, these principles of {s_label} unlock real-world results."
                vis = f"Animated visual synthesis card for {subject} with kinetic metrics, character silhouette, and warm closing gradient."
                shot, cam, light = "medium_wide", "eye_level", "balanced_natural"
            else:
                narr = fact_line or f"At the core of {s_label}, {deep_mechanism} drives the outcome."
                vis = f"Step-by-step 2D/3D animated breakdown of {subject} showing {deep_mechanism}, high-contrast callouts, and smooth lateral glide."
                shot, cam, light = "medium", "eye_level", "bright_studio"

        narr = _trim_to_word_budget(narr, max(8, words_per_scene))
        vis = f"{vis} Continuity: {subject} preserves consistent character design, palette, and lighting grade across shot {i + 1} ({beat})."
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
            "sound_cue": "ambient_swell" if i == 0 else ("subtle_chime" if i < num_scenes - 1 else "warm_resolve"),
            "transition": transition,
            "voice_gender": voice_cast["voice_gender"],
            "voice_id": voice_cast["voice_id"],
            "speaker_name": voice_cast["speaker_name"],
            "preferred_scene_engine": anim_engine,
            "animation_theme": anim_theme,
            "silent_action_sec": 0.45,
            "pause_sec": 0.35,
        })
    return scenes


def _dialogue_cast(scenes: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Keep the names written in the script. Do not invent a cast."""
    generic = ("narrator", "anchor", "co-narrator", "lead voice")
    names: list[str] = []
    for sc in scenes:
        name = str(sc.get("speaker_name") or "").strip()
        if not name or any(g in name.lower() for g in generic):
            continue
        if name not in names:
            names.append(name)
    cast: dict[str, dict[str, str]] = {}
    for index, name in enumerate(names):
        if index % 2 == 0:
            cast[name] = {"voice_gender": "male", "voice_id": "character_1", "speaker_name": name}
        else:
            cast[name] = {"voice_gender": "female", "voice_id": "character_2", "speaker_name": name}
    return cast


def _conversation_requested(prompt: str, format_key: str) -> bool:
    """Return True when the prompt or format calls for a multi-character dialogue."""
    if format_key in ("character_dialogue_2d", "character_conversation"):
        return True
    low = prompt.lower()
    return any(
        k in low
        for k in (
            "two people talking",
            "two characters talking",
            "three people talking",
            "three characters talking",
            "3 people talking",
            "3 characters talking",
            "people talking",
            "characters talking",
            "three people are talking",
            "dialogue between",
            "conversation between",
            "talking to each other",
            "people are talking",
        )
    )


def _build_conversation_scenes(
    subject: str,
    fmt_spec: dict[str, Any],
    num_scenes: int,
    words_per_scene: int,
    visual_style: str | None = None,
    prompt: str = "",
) -> list[dict[str, Any]]:
    """Build multi-character dialogue scenes with distinct voices and character presence."""
    topic = subject.strip() or "workplace job layoffs in the modern era"
    if re.fullmatch(r"(?:two people talking|three people talking|a script|an everyday conversation)", topic, re.IGNORECASE):
        topic = "the modern wave of corporate layoffs"
    
    is_trio = any(k in prompt.lower() for k in ("three", "3 people", "3 characters", "trio", "three people"))
    is_layoff = any(k in (prompt + " " + topic).lower() for k in ("layoff", "playoff", "job layout", "modern area", "modern era", "severance", "headcount"))
    
    if is_trio:
        trio_chars = ["Alex", "Maya", "Liam"]
        if is_layoff:
            turns = [
                ("Alex", "male", "character_1", 0, "Did you see the announcement about the modern corporate job layoffs? Not playoffs—real workforce reductions happening across the tech area."),
                ("Maya", "female", "character_2", 1, "I did, Alex. Entire departments were notified with zero warning as companies scramble to cut operational overhead."),
                ("Liam", "male", "character_3", 2, "It is a tough reality of modern business restructuring. The key right now is documenting our core impact and staying resilient."),
                ("Alex", "male", "character_1", 0, "Exactly, Liam. We need to upgrade our skills, support our displaced colleagues, and adapt to these modern market shifts."),
                ("Maya", "female", "character_2", 1, "Agreed. By staying informed, communicating openly, and looking out for one another, we can navigate through any corporate layoff."),
                ("Liam", "male", "character_3", 2, "Well said. Let's make sure our team has a clear strategy and keeps moving forward together."),
            ]
        else:
            turns = [
                ("Alex", "male", "character_1", 0, f"Wait, did you two look into {topic} this morning?"),
                ("Maya", "female", "character_2", 1, f"I did, and honestly, {topic} is moving faster than either of us expected."),
                ("Liam", "male", "character_3", 2, f"It impacts our entire team. We need a clear, coordinated strategy on {topic}."),
                ("Alex", "male", "character_1", 0, f"Agreed Liam. Where do we even start with {topic}?"),
                ("Maya", "female", "character_2", 1, f"Right here, one step at a time, before {topic} catches everyone off guard."),
                ("Liam", "male", "character_3", 2, f"Count me in. Together, our group can master {topic} completely."),
            ]
        eng, theme = _select_scene_animation_mode(0, num_scenes, fmt_spec["writer_type"], visual_style=visual_style or "2d_illustrated")
        scenes: list[dict[str, Any]] = []
        shot_styles = [
            ("medium_group_shot", "eye_level", "three_shot_balanced"),
            ("medium_close", "eye_level", "rule_of_thirds"),
            ("medium_two_shot", "slight_low_angle", "two_shot_focus"),
            ("wide_hero", "eye_level", "three_shot_balanced"),
        ]
        for i in range(max(3, num_scenes)):
            speaker, gender, voice_id, spk_idx, line = turns[i % len(turns)]
            narr = _trim_to_word_budget(line, max(8, words_per_scene))
            st_shot, st_cam, st_comp = shot_styles[i % len(shot_styles)]
            scenes.append({
                "title": f"Scene {i + 1}: {speaker}'s Perspective",
                "purpose": f"Three-person animated dialogue exchange ({speaker} speaking)",
                "narration_segment": narr,
                "visual_description": f"2D animated modern conference room with floor-to-ceiling glass windows and digital wall telemetry. Three colleagues (Alex in navy suit, Maya in magenta blazer, Liam in emerald vest with glasses) sit at a sleek boardroom table with open laptops. {speaker} gestures expressively with realistic lip-sync while the others listen.",
                "shot_type": st_shot,
                "camera_angle": st_cam,
                "camera_movement": "subtle_push_in",
                "lighting": "modern_office_key",
                "composition": st_comp,
                "on_screen_text": f"{speaker}: Modern Restructuring",
                "sound_cue": "ambient_office_tone",
                "transition": "cut" if i == 0 else _TRANSITION_CYCLE[(i - 1) % len(_TRANSITION_CYCLE)],
                "voice_gender": gender,
                "voice_id": voice_id,
                "speaker_name": speaker,
                "character_name": speaker,
                "three_people": True,
                "characters": trio_chars,
                "speaking_index": spk_idx,
                "preferred_scene_engine": "hyperframes",
                "animation_theme": "2d_illustrated",
                "visual_style": visual_style or "2d_illustrated",
                "silent_action_sec": 0.35,
                "pause_sec": 0.35,
            })
        return scenes

    turns = [
        ("Alex", "Maya", "male", "character_1", f"Wait, did you really look into {topic} this morning?"),
        ("Maya", "Alex", "female", "character_2", f"I did, and honestly, {topic} is moving faster than either of us expected."),
        ("Alex", "Maya", "male", "character_1", f"That changes everything. Where do we even start with {topic}?"),
        ("Maya", "Alex", "female", "character_2", f"Right here, one clear step at a time, before {topic} catches everyone off guard."),
        ("Alex", "Maya", "male", "character_1", f"Alright, I am in. Let us tackle {topic} together."),
        ("Maya", "Alex", "female", "character_2", f"Deal. Once we share what we found on {topic}, people will actually listen."),
    ]
    eng, theme = _select_scene_animation_mode(0, num_scenes, fmt_spec["writer_type"], visual_style=visual_style or "2d_illustrated")
    scenes: list[dict[str, Any]] = []
    for i in range(max(2, num_scenes)):
        speaker, partner, gender, voice_id, line = turns[i % len(turns)]
        narr = _trim_to_word_budget(line, max(8, words_per_scene))
        scenes.append({
            "title": f"{speaker} & {partner}",
            "purpose": "Two-character animated dialogue exchange",
            "narration_segment": narr,
            "visual_description": f"2D animated two-shot of {speaker} and {partner} talking expressively about {topic}; {speaker} speaks while {partner} reacts.",
            "shot_type": "medium_two_shot" if i in (0, num_scenes - 1) else "medium_close",
            "camera_angle": "eye_level",
            "camera_movement": "subtle_push_in",
            "lighting": "warm_illustrated_key",
            "composition": "two_shot_balanced",
            "on_screen_text": f"{speaker}: {topic[:36]}",
            "sound_cue": "ambient_room_tone",
            "transition": "cut" if i == 0 else _TRANSITION_CYCLE[(i - 1) % len(_TRANSITION_CYCLE)],
            "voice_gender": gender,
            "voice_id": voice_id,
            "speaker_name": speaker,
            "character_name": speaker,
            "partner_name": partner,
            "preferred_scene_engine": eng,
            "animation_theme": theme,
            "visual_style": visual_style or "2d_illustrated",
            "silent_action_sec": 0.25,
            "pause_sec": 0.25,
        })
    return scenes


def develop_and_write_screenplay(
    prompt: str,
    format_key: str,
    brief: dict[str, Any],
    research_claims: list[dict[str, Any]] | None = None,
    style_guide_md: str = "",
    uploaded_script: str | None = None,
    voice_mode: str = "auto",
    visual_style: str | None = None,
    production_mode: str | None = None,
) -> dict[str, Any]:
    """Run Story Architect -> Hollywood Screenplay Architect -> Script Doctor -> Evaluator."""
    from backend.orchestration.audio_studio import sanitize_spoken_voiceover
    from backend.services.document_parser import clean_markdown_inline, parse_structured_screenplay

    fmt_spec = get_format_spec(format_key)
    parsed_script = parse_structured_screenplay(uploaded_script or prompt)
    subject = (
        parsed_script.get("subject")
        if parsed_script.get("is_structured") and parsed_script.get("subject")
        else _extract_subject(prompt)
    )
    target_dur = float(
        brief.get("target_duration_sec")
        or parsed_script.get("duration_sec")
        or fmt_spec["default_duration_sec"]
    )
    claims = research_claims or []

    source_text = uploaded_script or prompt
    if parsed_script.get("is_structured") and parsed_script.get("scenes"):
        scenes = list(parsed_script["scenes"])
        author_mode = "user_structured_screenplay"
        dialogue_voices = _dialogue_cast(scenes)
        for i, sc in enumerate(scenes):
            sc["narration_segment"] = sanitize_spoken_voiceover(sc.get("narration_segment", ""), default="")
            cast = _cast_voice_for_scene(i, len(scenes), fmt_spec["writer_type"], source_text, voice_mode=voice_mode)
            eng, theme = _select_scene_animation_mode(i, len(scenes), fmt_spec["writer_type"], visual_style=visual_style)
            speaker = str(sc.get("speaker_name") or "")
            if dialogue_voices and speaker in dialogue_voices and voice_mode not in ("male", "female"):
                sc.update(dialogue_voices[speaker])
            elif voice_mode in ("male", "female", "dual"):
                sc["voice_gender"] = cast["voice_gender"]
                sc["voice_id"] = cast["voice_id"]
                sc["speaker_name"] = cast["speaker_name"]
            else:
                sc.setdefault("voice_gender", cast["voice_gender"])
                sc.setdefault("voice_id", cast["voice_id"])
                sc.setdefault("speaker_name", cast["speaker_name"])
            if visual_style and visual_style != "auto":
                sc["preferred_scene_engine"] = eng
                sc["animation_theme"] = theme
                sc["visual_style"] = visual_style
            else:
                sc.setdefault("preferred_scene_engine", eng)
                sc.setdefault("animation_theme", theme)
            sc.setdefault("transition", "cut" if i == 0 else _TRANSITION_CYCLE[(i - 1) % len(_TRANSITION_CYCLE)])
    else:
        density = float(fmt_spec.get("shot_density_sec") or 8.0)
        pacing = str(brief.get("pacing") or "balanced")
        if pacing == "fast":
            density = min(density, 3.0)
        elif pacing == "cinematic":
            density = max(density, 8.0)
        num_scenes = plan_scene_count(target_dur, density)
        per_scene_sec = max(2.5, target_dur / num_scenes)
        spoken_budget_sec = max(1.5, per_scene_sec - 0.8)
        words_per_scene = max(6, int(round((spoken_budget_sec / 60.0) * fmt_spec["wpm"])))

        if _conversation_requested(prompt, format_key):
            scenes = _build_conversation_scenes(
                subject,
                fmt_spec,
                max(3, num_scenes),
                words_per_scene,
                visual_style=visual_style if visual_style and visual_style != "auto" else None,
                prompt=prompt,
            )
            author_mode = "dialogue_script"
        else:
            scenes = _try_llm_screenplay(
                subject, fmt_spec, brief, claims, style_guide_md, num_scenes, words_per_scene, production_mode=production_mode
            )
            author_mode = "llm_specialist" if scenes else "hollywood_skill_architect"
            if not scenes:
                scenes = _build_specialist_scenes_offline(
                    subject, fmt_spec, brief, claims, num_scenes, words_per_scene, prompt=prompt, voice_mode=voice_mode
                )
                if visual_style and visual_style != "auto":
                    for i, sc in enumerate(scenes):
                        eng, theme = _select_scene_animation_mode(i, len(scenes), fmt_spec["writer_type"], visual_style=visual_style)
                        sc["preferred_scene_engine"] = eng
                        sc["animation_theme"] = theme
                        sc["visual_style"] = visual_style
            else:
                for i, sc in enumerate(scenes):
                    cast = _cast_voice_for_scene(i, len(scenes), fmt_spec["writer_type"], prompt, voice_mode=voice_mode)
                    eng, theme = _select_scene_animation_mode(i, len(scenes), fmt_spec["writer_type"], visual_style=visual_style)
                    sc.setdefault("voice_gender", cast["voice_gender"])
                    sc.setdefault("voice_id", cast["voice_id"])
                    sc.setdefault("speaker_name", cast["speaker_name"])
                    if visual_style and visual_style != "auto":
                        sc["preferred_scene_engine"] = eng
                        sc["animation_theme"] = theme
                        sc["visual_style"] = visual_style
                    else:
                        sc.setdefault("preferred_scene_engine", eng)
                        sc.setdefault("animation_theme", theme)
                    sc.setdefault("transition", "cut" if i == 0 else _TRANSITION_CYCLE[(i - 1) % len(_TRANSITION_CYCLE)])

    # Script Doctor + Audience Retention Editor: verify runtime & tighten/expand narration to hit target tolerance
    evaluation = evaluate_screenplay(fmt_spec["format_key"], {**brief, "target_duration_sec": target_dur}, scenes, claims)
    if author_mode != "user_structured_screenplay" and not evaluation["runtime_report"]["within_tolerance"]:
        actual = max(1.0, evaluation["runtime_report"]["estimated_total_sec"])
        scale = target_dur / actual
        for sc in scenes:
            sc["silent_action_sec"] = round(max(0.25, min(2.5, float(sc.get("silent_action_sec", 0.45)) * scale)), 2)
            if scale < 0.85:
                cur_words = len(sc["narration_segment"].split())
                sc["narration_segment"] = _trim_to_word_budget(sc["narration_segment"], max(6, int(cur_words * scale)))
        evaluation = evaluate_screenplay(fmt_spec["format_key"], {**brief, "target_duration_sec": target_dur}, scenes, claims)

    # Assign exact scene durations (preserve user scene duration if explicitly provided in structured screenplay)
    for idx, sc in enumerate(scenes):
        if author_mode == "user_structured_screenplay" and sc.get("duration_sec"):
            sc["duration_sec"] = round(float(sc["duration_sec"]), 2)
        else:
            sc["duration_sec"] = evaluation["runtime_report"]["scenes"][idx]["estimated_duration_sec"]
        sc["order_index"] = idx

    logline = f"A {fmt_spec['label'].lower()} exploring {subject} through {scenes[0]['title'].lower()} to {scenes[-1]['title'].lower()}."
    treatment = (
        f"# Story Treatment: {subject}\n\n"
        f"**Format:** {fmt_spec['label']} ({fmt_spec['aspect_ratio']})\n"
        f"**Target Runtime:** {target_dur:.0f}s (Estimated: {evaluation['runtime_report']['estimated_total_sec']:.1f}s)\n"
        f"**Narrative Arc:** {' -> '.join(s['title'] for s in scenes)}\n"
        f"**Voice Casting:** Dual Human Neural Voices (Male Anchor + Female Co-Narrator/Lead)\n\n"
        f"**Logline:** {logline}\n"
    )

    screenplay_md_lines = [f"# SCREENPLAY: {subject.upper()}", f"*Format: {fmt_spec['label']} | Runtime: {sum(float(s['duration_sec']) for s in scenes):.1f}s*", ""]
    for idx, sc in enumerate(scenes):
        screenplay_md_lines.extend([
            f"## SCENE {idx + 1}: {sc['title'].upper()} ({sc['duration_sec']:.1f}s) — [{sc.get('speaker_name', 'Narrator')} | Engine: {sc.get('preferred_scene_engine', 'hyperframes')} | Transition: {sc.get('transition', 'dissolve')}]",
            f"**VISUAL:** {sc['visual_description']}",
            f"**CAMERA:** {sc.get('shot_type', 'medium')} / {sc.get('camera_angle', 'eye_level')} / {sc.get('camera_movement', 'slow_push_in')} | **LIGHTING:** {sc.get('lighting', 'natural')}",
            f"**NARRATION / VO ({sc.get('voice_gender', 'male').upper()}):** {sc['narration_segment']}",
            f"**ON-SCREEN TEXT:** {sc.get('on_screen_text', '')} | **SOUND:** {sc.get('sound_cue', '')}",
            "",
        ])

    char_desc = str(parsed_script.get("character_description") or "")
    if not char_desc or "#" in char_desc or "SCENE" in char_desc or "Format:" in char_desc:
        char_desc = f"Locked visual identity for {subject}: consistent facial features, silhouette, wardrobe, and color palette across every scene."
    else:
        char_desc = clean_markdown_inline(char_desc)[:240]

    return {
        "subject": subject,
        "character_name": clean_markdown_inline(str(parsed_script.get("character_name") or subject))[:48],
        "character_description": char_desc,
        "format_spec": fmt_spec,
        "author_mode": author_mode,
        "logline": logline,
        "treatment_md": treatment,
        "screenplay_md": "\n".join(screenplay_md_lines),
        "scenes": scenes,
        "evaluation": evaluation,
        "runtime_report": evaluation["runtime_report"],
    }
