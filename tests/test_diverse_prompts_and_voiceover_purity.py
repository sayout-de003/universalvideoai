"""Verification tests for diverse prompt routing, customizations, and voice-over purity."""

from __future__ import annotations

import re

from backend.orchestration.audio_studio import sanitize_spoken_voiceover
from backend.orchestration.engine_registry import select_render_engine
from backend.services.format_catalog import resolve_format
from backend.services.screenwriting_service import develop_and_write_screenplay

_META_FORBIDDEN = re.compile(
    r"\b(?:beat\s+\d+|at\s+beat|in\s+scene|30\s*sec|create\s+a|make\s+a|2d\s+animated\s+video|a\s+script|before\s+the\s+first\s+strike\s+fell)\b",
    re.IGNORECASE,
)


def _assert_clean_voiceover(scenes: list[dict]) -> None:
    assert len(scenes) >= 2
    for sc in scenes:
        narr = str(sc.get("narration_segment") or "").strip()
        assert narr, f"Empty narration in scene: {sc}"
        assert not _META_FORBIDDEN.search(narr), f"Meta/instruction leakage in narration: {narr!r}"


def test_two_people_talking_2d_dialogue():
    prompt = "two people talking 2d animated video a script"
    fmt = resolve_format(prompt)
    assert fmt == "character_dialogue_2d"

    res = develop_and_write_screenplay(
        prompt=prompt,
        format_key=fmt,
        brief={"target_duration_sec": 30.0, "tone": "conversational"},
        research_claims=[],
        style_guide_md="2D animated dialogue",
    )
    assert res["author_mode"] == "dialogue_script"
    scenes = res["scenes"]
    _assert_clean_voiceover(scenes)
    speakers = {s["speaker_name"] for s in scenes}
    voice_ids = {s["voice_id"] for s in scenes}
    assert len(speakers) >= 2
    assert len(voice_ids) >= 2
    assert all(s.get("partner_name") for s in scenes)


def test_two_people_talking_preserves_topic():
    prompt = "make a 30 sec 2d animated video of two people talking about climate change"
    res = develop_and_write_screenplay(
        prompt=prompt,
        format_key=resolve_format(prompt),
        brief={"target_duration_sec": 30.0},
        research_claims=[],
        style_guide_md="2D animated dialogue",
    )
    assert res["author_mode"] == "dialogue_script"
    joined = " ".join(s["narration_segment"] for s in res["scenes"]).lower()
    assert "climate change" in joined
    _assert_clean_voiceover(res["scenes"])


def test_cyberpunk_pixel_art_prompt():
    prompt = "create a 30 sec video of a futuristic cyberpunk city with flying cars in pixel art"
    fmt = resolve_format(prompt)
    assert fmt in ("pixel_art_retro", "scifi_cyberpunk")
    assert fmt != "educational_videos"

    engine, _ = select_render_engine(
        category="animation",
        prompt=prompt,
        visual_style="pixel_art",
    )
    assert engine in ("hyperframes", "libresprite")

    res = develop_and_write_screenplay(
        prompt=prompt,
        format_key=fmt,
        brief={"target_duration_sec": 30.0},
        research_claims=[],
        style_guide_md="pixel art cyberpunk",
        visual_style="pixel_art",
    )
    _assert_clean_voiceover(res["scenes"])


def test_anime_action_prompt():
    prompt = "anime battle between two swordsmen at sunset"
    fmt = resolve_format(prompt)
    assert fmt == "anime_action_scene"

    res = develop_and_write_screenplay(
        prompt=prompt,
        format_key=fmt,
        brief={"target_duration_sec": 30.0},
        research_claims=[],
        style_guide_md="anime",
        visual_style="anime",
    )
    _assert_clean_voiceover(res["scenes"])


def test_whiteboard_skill_routing():
    prompt = "handdraw whiteboard explainer about photosynthesis"
    fmt = resolve_format(prompt)
    assert fmt == "handdrawn_whiteboard"
    engine, _ = select_render_engine(category="animation", prompt=prompt)
    assert engine in ("handdraw", "hyperframes")


