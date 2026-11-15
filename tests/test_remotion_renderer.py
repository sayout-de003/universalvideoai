"""Phase 4 Verification: Real Remotion React Composition Rendering (Charts, Typography, Captions, Transitions)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from backend.services.remotion_renderer import get_remotion_status, render_remotion_scene


def test_remotion_is_installed_and_ready():
    st = get_remotion_status()
    assert st["available"] is True, st
    assert st["status"] == "READY"


def test_remotion_renders_chart_and_captions(tmp_path: Path):
    out_mp4 = tmp_path / "remotion_chart.mp4"
    res = render_remotion_scene(
        scene={
            "title": "Q4 Studio Growth",
            "on_screen_text": "Q4 Studio Growth",
            "visual_description": "Animated bar chart showing production speed",
            "narration_segment": "AI film production scales across engines with automated quality checks.",
            "duration_sec": 2.0,
            "chart_type": "bar_chart",
            "chart_data": [
                {"label": "AI Video", "value": 45},
                {"label": "Blender", "value": 78},
                {"label": "Remotion", "value": 94},
            ],
        },
        output_mp4=out_mp4,
        width=640,
        height=360,
        fps=24,
    )
    assert res["ok"] is True, res
    assert out_mp4.is_file() and out_mp4.stat().st_size > 2048

    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out_mp4)],
            text=True,
        )
    )
    v_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
    assert len(v_streams) == 1
    assert int(v_streams[0]["width"]) == 640
    assert int(v_streams[0]["height"]) == 360
