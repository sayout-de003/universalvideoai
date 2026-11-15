"""Phase 7 Verification: Automated Production QA Checks & Separation of Human Visual Approval."""

from __future__ import annotations

import subprocess
from pathlib import Path

from backend.db import get_conn, init_db
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project
from backend.orchestration.qa import record_human_visual_approval, run_qa_verification
from backend.services.character_asset_service import get_default_humanoid_asset, register_character_asset


def test_qa_detects_missing_corrupt_black_and_passes_valid_with_separate_human_approval(tmp_path: Path):
    init_db()
    proj = create_project(ProjectCreateRequest(prompt="QA test film", target_duration_sec=4))
    pid = proj["project"]["id"]
    try:
        # 1. Missing file
        r_missing = run_qa_verification(pid, tmp_path / "does_not_exist.mp4")
        assert r_missing["automated_qa_passed"] is False
        assert r_missing["human_visual_approved"] is False

        # 2. Corrupt file
        corrupt = tmp_path / "corrupt.mp4"
        corrupt.write_bytes(b"not a real mp4 file")
        r_corrupt = run_qa_verification(pid, corrupt)
        assert r_corrupt["automated_qa_passed"] is False

        # 3. Black frames
        black_mp4 = tmp_path / "black.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=640x360:d=2.5:r=24",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2.5",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(black_mp4),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        r_black = run_qa_verification(pid, black_mp4, expected_aspect_ratio="16:9", expected_resolution="640x360")
        assert r_black["automated_qa_passed"] is False
        black_chk = next(c for c in r_black["checks"] if c["name"] == "black_frame_check")
        assert black_chk["passed"] is False

        # 4. Valid video + character continuity + dialogue + lip-sync + wardrobe check
        glb = get_default_humanoid_asset()
        assert glb is not None
        register_character_asset(
            project_id=pid,
            name="Scout",
            mesh_path=glb,
            wardrobe_spec={"jacket": "olive"},
            voice_id="character_1",
            validate=False,
        )
        dlg_wav = tmp_path / "dlg.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=280:duration=1.5", "-ar", "44100", "-ac", "2", str(dlg_wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        valid_mp4 = tmp_path / "valid.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24:duration=2.5",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2.5",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(valid_mp4),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        # Wardrobe mismatch should fail
        r_wardrobe_bad = run_qa_verification(
            pid,
            valid_mp4,
            expected_aspect_ratio="16:9",
            expected_resolution="640x360",
            expected_duration_sec=2.5,
            expected_wardrobe={"Scout": {"jacket": "crimson"}},
        )
        assert r_wardrobe_bad["automated_qa_passed"] is False

        # Valid QA pass, still pending human visual approval
        r_ok = run_qa_verification(
            pid,
            valid_mp4,
            expected_aspect_ratio="16:9",
            expected_resolution="640x360",
            expected_duration_sec=2.5,
            dialogue_tracks=[{"speaker": "Scout", "wav_path": str(dlg_wav)}],
            lip_sync_frames=[{"frame": 1, "time_sec": 0.0, "open": 0.5}, {"frame": 24, "time_sec": 1.0, "open": 0.2}],
            expected_wardrobe={"Scout": {"jacket": "olive"}},
        )
        assert r_ok["automated_qa_passed"] is True, r_ok
        assert r_ok["human_visual_approved"] is False
        assert r_ok["approval_status"] == "PENDING_HUMAN_VISUAL_REVIEW"

        human = record_human_visual_approval(pid, r_ok["report_id"], approved=True, reviewer_notes="Visuals approved")
        assert human["human_visual_approved"] is True
        assert human["approval_status"] == "HUMAN_APPROVED"
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM projects WHERE id=?", (pid,))
