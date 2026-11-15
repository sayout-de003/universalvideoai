"""Per-Character Voice IDs, Dialogue Synthesis, Phoneme/Viseme Timing Extraction, Lip Sync & Audio Alignment."""

from __future__ import annotations

import math
import re
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any

from backend.db import get_conn, init_db
from backend.orchestration.audio_studio import generate_tts, mix_audio_stems, probe_duration

_DEFAULT_VOICE_POOL = ("character_1", "character_2", "narrator_warm", "narrator_deep")

_CHAR_TO_VISEME = {
    "a": "AA", "e": "EE", "i": "IY", "o": "OH", "u": "UW",
    "b": "BMP", "m": "BMP", "p": "BMP",
    "f": "FV", "v": "FV",
    "l": "LN", "n": "LN", "t": "TH", "d": "TH", "s": "SZ", "z": "SZ",
}


def assign_character_voice(
    project_id: str,
    character_name: str,
    voice_id: str,
    voice_provider: str = "local",
) -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, voice_id, voice_provider FROM characters WHERE project_id=? AND lower(name)=lower(?)",
            (project_id, character_name),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE characters SET voice_id=?, voice_provider=? WHERE id=?",
                (voice_id, voice_provider, row["id"]),
            )
            return {"character_id": row["id"], "name": row["name"], "voice_id": voice_id, "voice_provider": voice_provider}
        cid = f"char_{abs(hash((project_id, character_name))) % 10**8}"
        conn.execute(
            "INSERT INTO characters (id, project_id, name, voice_id, voice_provider) VALUES (?, ?, ?, ?, ?)",
            (cid, project_id, character_name, voice_id, voice_provider),
        )
    return {"character_id": cid, "name": character_name, "voice_id": voice_id, "voice_provider": voice_provider}


def get_character_voice(project_id: str, character_name: str) -> str:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT voice_id FROM characters WHERE project_id=? AND lower(name)=lower(?)",
            (project_id, character_name),
        ).fetchone()
    if row and row["voice_id"] and row["voice_id"] != "default":
        return str(row["voice_id"])
    idx = abs(hash(character_name.lower())) % len(_DEFAULT_VOICE_POOL)
    return _DEFAULT_VOICE_POOL[idx]


def extract_phoneme_and_lip_sync_timings(
    wav_path: Path,
    text: str,
    fps: int = 24,
    expression: str = "neutral",
) -> list[dict[str, Any]]:
    """Extract per-frame mouth openness & viseme timings from real WAV amplitude + text phonemes."""
    if not wav_path.is_file():
        return []

    duration = probe_duration(wav_path)
    if duration <= 0.0:
        return []

    total_frames = max(1, int(round(duration * fps)))
    amplitudes: list[float] = [0.0] * total_frames

    try:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
        if sampwidth == 2 and n_frames > 0:
            samples = struct.unpack(f"<{n_frames * n_channels}h", raw)
            mono = samples[::n_channels] if n_channels > 1 else samples
            win = max(1, len(mono) // total_frames)
            peaks = []
            for i in range(total_frames):
                chunk = mono[i * win : (i + 1) * win]
                if chunk:
                    rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
                    peaks.append(rms)
                else:
                    peaks.append(0.0)
            max_p = max(peaks) if peaks else 1.0
            scale = 1.0 / max(0.05, max_p)
            amplitudes = [round(min(1.0, p * scale), 3) for p in peaks]
    except Exception:
        amplitudes = [0.4 if i % 3 else 0.1 for i in range(total_frames)]

    letters = re.sub(r"[^a-z]", "", text.lower()) or "a"
    frames: list[dict[str, Any]] = []
    for f_idx in range(total_frames):
        amp = amplitudes[f_idx]
        char_idx = min(len(letters) - 1, int((f_idx / total_frames) * len(letters)))
        ch = letters[char_idx]
        viseme = "REST" if amp < 0.08 else _CHAR_TO_VISEME.get(ch, "AA")
        frames.append({
            "frame": f_idx + 1,
            "time_sec": round(f_idx / fps, 3),
            "open": round(amp, 3),
            "viseme": viseme,
            "expression": expression,
        })
    return frames


def synthesize_dialogue_lines(
    project_id: str,
    dialogue_lines: list[dict[str, Any]],
    output_dir: Path,
    fps: int = 24,
    pause_between_sec: float = 0.25,
) -> dict[str, Any]:
    """Synthesize multi-speaker dialogue with per-character voice IDs and extract lip-sync timings."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cursor_sec = 0.0
    tracks: list[dict[str, Any]] = []
    all_lip_sync: list[dict[str, Any]] = []

    for idx, line in enumerate(dialogue_lines):
        speaker = str(line.get("speaker") or line.get("character") or f"Speaker_{idx + 1}")
        text = str(line.get("text") or line.get("line") or "").strip()
        if not text:
            continue
        expression = str(line.get("expression") or "neutral")
        voice_id = str(line.get("voice_id") or get_character_voice(project_id, speaker))
        wav_path = output_dir / f"dialogue_{idx + 1:02d}_{re.sub(r'[^a-zA-Z0-9_-]', '_', speaker)}.wav"
        tts_res = generate_tts(text=text, output_wav=wav_path, voice_id=voice_id)
        dur = float(tts_res.get("duration_sec") or probe_duration(wav_path) or 1.0)
        lip_frames = extract_phoneme_and_lip_sync_timings(wav_path, text, fps=fps, expression=expression)

        frame_offset = int(round(cursor_sec * fps))
        for lf in lip_frames:
            all_lip_sync.append({
                **lf,
                "frame": lf["frame"] + frame_offset,
                "time_sec": round(lf["time_sec"] + cursor_sec, 3),
                "speaker": speaker,
            })

        tracks.append({
            "speaker": speaker,
            "voice_id": voice_id,
            "provider": tts_res.get("provider"),
            "wav_path": str(wav_path),
            "start_sec": round(cursor_sec, 3),
            "end_sec": round(cursor_sec + dur, 3),
            "duration_sec": round(dur, 3),
            "expression": expression,
            "text": text,
        })
        cursor_sec += dur + pause_between_sec

    return {
        "ok": len(tracks) > 0,
        "total_duration_sec": round(max(0.0, cursor_sec - (pause_between_sec if tracks else 0.0)), 3),
        "tracks": tracks,
        "lip_sync_frames": all_lip_sync,
    }


def align_and_mix_scene_dialogue(
    dialogue_result: dict[str, Any],
    video_path: Path,
    output_mp4: Path,
    stems_dir: Path,
    music_wav: Path | None = None,
    sfx_cues: list[tuple[Path, float]] | None = None,
) -> dict[str, Any]:
    """Mix dialogue tracks into master stems and mux cleanly onto the rendered video."""
    tracks = dialogue_result.get("tracks") or []
    narration_wavs = [(Path(t["wav_path"]), float(t["start_sec"])) for t in tracks if Path(t["wav_path"]).is_file()]
    video_dur = probe_duration(video_path)
    total_dur = max(video_dur, float(dialogue_result.get("total_duration_sec") or 1.0))

    stems = mix_audio_stems(
        narration_wavs=narration_wavs,
        music_wav=music_wav,
        sfx_cues=sfx_cues or [],
        total_duration_sec=total_dur,
        stems_dir=stems_dir,
    )
    master_mix = Path(stems["master_mix"])
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(master_mix),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
            str(output_mp4),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or not output_mp4.is_file():
        return {"ok": False, "reason": proc.stderr[-300:]}
    return {"ok": True, "output": str(output_mp4), "stems": stems, "duration_sec": probe_duration(output_mp4)}
