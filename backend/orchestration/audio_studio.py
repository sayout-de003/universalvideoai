"""Complete Audio Production Studio: TTS, multi-speaker, music, SFX, subtitles, mixing, and stems."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def probe_duration(media_path: Path) -> float:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
            text=True, timeout=15,
        ).strip()
        return max(0.1, float(out))
    except Exception:
        return 0.0


def generate_tts(
    text: str,
    output_wav: Path,
    voice_id: str = "default",
    language: str = "en",
    rate_wpm: int = 165,
) -> dict[str, Any]:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    clean_text = text.strip() or "Silence."

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key and voice_id.startswith("openai:"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            voice = voice_id.split(":", 1)[1] or "onyx"
            mp3_tmp = output_wav.with_suffix(".mp3")
            with client.audio.speech.with_streaming_response.create(model="gpt-4o-mini-tts", voice=voice, input=clean_text) as resp:
                resp.stream_to_file(mp3_tmp)
            subprocess.run(["ffmpeg", "-y", "-i", str(mp3_tmp), "-ar", "44100", "-ac", "2", str(output_wav)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            mp3_tmp.unlink(missing_ok=True)
            return {"success": True, "path": str(output_wav), "duration_sec": probe_duration(output_wav), "provider": "openai_tts", "license": "generated_openai_tts"}
        except Exception:
            pass

    if voice_id.startswith("voicestudio:") or voice_id == "default":
        from backend.integrations.voicestudio_adapter import voicestudio_adapter
        vs_voice = voice_id.split(":", 1)[1] if voice_id.startswith("voicestudio:") else "alloy"
        vs_res = voicestudio_adapter.synthesize_speech(clean_text, output_wav, voice=vs_voice)
        if vs_res.get("success"):
            return {**vs_res, "duration_sec": probe_duration(output_wav)}

    if shutil.which("say") and shutil.which("ffmpeg"):
        aiff_tmp = output_wav.with_suffix(".aiff")
        voice_map = {"default": "Daniel", "narrator_deep": "Daniel", "narrator_warm": "Samantha", "character_1": "Alex", "character_2": "Karen", "hindi": "Lekha"}
        selected_voice = voice_map.get(voice_id, voice_id if voice_id != "default" else "Daniel")
        if language == "hi" and voice_id == "default":
            selected_voice = "Lekha"
        cmd = ["say", "-r", str(rate_wpm), "-o", str(aiff_tmp)]
        if selected_voice:
            cmd.extend(["-v", selected_voice])
        cmd.append(clean_text)
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode != 0 or not aiff_tmp.exists():
            subprocess.run(["say", "-r", str(rate_wpm), "-o", str(aiff_tmp), clean_text], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ffmpeg", "-y", "-i", str(aiff_tmp), "-ar", "44100", "-ac", "2", str(output_wav)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        aiff_tmp.unlink(missing_ok=True)
        return {"success": True, "path": str(output_wav), "duration_sec": probe_duration(output_wav), "provider": "macos_say", "license": "generated_local_system_tts"}

    words = max(1, len(clean_text.split()))
    dur = max(1.5, round(words / 2.6, 2))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc=0.12*sin(2*PI*180*t)*sin(2*PI*3.5*t):s=44100:d={dur}", "-ar", "44100", "-ac", "2", str(output_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"success": True, "path": str(output_wav), "duration_sec": probe_duration(output_wav), "provider": "ffmpeg_cadence_fallback", "license": "generated_procedural_cc0"}


def generate_music_bed(output_wav: Path, duration_sec: float, mood: str = "cinematic") -> dict[str, Any]:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    dur = max(1.0, float(duration_sec))
    mood_exprs = {
        "cinematic": "0.08*sin(2*PI*110*t)+0.06*sin(2*PI*164.81*t)+0.05*sin(2*PI*220*t)+0.03*sin(2*PI*329.63*t)*(0.5+0.5*sin(2*PI*0.25*t))",
        "upbeat": "0.07*sin(2*PI*261.63*t)+0.06*sin(2*PI*329.63*t)+0.05*sin(2*PI*392.00*t)*(0.6+0.4*sin(2*PI*2.0*t))",
        "comedy": "0.07*sin(2*PI*293.66*t)+0.06*sin(2*PI*369.99*t)+0.05*sin(2*PI*440.00*t)*(0.5+0.5*sin(2*PI*3.0*t))",
        "ambient": "0.06*sin(2*PI*130.81*t)+0.05*sin(2*PI*196.00*t)+0.04*sin(2*PI*246.94*t)",
    }
    expr = mood_exprs.get(mood, mood_exprs["cinematic"])
    fade_out_start = max(0.0, dur - 1.0)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc={expr}:s=44100:d={dur}",
            "-af", f"lowpass=f=650,aecho=0.8:0.7:40:0.25,afade=t=in:st=0:d=0.6,afade=t=out:st={fade_out_start:.2f}:d=0.9,volume=0.50",
            "-ar", "44100", "-ac", "2", str(output_wav),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"success": True, "path": str(output_wav), "duration_sec": probe_duration(output_wav), "provider": "ffmpeg_procedural_music", "license": "generated_procedural_cc0"}


def generate_sfx(output_wav: Path, sfx_type: str = "whoosh", duration_sec: float = 0.8) -> dict[str, Any]:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.2, float(duration_sec))
    if sfx_type == "impact":
        src = f"aevalsrc=0.45*sin(2*PI*65*t)*exp(-4*t):s=44100:d={dur}"
    elif sfx_type == "riser":
        src = f"aevalsrc=0.25*sin(2*PI*(120+400*t/{dur})*t):s=44100:d={dur}"
    elif sfx_type == "pop":
        src = f"aevalsrc=0.35*sin(2*PI*520*t)*exp(-14*t):s=44100:d={dur}"
    elif sfx_type == "ambience":
        src = f"anoisesrc=c=pink:r=44100:a=0.04:d={dur}"
    else:
        src = f"anoisesrc=c=pink:r=44100:a=0.18:d={dur}"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={max(0.05, dur-0.15):.2f}:d=0.15", "-ar", "44100", "-ac", "2", str(output_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"success": True, "path": str(output_wav), "duration_sec": probe_duration(output_wav), "provider": "ffmpeg_procedural_sfx", "license": "generated_procedural_cc0"}


def _fmt_srt_time(sec: float) -> str:
    ms = int(round(max(0.0, sec) * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, rem = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{rem:03d}"


def generate_subtitles(scenes_with_timings: list[dict[str, Any]], output_dir: Path, languages: list[str] | None = None, word_level: bool = True) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    langs = languages or ["en"]
    files: dict[str, dict[str, str]] = {}
    idx = 1
    for lang in langs:
        srt_lines: list[str] = []
        vtt_lines: list[str] = ["WEBVTT", ""]
        idx = 1
        for sc in scenes_with_timings:
            text = (sc.get("narration_segment") or sc.get("script_segment") or "").strip()
            if not text:
                continue
            if lang != "en":
                text = f"[{lang.upper()}] {text}"
            start = float(sc.get("start_sec", 0.0))
            dur = max(0.5, float(sc.get("duration_sec", 4.0)))
            words = text.split()
            if word_level and len(words) > 1:
                chunks = [" ".join(words[i:i + 4]) for i in range(0, len(words), 4)]
                step = dur / len(chunks)
                for ci, chunk in enumerate(chunks):
                    c_start = start + ci * step
                    c_end = min(start + dur, c_start + step - 0.02)
                    srt_lines.extend([str(idx), f"{_fmt_srt_time(c_start)} --> {_fmt_srt_time(c_end)}", chunk, ""])
                    vtt_lines.extend([f"{_fmt_srt_time(c_start).replace(',', '.')} --> {_fmt_srt_time(c_end).replace(',', '.')}", chunk, ""])
                    idx += 1
            else:
                end = start + dur - 0.05
                srt_lines.extend([str(idx), f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}", text, ""])
                vtt_lines.extend([f"{_fmt_srt_time(start).replace(',', '.')} --> {_fmt_srt_time(end).replace(',', '.')}", text, ""])
                idx += 1
        srt_path = output_dir / f"subtitles_{lang}.srt"
        vtt_path = output_dir / f"subtitles_{lang}.vtt"
        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
        vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")
        files[lang] = {"srt": str(srt_path), "vtt": str(vtt_path)}
    return {"languages": langs, "files": files, "cue_count": idx - 1}


def mix_audio_stems(
    narration_wavs: list[tuple[Path, float]],
    music_wav: Path | None,
    sfx_cues: list[tuple[Path, float]],
    total_duration_sec: float,
    stems_dir: Path,
    music_volume: float = 0.25,
) -> dict[str, str]:
    stems_dir.mkdir(parents=True, exist_ok=True)
    dur = max(1.0, float(total_duration_sec))

    narration_stem = stems_dir / "narration.wav"
    if narration_wavs:
        inputs, filter_parts, labels = [], [], []
        for idx, (wav, start_sec) in enumerate(narration_wavs):
            inputs.extend(["-i", str(wav)])
            delay_ms = max(0, int(round(start_sec * 1000)))
            lbl = f"[n{idx}]"
            filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},apad=whole_dur={dur:.3f}{lbl}")
            labels.append(lbl)
        filter_parts.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0,alimiter=limit=0.95[nout]")
        subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filter_parts), "-map", "[nout]", "-t", f"{dur:.3f}", str(narration_stem)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dur:.3f}", str(narration_stem)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    music_stem = stems_dir / "music.wav"
    if music_wav and music_wav.exists():
        subprocess.run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(music_wav), "-t", f"{dur:.3f}", "-af", f"volume={music_volume:.2f}", "-ar", "44100", "-ac", "2", str(music_stem)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dur:.3f}", str(music_stem)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    sfx_stem = stems_dir / "sfx.wav"
    if sfx_cues:
        inputs, filter_parts, labels = [], [], []
        for idx, (wav, start_sec) in enumerate(sfx_cues):
            inputs.extend(["-i", str(wav)])
            delay_ms = max(0, int(round(start_sec * 1000)))
            lbl = f"[s{idx}]"
            filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},apad=whole_dur={dur:.3f}{lbl}")
            labels.append(lbl)
        filter_parts.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0,volume=0.65[sout]")
        subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filter_parts), "-map", "[sout]", "-t", f"{dur:.3f}", str(sfx_stem)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dur:.3f}", str(sfx_stem)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    master_mix = stems_dir / "master_mix.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(narration_stem), "-i", str(music_stem), "-i", str(sfx_stem),
            "-filter_complex", "[1:a][0:a]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=250[mduck];[0:a][mduck][2:a]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.95[mix]",
            "-map", "[mix]", "-t", f"{dur:.3f}", str(master_mix),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"narration": str(narration_stem), "music": str(music_stem), "sfx": str(sfx_stem), "master_mix": str(master_mix)}
