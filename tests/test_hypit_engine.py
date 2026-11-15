"""Tests for Hypit clean-room integration engine.

Verifies SVML semantic script parsing, reference video cloning,
word-synchronized kinetic captions, and zero-waste variant generation.
"""

from __future__ import annotations

from pathlib import Path
from backend.services.hypit_engine import (
    analyze_and_clone_reference,
    generate_production_variants,
    generate_word_synchronized_captions,
    parse_semantic_script,
)


def test_parse_semantic_script() -> None:
    source = """[Role: Host (male)]
[Role: Co-Host (female)]

[Segment: The Hook]
Host: Every year, thousands of builders make the exact same mistake. @{reveal}

[Segment: The Solution]
Co-Host: But once you understand the underlying protocol, @{zoom} everything clicks into place.
"""
    parsed = parse_semantic_script(source)
    assert parsed["ok"] is True
    assert len(parsed["segments"]) == 2
    assert len(parsed["roles"]) == 2
    assert len(parsed["moments"]) == 2
    assert parsed["segments"][0]["title"] == "The Hook"
    assert parsed["segments"][0]["role"] == "Host"
    assert "every year" in parsed["segments"][0]["spoken_text"].lower()
    assert "@{" not in parsed["spoken_dialogue"]
    assert "[Segment" not in parsed["spoken_dialogue"]
    assert len(parsed["segments"][0]["tokens"]) > 0


def test_analyze_and_clone_reference() -> None:
    res = analyze_and_clone_reference(
        reference_path_or_url="https://example.com/demo_reference.mp4",
        target_prompt="Top 5 Breakthrough Renewable Energy Inventions",
        target_duration_sec=35.0,
    )
    assert res["ok"] is True
    assert "reference_metrics" in res
    assert "target_blueprint" in res
    blueprint = res["target_blueprint"]
    assert blueprint["style_archetype"] == "ranking_listicle"
    assert len(blueprint["scenes"]) >= 3
    assert blueprint["scenes"][0]["pacing_mode"] == "fast_cut"
    assert blueprint["scenes"][-1]["pacing_mode"] == "settling"


def test_generate_word_synchronized_captions(tmp_path: Path) -> None:
    tokens = [
        {"word": "Every", "start_sec": 0.0, "end_sec": 0.3},
        {"word": "second", "start_sec": 0.3, "end_sec": 0.6},
        {"word": "counts", "start_sec": 0.6, "end_sec": 0.9},
        {"word": "here.", "start_sec": 0.9, "end_sec": 1.2},
    ]
    res = generate_word_synchronized_captions(tokens, tmp_path, style="kinetic_highlight")
    assert res["ok"] is True
    assert res["cue_count"] >= 1
    vtt = Path(res["vtt_path"]).read_text(encoding="utf-8")
    srt = Path(res["srt_path"]).read_text(encoding="utf-8")
    assert "WEBVTT" in vtt
    assert "Every" in srt
    assert "counts" in srt


def test_generate_production_variants() -> None:
    # Test with non-existent project returns ok=False error gracefully
    res = generate_production_variants(
        base_project_id="non_existent_proj_123",
        variants_spec=[{"name": "Spanish Variant", "type": "language_swap", "language": "es"}],
    )
    assert res["ok"] is False
    assert "not found" in res["error"]