def test_sanitize_spoken_voiceover_strips_prompt_and_beat_wrappers():
    cleaned_prompt = sanitize_spoken_voiceover("create a 30 sec video of a futuristic cyberpunk city")
    assert "30 sec" not in cleaned_prompt.lower()
    assert "create a" not in cleaned_prompt.lower()
    assert "futuristic cyberpunk city" in cleaned_prompt.lower()

    cleaned_beat = sanitize_spoken_voiceover("At beat 2, the neon skyline ignites.")
    assert not cleaned_beat.lower().startswith("at beat")
    assert "neon skyline ignites" in cleaned_beat.lower()


def test_screenplay_guide_framing_is_never_spoken_and_supports_three_people():
    from backend.orchestration.audio_studio import contains_screenplay_meta
    from backend.services.document_parser import parse_structured_screenplay

    prompt = "30 sec screenplay guide: two or more people talking about coffee in an office"
    res = develop_and_write_screenplay(
        prompt=prompt,
        format_key=resolve_format(prompt),
        brief={"target_duration_sec": 30.0},
        research_claims=[],
    )
    _assert_clean_voiceover(res["scenes"])
    speakers = {sc.get("speaker_name") for sc in res["scenes"]}
    assert len(speakers) >= 3
    for sc in res["scenes"]:
        spoken = sc["narration_segment"].lower()
        assert not contains_screenplay_meta(spoken), spoken
        assert "screenplay" not in spoken
        assert "guide" not in spoken
        assert "30 sec" not in spoken

    # Structured scene with SETTING/GUIDE metadata and no quotes must not speak metadata
    parsed = parse_structured_screenplay("Scene 1 (0-5s):\nSETTING: Office\nGUIDE: Keep it punchy\nVISUAL: People sit at a table.")
    assert parsed["scenes"][0]["narration_segment"] == ""

    assert sanitize_spoken_voiceover("30 sec screenplay guide. Alex: Let us grab coffee.") == "Let us grab coffee."


def test_stage_directions_and_conversational_conference_staging():
    from backend.orchestration.audio_studio import contains_screenplay_meta, sanitize_spoken_voiceover
    from backend.services.hyperframes_renderer import _PIXAR_MOTION_TEMPLATE

    # All bracketed & parenthetical stage directions + expanded spec/template meta are stripped
    raw = "30 sec screenplay guidelines: Alex (leaning forward nervously): [SFX: coffee cup clinks] Wait, did you see the layoff memo?"
    cleaned = sanitize_spoken_voiceover(raw, default="")
    assert cleaned == "Wait, did you see the layoff memo?", cleaned
    assert contains_screenplay_meta("production spec for 30 sec screenplay template")

    # Three-person conference conversation uses natural pacing & varied shot framing
    prompt = "Three people in a conference room talking about corporate layoffs"
    res = develop_and_write_screenplay(
        prompt=prompt,
        format_key=resolve_format(prompt),
        brief={"target_duration_sec": 30.0},
        research_claims=[],
    )
    assert len(res["scenes"]) >= 4
    shots = {sc.get("shot_type") for sc in res["scenes"]}
    assert "medium_three_shot" in shots
    assert "medium_close_speaker" in shots
    for sc in res["scenes"]:
        assert sc.get("silent_action_sec") == 0.35
        assert sc.get("pause_sec") == 0.35
        assert "conference room" in (sc.get("visual_description") or "").lower()

    # HyperFrames 2D renderer includes conference room & conversational character, without floating mouth bug
    assert "drawOfficeConferenceBackground" in _PIXAR_MOTION_TEMPLATE
    assert "drawConversationalCharacter" in _PIXAR_MOTION_TEMPLATE
    assert "charY - charScale * 16" not in _PIXAR_MOTION_TEMPLATE
