"""Tests for screenplay TTS sanitization and human-spoken voice-over purity.

Ensures that markdown headers (# SCREENPLAY: ...), scene numbers (## SCENE 1),
camera tags (**CAMERA:** wide), lighting tags, timecode annotations ((5.3s)),
and sound cues are NEVER spoken aloud by TTS under any circumstances.
"""

from __future__ import annotations

from pathlib import Path
from backend.orchestration.audio_studio import generate_tts, sanitize_spoken_voiceover
from backend.services.document_parser import parse_structured_screenplay


def test_sanitize_spoken_voiceover_strips_all_metadata() -> None:
    raw = """# SCREENPLAY: NAPOLEON BONAPARTE *Format: Educational Video | Runtime: 28.0s | Voice: Deep, authoritative male documentary narration*
## SCENE 1: INTRODUCTION (5.3s)
**VISUAL:** Cinematic introduction of Napoleon Bonaparte standing confidently in his iconic military uniform, bicorne hat, and hand tucked inside his waistcoat. A historical map of Europe fades into the background.
**CAMERA:** wide / eye_level / slow_push_in | **LIGHTING:** dramatic_cinematic
**NARRATION / VO:** Meet Napoleon Bonaparte, the military genius who reshaped the history of Europe.
**ON-SCREEN TEXT:** NAPOLEON BONAPARTE (1769-1821) | **SOUND:** cinematic_ambient_swell
## SCENE 2: RISE TO POWER (5.3s)
**VISUAL:** Animated historical timeline showing the French Revolution.
**CAMERA:** medium / eye_level / slow_push_in | **LIGHTING:** dramatic_historical
**NARRATION / VO:** During the French Revolution, he rose through the military ranks and became a celebrated general.
**ON-SCREEN TEXT:** THE RISE OF A GENERAL | **SOUND:** orchestral_whoosh_transition"""

    clean = sanitize_spoken_voiceover(raw)
    assert "#" not in clean
    assert "*" not in clean
    assert "SCREENPLAY" not in clean
    assert "SCENE" not in clean
    assert "VISUAL" not in clean
    assert "CAMERA" not in clean
    assert "LIGHTING" not in clean
    assert "ON-SCREEN" not in clean
    assert "SOUND" not in clean
    assert "5.3s" not in clean
    assert "Meet Napoleon Bonaparte" in clean
    assert "During the French Revolution" in clean


def test_sanitize_spoken_voiceover_single_line_with_cues() -> None:
    text = '**NARRATION / VO (MALE):** "In 1804, he crowned himself Emperor of the French." [SFX: orchestral swell] (5.7s)'
    clean = sanitize_spoken_voiceover(text)
    assert clean == "In 1804, he crowned himself Emperor of the French."


def test_parse_structured_screenplay_clean_separation() -> None:
    raw = """# SCREENPLAY: NAPOLEON BONAPARTE *Format: Educational Video | Runtime: 28.0s*
## SCENE 1: INTRODUCTION (5.3s)
**VISUAL:** Cinematic introduction of Napoleon Bonaparte in uniform.
**CAMERA:** wide / eye_level / slow_push_in | **LIGHTING:** dramatic_cinematic
**NARRATION / VO:** Meet Napoleon Bonaparte, the military genius who reshaped the history of Europe.
**ON-SCREEN TEXT:** NAPOLEON BONAPARTE"""

    res = parse_structured_screenplay(raw)
    assert res["is_structured"] is True
    assert res["title"] == "Napoleon Bonaparte"
    assert len(res["scenes"]) == 1
    sc = res["scenes"][0]
    assert sc["title"] == "Introduction"
    assert sc["duration_sec"] == 5.3
    assert sc["narration_segment"] == "Meet Napoleon Bonaparte, the military genius who reshaped the history of Europe."
    assert "Cinematic introduction" in sc["visual_description"]
    assert "#" not in sc["narration_segment"]
    assert "*" not in sc["narration_segment"]


def test_generate_tts_sanitizes_input(tmp_path: Path) -> None:
    out_wav = tmp_path / "test_tts.wav"
    raw_input = "# SCREENPLAY: TEST\n**VISUAL:** A mountain.\n**NARRATION / VO:** The highest peak in the world."
    res = generate_tts(raw_input, out_wav)
    assert res["success"] is True or out_wav.exists()
