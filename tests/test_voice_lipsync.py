"""Phase 5 Verification: Per-Character Voice IDs, Dialogue Synthesis, Lip Sync & Audio Alignment."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from backend.db import get_conn, init_db
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project
from backend.services.voice_lip_sync_service import (
    align_and_mix_scene_dialogue,
    assign_character_voice,
    get_character_voice,
    synthesize_dialogue_lines,
)


def test_per_character_voice_dialogue_lipsync_and_audio_mix(tmp_path: Path):
    init_db()
    proj = create_project(ProjectCreateRequest(prompt="Dialogue lip-sync test", target_duration_sec=8))
    pid = proj["project"]["id"]
    try:
        v1 = assign_character_voice(pid, "Elena", "narrator_warm")
        v2 = assign_character_voice(pid, "Marcus", "character_1")
        assert v1["voice_id"] == "narrator_warm"
        assert v2["voice_id"] == "character_1"
        assert get_character_voice(pid, "Elena") == "narrator_warm"
        assert get_character_voice(pid, "Marcus") == "character_1"

        dlg = synthesize_dialogue_lines(
            project_id=pid,
            dialogue_lines=[
                {"speaker": "Elena", "text": "Welcome to the studio.", "expression": "happy"},
                {"speaker": "Marcus", "text": "All engines are online.", "expression": "focused"},
            ],
            output_dir=tmp_path / "dialogue",
            fps=24,
        )
        assert dlg["ok"] is True
        assert len(dlg["tracks"]) == 2
        assert dlg["tracks"][1]["start_sec"] > dlg["tracks"][0]["start_sec"]
        assert len(dlg["lip_sync_frames"]) > 10
        assert any(f["viseme"] != "REST" for f in dlg["lip_sync_frames"])

        # Create a short silent test video and align/mix dialogue onto it
        silent_mp4 = tmp_path / "silent.mp4"
        dur = max(2.0, dlg["total_duration_sec"])
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x112233:s=320x180:d={dur:.2f}:r=24",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent_mp4),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        mixed_mp4 = tmp_path / "mixed.mp4"
        mix_res = align_and_mix_scene_dialogue(
            dialogue_result=dlg,
            video_path=silent_mp4,
            output_mp4=mixed_mp4,
            stems_dir=tmp_path / "stems",
        )
        assert mix_res["ok"] is True, mix_res
        assert mixed_mp4.is_file()

        probe = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(mixed_mp4)],
                text=True,
            )
        )
        types = {s["codec_type"] for s in probe["streams"]}
        assert types == {"video", "audio"}
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM projects WHERE id=?", (pid,))
