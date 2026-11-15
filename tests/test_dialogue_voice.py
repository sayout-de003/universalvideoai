"""Voice speaks the script. A 2D conversation is two people, not a 30s screenplay read-through."""

from backend.orchestration.audio_studio import sanitize_spoken_voiceover
from backend.services.document_parser import parse_structured_screenplay
from backend.services.screenwriting_service import develop_and_write_screenplay


def test_fountain_dialogue_is_spoken_and_directions_are_not() -> None:
    raw = """INT. CAFE - DAY

Alex walks to the window.

ALEX
We have to leave now.

JORDAN
Then we go together.
"""
    parsed = parse_structured_screenplay(raw)
    spoken = [sc["narration_segment"] for sc in parsed["scenes"]]
    assert spoken == ["We have to leave now.", "Then we go together."]
    assert "2D" not in parsed["scenes"][0]["visual_description"]
    assert parsed["scenes"][0]["speaker_name"] == "Alex"
    assert parsed["scenes"][1]["speaker_name"] == "Jordan"
    blob = " ".join(spoken)
    assert "walks to the window" not in blob
    assert "INT." not in blob
    assert sum(sc["duration_sec"] for sc in parsed["scenes"]) < 30


def test_chosen_style_locks_the_picture_and_the_voice_follows_the_prompt() -> None:
    pkg = develop_and_write_screenplay(
        "A lighthouse keeper watches a storm roll over the harbor",
        "fiction_short_films",
        {"target_duration_sec": 24, "pacing": "fast"},
        [],
        visual_style="pixel_art",
    )
    scenes = pkg["scenes"]
    assert len(scenes) >= 3
    assert {sc["visual_style"] for sc in scenes} == {"pixel_art"}
    assert {sc["preferred_scene_engine"] for sc in scenes} == {"hyperframes"}
    spoken = " ".join(sc["narration_segment"] for sc in scenes).lower()
    assert "lighthouse" in spoken or "lighthouse" in pkg["subject"].lower()
    assert "alex" not in spoken and "jordan" not in spoken
    assert "SCREENPLAY" not in spoken and "VISUAL" not in spoken


def test_a_script_keeps_its_speakers_and_uses_the_chosen_style() -> None:
    pkg = develop_and_write_screenplay(
        "MAYA\nThe harbor lights just went out.\nSAM\nThen we take the lamp and go down.",
        "animation_motion_graphics",
        {"target_duration_sec": 20},
        [],
        visual_style="hand_drawn_storybook",
    )
    spoken = [sc["narration_segment"] for sc in pkg["scenes"]]
    assert spoken == ["The harbor lights just went out.", "Then we take the lamp and go down."]
    assert {sc["speaker_name"] for sc in pkg["scenes"]} == {"Maya", "Sam"}
    assert {sc["visual_style"] for sc in pkg["scenes"]} == {"hand_drawn_storybook"}
    assert {sc["preferred_scene_engine"] for sc in pkg["scenes"]} == {"hyperframes"}


def test_stage_direction_is_not_spoken() -> None:
    assert sanitize_spoken_voiceover("We see two people enter the room.", default="") == ""
    assert sanitize_spoken_voiceover("**CAMERA:** wide shot of the cafe", default="") == ""
