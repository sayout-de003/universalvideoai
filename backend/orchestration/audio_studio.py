"""Complete Audio Production Studio: Neural Human Male/Female TTS, multi-speaker, music, SFX, subtitles, mixing, and stems."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
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


_EDGE_NEURAL_VOICES: dict[str, str] = {
    "default": "en-US-ChristopherNeural",
    "narrator_deep": "en-US-ChristopherNeural",
    "male": "en-US-ChristopherNeural",
    "male_narrator": "en-US-ChristopherNeural",
    "character_1": "en-US-ChristopherNeural",
    "boss": "en-US-ChristopherNeural",
    "male_lead": "en-US-GuyNeural",
    "character_2": "en-US-GuyNeural",
    "employee": "en-US-GuyNeural",
    "character_3": "en-GB-RyanNeural",
    "friend": "en-GB-RyanNeural",
    "male_british": "en-GB-RyanNeural",
    "narrator_warm": "en-US-AriaNeural",
    "female": "en-US-AriaNeural",
    "female_narrator": "en-US-AriaNeural",
    "character_4": "en-US-JennyNeural",
    "female_lead": "en-US-JennyNeural",
    "male_executive": "en-US-ChristopherNeural",
    "female_british": "en-GB-SoniaNeural",
    "sarah": "en-US-AriaNeural",
    "maya": "en-US-JennyNeural",
    "elena": "en-US-AriaNeural",
    "emily": "en-US-AriaNeural",
    "anna": "en-US-JennyNeural",
    "emma": "en-US-JennyNeural",
    "clara": "en-GB-SoniaNeural",
    "mark": "en-US-ChristopherNeural",
    "alex": "en-US-GuyNeural",
    "david": "en-US-ChristopherNeural",
    "john": "en-US-ChristopherNeural",
    "liam": "en-GB-RyanNeural",
    "sam": "en-GB-RyanNeural",
    "hindi": "hi-IN-MadhurNeural",
    "hindi_male": "hi-IN-MadhurNeural",
    "hindi_female": "hi-IN-SwaraNeural",
}

_FEMALE_NAME_KEYWORDS = (
    "sarah", "maya", "aria", "jenny", "sonia", "swara", "emily", "anna", "emma",
    "olivia", "sophia", "jessica", "rachel", "maria", "elena", "lisa", "clara",
    "female", "woman", "girl", "mother", "sister", "actress", "cto sarah", "co-founder sarah"
)

_MALE_NAME_KEYWORDS = (
    "mark", "alex", "guy", "male", "man", "chris", "christopher", "david", "john",
    "liam", "sam", "ryan", "michael", "james", "robert", "boss", "employee", "friend",
    "boy", "father", "brother", "actor", "lead engineer mark", "engineer mark"
)


def resolve_neural_voice(voice_id: str = "default", language: str = "en") -> tuple[str, str]:
    """Return (edge_neural_voice_name, gender) for the requested voice_id and language."""
    vid = (voice_id or "default").strip()
    low_vid = vid.lower()
    if vid.startswith("edge:"):
        custom = vid.split(":", 1)[1].strip()
        gender = "female" if any(f in custom.lower() for f in ("aria", "jenny", "sonia", "swara", "natasha", "clara")) else "male"
        return custom, gender
    if language == "hi":
        if vid in ("narrator_warm", "female", "female_narrator", "character_4", "female_lead", "hindi_female") or any(f in low_vid for f in _FEMALE_NAME_KEYWORDS):
            return "hi-IN-SwaraNeural", "female"
        return "hi-IN-MadhurNeural", "male"

    if low_vid in _EDGE_NEURAL_VOICES:
        edge_voice = _EDGE_NEURAL_VOICES[low_vid]
        gender = "female" if (
            low_vid in ("narrator_warm", "female", "female_narrator", "character_4", "female_lead", "female_british")
            or any(f in low_vid for f in _FEMALE_NAME_KEYWORDS)
            or any(f in edge_voice.lower() for f in ("aria", "jenny", "sonia", "swara"))
        ) else "male"
        return edge_voice, gender

    # Contextual name / gender inference if not in explicit table
    if any(f in low_vid for f in _FEMALE_NAME_KEYWORDS):
        return "en-US-AriaNeural", "female"
    if any(m in low_vid for m in _MALE_NAME_KEYWORDS):
        return "en-US-ChristopherNeural", "male"

    edge_voice = _EDGE_NEURAL_VOICES.get(vid, "en-US-ChristopherNeural")
    gender = "female" if vid in ("narrator_warm", "female", "female_narrator", "character_4", "female_lead", "female_british") else "male"
    return edge_voice, gender


def sanitize_spoken_voiceover(raw_text: str, default: str = "Silence.") -> str:
    """Sanitize raw text for TTS voice-over so that markdown formatting, scene headers,
    visual descriptions, camera cues, and technical metadata are NEVER read aloud.
    Only pure human dialogue and narration are spoken."""
    text = (raw_text or "").strip()
    if not text:
        return default

    # If text is solely a header / screenplay banner / scene label with no spoken dialogue, never speak it
    if re.fullmatch(r"^(?:#+\s*)*(?:SCREENPLAY|SCENE\s*\d*|ACT\s*\d*|EPISODE\s*\d*|CHAPTER\s*\d*|PART\s*\d*)[^:\n.!?]*(?::\s*[^:\n.!?]{0,40})?$", text, flags=re.IGNORECASE):
        if not re.search(r"\b(?:NARRATION|VO|SPOKEN|DIALOGUE|NARRATOR)\b", text, flags=re.IGNORECASE):
            return default

    # Normalize screenplay text so each field starts on its own line
    normalized = re.sub(r"\s*(##+\s*SCENE\s+\d+)", r"\n\1", text, flags=re.IGNORECASE)
    normalized = re.sub(
        r"\s*((?:\*\*)?(?:VISUAL|CAMERA|LIGHTING|NARRATION\s*/?\s*VO|NARRATION|VO|ON-SCREEN\s+TEXT|SOUND|AUDIO|DIALOGUE|SPEECH|NARRATOR)(?:\s*\([^)]*\))?(?:\*\*)?\s*:)",
        r"\n\1",
        normalized,
        flags=re.IGNORECASE,
    )

    # 1. If explicit NARRATION/VO/DIALOGUE/NARRATOR tags exist, isolate only their spoken contents
    vo_matches = re.findall(
        r"(?:^|\n)\s*(?:\*\*)?(?:NARRATION\s*/?\s*VO|NARRATION|VO|DIALOGUE|SPOKEN|SPEECH|NARRATOR)(?:\s*\([^)]*\))?(?:\*\*)?\s*:\s*(.*?)(?=\n(?:\*\*)?[A-Za-z0-9_\s/-]{2,30}(?:\*\*)?\s*:|\n##|\Z)",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if vo_matches:
        text = " ".join(m.strip() for m in vo_matches if m.strip())
    else:
        # 2. Filter out screenplay metadata lines, scene titles, and visual directions
        lines = []
        for line in normalized.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            # Header lines (# SCREENPLAY..., ## SCENE...)
            if re.match(r"^#+\s*", line_s):
                continue
            # Format/Runtime headers
            if re.match(r"^\*?\s*Format\s*:.*?Runtime\s*:", line_s, flags=re.IGNORECASE):
                continue
            if re.match(r"^(?:#+\s*)*(?:SCREENPLAY|SCENE\s+\d+|ACT\s+\d+)\b", line_s, flags=re.IGNORECASE):
                remainder = re.sub(r"^(?:#+\s*)*(?:SCREENPLAY|SCENE\s+\d+|ACT\s+\d+)[^:\-]*[:\-]\s*", "", line_s, flags=re.IGNORECASE).strip()
                if not remainder or (not re.search(r"[.!?“”\"]", remainder) and len(remainder.split()) < 5):
                    continue
                line_s = remainder
            # Screenplay field blocks
            if re.match(r"^(?:\*\*)?(?:VISUAL|CAMERA|LIGHTING|SOUND|ON-SCREEN\s+TEXT|COMPOSITION|PROPS?|LOCATION|TRANSITION|EFFECTS?|MUSIC|SFX)(?:\*\*)?\s*:", line_s, flags=re.IGNORECASE):
                continue
            # Sluglines, transitions, and stage directions
            if re.match(r"^(?:EXT\.|INT\.|EST\.|FADE\s+IN|CUT\s+TO|DISSOLVE\s+TO)\b", line_s, flags=re.IGNORECASE):
                continue
            if re.match(r"^\(.*\)$", line_s):
                continue
            if re.match(r"^(?:we see|show the|cut to|camera |the camera|fade in|wide shot|close-up|close up|pan to|dolly)\b", line_s, flags=re.IGNORECASE):
                continue
            lines.append(line_s)
        text = " ".join(lines) if lines else ""

    if not text.strip():
        return default

    # 3. Strip screenplay guide/prompt-instruction wrappers and beat prefixes first
    text = re.sub(
        r"^(?:(?:please\s+)?(?:create|make|generate|write|produce|build|render)\s+(?:a|an)\s+(?:\d+\s*(?:sec|second|seconds|min|minute|minutes|s)\s+)?(?:[\w-]+\s+){0,4}?(?:video|animation|film|clip|short|reel|script|screenplay)\s+(?:of|about|on|for|showing|featuring)?\s*)+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:\b\d+\s*-?\s*(?:sec|second|seconds|min|minute|minutes|s)\s+)?\b(?:(?:screenplay|production|prompt|video|animation)\s+(?:guide|guidelines|instructions?|spec|specification|structure|template)|scene\s+breakdown)\b\s*[:.\-]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^(?:At\s+beat\s+\d+|In\s+(?:scene|step|phase|stage|chapter)\s+\d+|Scene\s+\d+[:\-]?).*?[:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:At\s+beat\s+\d+|In\s+(?:scene|step|phase|stage|chapter)\s+\d+)\s*[,:\-]?\s*", "", text, flags=re.IGNORECASE)

    # 4. Strip semantic moment tags @{...} and ALL bracketed/parenthetical stage directions
    text = re.sub(r"@\{[^}]+\}", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"\([^)]*\)", "", text)

    # 4b. Strip character speaker prefixes like 'NARRATOR: ' or 'Alex: ' or 'NAPOLEON: '
    text = re.sub(r"^(?:[A-Za-z][A-Za-z0-9_\s]{1,32}\s*:\s*)+", "", text.strip())
    # Strip any residual leading character name or perspective label with colon or spaced dash after guide removal
    text = re.sub(r"(?i)^(?:\s*(?:[A-Za-z0-9_]{1,24})\s*(?::\s*|\s+[-–—]\s+))+", "", text)
    # Also strip embedded speaker labels e.g. "Maya: I agree." if pasted into one block
    text = re.sub(r"(?i)(?<=\.)\s*(?:[A-Za-z0-9_\s]{1,24})\s*:\s*", " ", text)
    text = re.sub(r"(?i)^(?:for|about|on|of|with|in)\s+", "", text)

    # 5. Strip markdown tokens (#, *, _, `, ~, |, >)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"^[#*\s>~`\-]+", "", text)
    text = re.sub(r"[#*`~|]", "", text)

    # 6. Clean up surrounding quotes and multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("\"'“”‘’")
    return text if text else default


def contains_screenplay_meta(text: str) -> bool:
    """Return True if spoken text still contains screenplay guide/instruction meta-text."""
    low = (text or "").lower()
    return bool(re.search(
        r"\b(?:(?:screenplay|production|prompt|video|animation)\s+(?:guide|guidelines|instructions?|spec|specification|structure|template)|scene\s+breakdown|\d+\s*sec\s+screenplay)\b",
        low,
    ))


def generate_tts(
    text: str,
    output_wav: Path,
    voice_id: str = "default",
    language: str = "en",
    rate_wpm: int = 165,
    production_mode: str | None = None,
) -> dict[str, Any]:
    from backend.orchestration.engine_registry import is_free_open_source_mode

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    clean_text = sanitize_spoken_voiceover(text)
    free_mode = is_free_open_source_mode(production_mode)

    if not clean_text or clean_text.lower() in ("silence.", "silence"):
        return {
            "success": False,
            "status": "FAILED",
            "path": str(output_wav),
            "duration_sec": 0.0,
            "provider": "silence",
            "voice_used": "none",
            "reason": "Silent or empty dialogue text; refusing to treat silence as spoken dialogue.",
        }

    # Hugging Face Open-Source Voice Models (Zonos-v0.3-Mini, OmniVoice, Fish Audio Drama 3)
    if voice_id.startswith(("zonos", "omnivoice", "drama", "fish", "hf:")) or any(k in voice_id.lower() for k in ("zonos", "omnivoice", "drama", "fishaudio")):
        from backend.services.huggingface_voice_service import generate_speech_with_huggingface_voice
        if "drama" in voice_id.lower() or "fish" in voice_id.lower():
            model_name = "fishaudio/drama-3"
        elif "zonos" in voice_id.lower():
            model_name = "Zyphra/ZONOS3-Mini"
        else:
            model_name = "k2-fsa/OmniVoice"
        hf_voice_res = generate_speech_with_huggingface_voice(
            model_key_or_repo=model_name,
            text=clean_text,
            output_wav=output_wav,
            voice_id=voice_id,
            language=language,
        )
        if hf_voice_res.get("success"):
            return hf_voice_res

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not free_mode and openai_key and voice_id.startswith("openai:"):
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

    from backend.integrations.voicestudio_adapter import voicestudio_adapter
    _vs_names = {
        "default": "onyx",
        "narrator_deep": "onyx",
        "narrator_warm": "nova",
        "character_1": "echo",
        "character_2": "shimmer",
        "hindi": "alloy",
    }
    vs_voice = voice_id.split(":", 1)[1] if voice_id.startswith("voicestudio:") else _vs_names.get(voice_id, "onyx")
    vs_res = voicestudio_adapter.synthesize_speech(clean_text, output_wav, voice=vs_voice)
    if vs_res.get("success"):
        return {**vs_res, "duration_sec": probe_duration(output_wav)}

    # Primary Human Neural TTS (Microsoft Edge Neural Voices — Male & Female)
    if shutil.which("ffmpeg") and not os.environ.get("DISABLE_EDGE_TTS"):
        edge_voice, gender = resolve_neural_voice(voice_id, language)
        mp3_tmp = output_wav.with_suffix(".edge.mp3")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "edge_tts", "--voice", edge_voice, "--text", clean_text, "--write-media", str(mp3_tmp)],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if proc.returncode == 0 and mp3_tmp.is_file() and mp3_tmp.stat().st_size > 512:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(mp3_tmp), "-ar", "44100", "-ac", "2", str(output_wav)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                mp3_tmp.unlink(missing_ok=True)
                return {
                    "success": True,
                    "path": str(output_wav),
                    "duration_sec": probe_duration(output_wav),
                    "provider": "edge_neural_tts",
                    "voice_used": edge_voice,
                    "voice_gender": gender,
                    "quality_tier": "neural_human_tts",
                    "license": "generated_neural_tts",
                }
        except Exception:
            pass
        finally:
            mp3_tmp.unlink(missing_ok=True)

    if shutil.which("say") and shutil.which("ffmpeg"):
        aiff_tmp = output_wav.with_suffix(".aiff")
        voice_map = {
            "default": "Daniel",
            "narrator_deep": "Daniel",
            "male": "Daniel",
            "male_narrator": "Daniel",
            "character_1": "Daniel",
            "boss": "Daniel",
            "male_lead": "Alex",
            "character_2": "Alex",
            "employee": "Alex",
            "character_3": "Fred",
            "friend": "Fred",
            "narrator_warm": "Samantha",
            "female": "Samantha",
            "female_narrator": "Samantha",
            "character_4": "Karen",
            "female_lead": "Karen",
            "hindi": "Lekha",
        }
        selected_voice = voice_map.get(voice_id, voice_id if voice_id != "default" else "Daniel")
        if language == "hi" and voice_id == "default":
            selected_voice = "Lekha"
        cmd = ["say", "-r", str(rate_wpm), "-o", str(aiff_tmp)]
        if selected_voice:
            cmd.extend(["-v", selected_voice])
        cmd.append(clean_text)
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode != 0 or not aiff_tmp.exists():
            selected_voice = "Daniel"
            subprocess.run(["say", "-r", str(rate_wpm), "-o", str(aiff_tmp), clean_text], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ffmpeg", "-y", "-i", str(aiff_tmp), "-ar", "44100", "-ac", "2", str(output_wav)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        aiff_tmp.unlink(missing_ok=True)
        return {
            "success": True,
            "path": str(output_wav),
            "duration_sec": probe_duration(output_wav),
            "provider": "macos_say",
            "voice_used": selected_voice,
            "quality_tier": "local_os_tts",
            "license": "generated_local_system_tts",
        }

    # Linux espeak-ng / espeak fallback
    espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
    if espeak_bin and shutil.which("ffmpeg"):
        try:
            raw_tmp = output_wav.with_suffix(".espeak.wav")
            subprocess.run([espeak_bin, "-s", str(rate_wpm), "-w", str(raw_tmp), clean_text], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if raw_tmp.exists() and raw_tmp.stat().st_size > 256:
                subprocess.run(["ffmpeg", "-y", "-i", str(raw_tmp), "-ar", "44100", "-ac", "2", str(output_wav)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                raw_tmp.unlink(missing_ok=True)
                return {"success": True, "path": str(output_wav), "duration_sec": probe_duration(output_wav), "provider": "linux_espeak", "license": "generated_local_system_tts"}
        except Exception:
            pass

    words = max(1, len(clean_text.split()))
    dur = max(1.5, round(words / 2.6, 2))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dur}", str(output_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"success": False, "status": "UNAVAILABLE", "path": str(output_wav), "duration_sec": dur, "provider": "none", "reason": "No TTS engine available."}


def _fetch_openverse_music(output_wav: Path, mood: str, duration_sec: float) -> dict[str, Any] | None:
    """Fetch a real CC-licensed instrumental audio track from Openverse (zero-key)."""
    mood_queries = {
        "cinematic": "cinematic orchestral instrumental",
        "upbeat": "upbeat electronic corporate instrumental",
        "comedy": "playful acoustic instrumental",
        "ambient": "ambient documentary atmospheric",
    }
    q = mood_queries.get(mood, "cinematic instrumental")
    try:
        import httpx
        with httpx.Client(timeout=15.0, headers={"User-Agent": "UniversalAIVideoStudio/1.0"}, follow_redirects=True) as client:
            resp = client.get(
                "https://api.openverse.org/v1/audio/",
                params={"q": q, "license_type": "commercial,modification", "page_size": 8},
            )
            if resp.status_code != 200:
                return None
            for item in resp.json().get("results", []):
                url = item.get("url")
                if not url:
                    continue
                dl = client.get(url)
                if dl.status_code != 200 or len(dl.content) < 25_000:
                    continue
                tmp_raw = output_wav.with_suffix(".raw_music")
                tmp_raw.write_bytes(dl.content)
                fade_out = max(0.0, duration_sec - 1.2)
                proc = subprocess.run(
                    [
                        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(tmp_raw),
                        "-t", f"{duration_sec:.3f}",
                        "-af", f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out:.2f}:d=1.2,loudnorm=I=-24:TP=-2.0",
                        "-ar", "44100", "-ac", "2", str(output_wav),
                    ],
                    capture_output=True, text=True, timeout=60,
                )
                tmp_raw.unlink(missing_ok=True)
                if proc.returncode == 0 and output_wav.is_file() and probe_duration(output_wav) > 0.5:
                    return {
                        "success": True,
                        "path": str(output_wav),
                        "duration_sec": probe_duration(output_wav),
                        "provider": "openverse_cc_music",
                        "title": item.get("title") or q,
                        "license": f"{item.get('license', 'CC')} {item.get('license_version', '')}".strip(),
                        "attribution": item.get("creator") or "Openverse Audio",
                        "degraded": False,
                    }
    except Exception:
        return None
    return None


def generate_music_bed(output_wav: Path, duration_sec: float, mood: str = "cinematic") -> dict[str, Any]:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    dur = max(1.0, float(duration_sec))

    ov = _fetch_openverse_music(output_wav, mood, min(dur, 180.0))
    if ov:
        return ov

    pad_dur = min(dur, 32.0)
    fade_out_start = max(0.0, pad_dur - 1.2)
    chord = "0.07*sin(2*PI*110*t)+0.05*sin(2*PI*164.81*t)+0.04*sin(2*PI*220*t)+0.02*sin(2*PI*329.63*t)"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc={chord}:s=44100:d={pad_dur}",
            "-af", f"lowpass=f=900,aecho=0.8:0.75:40:0.18,afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.2f}:d=1.1",
            "-ar", "44100", "-ac", "2", str(output_wav),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {
        "success": True,
        "path": str(output_wav),
        "duration_sec": probe_duration(output_wav),
        "provider": "scored_pad_fallback",
        "license": "generated_procedural_cc0",
        "degraded": True,
    }


def generate_sfx(output_wav: Path, sfx_type: str = "subtle_chime", duration_sec: float = 0.5) -> dict[str, Any]:
    """Generate clean, non-noisy harmonic SFX cues (never pink/white noise whooshes)."""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.2, float(duration_sec))
    from backend.integrations.voicestudio_adapter import voicestudio_adapter
    vs_sfx = voicestudio_adapter.generate_sfx(sfx_type, output_wav, duration_sec=dur)
    if vs_sfx.get("success"):
        return {**vs_sfx, "duration_sec": probe_duration(output_wav)}

    if sfx_type == "impact":
        src = f"aevalsrc=0.22*sin(2*PI*65*t)*exp(-5*t):s=44100:d={dur}"
        tone = "lowpass=f=180"
    elif sfx_type == "riser":
        src = f"aevalsrc=0.12*sin(2*PI*(140+220*t/{dur})*t)*exp(-2*t):s=44100:d={dur}"
        tone = "lowpass=f=1200"
    elif sfx_type == "coffee_spit":
        # Percussive burst + splash envelope for comedic coffee spit
        src = f"anoisesrc=c=pink:r=44100:d={dur}:a=0.45"
        tone = "bandpass=f=1400:w=900,afade=t=in:st=0:d=0.02,afade=t=out:st=0.08:d=0.35"
    elif sfx_type == "comedic_sting":
        # Bright two-note comedic punchline sting
        src = f"aevalsrc=0.20*sin(2*PI*523.25*t)*exp(-4*t)+0.18*sin(2*PI*659.25*t)*exp(-3.5*t)+0.15*sin(2*PI*783.99*t)*exp(-3*t):s=44100:d={dur}"
        tone = "lowpass=f=2400"
    elif sfx_type == "office_ambience":
        # Subtle warm office room-tone bed
        src = f"anoisesrc=c=brown:r=44100:d={dur}:a=0.025"
        tone = "lowpass=f=450"
    else:
        # Soft harmonic chime / warm low pulse — zero pink/white noise hiss
        src = f"aevalsrc=0.06*sin(2*PI*220*t)*exp(-6*t)+0.04*sin(2*PI*329.63*t)*exp(-8*t):s=44100:d={dur}"
        tone = "lowpass=f=900"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-af", f"{tone},afade=t=in:st=0:d=0.04,afade=t=out:st={max(0.04, dur-0.15):.2f}:d=0.15", "-ar", "44100", "-ac", "2", str(output_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"success": True, "path": str(output_wav), "duration_sec": probe_duration(output_wav), "provider": "ffmpeg_harmonic_sfx", "license": "generated_procedural_cc0"}


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
            raw_t = (sc.get("narration_segment") or sc.get("script_segment") or "").strip()
            text = sanitize_spoken_voiceover(raw_t, default="")
            if not text or text.lower() == "silence.":
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
    music_volume: float = 0.22,
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
        filter_parts.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0,volume=0.25[sout]")
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


def _char_to_viseme(ch: str) -> str:
    c = ch.lower()
    if c in ("a", "ä", "á"):
        return "viseme_AA"
    if c in ("e", "i", "y"):
        return "viseme_EE"
    if c in ("o", "u", "w", "q"):
        return "viseme_OO"
    if c in ("f", "v"):
        return "viseme_FF"
    if c in ("m", "b", "p"):
        return "viseme_MBP"
    return "jaw_open"


def generate_viseme_timeline(
    wav_path: Path,
    text: str,
    speaker: str,
    offset_sec: float = 0.0,
    fps: int = 30,
) -> list[dict[str, Any]]:
    """Build audio-synchronized phoneme/viseme keyframes from a spoken WAV's RMS envelope."""
    import math
    import struct
    import wave

    if not wav_path.is_file():
        return []
    letters = [ch for ch in (text or "") if ch.isalpha()] or ["a"]
    frames_out: list[dict[str, Any]] = []
    try:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
    except Exception:
        return []

    if sampwidth != 2 or framerate <= 0 or n_frames <= 0:
        return []

    total_samples = len(raw) // 2
    samples = struct.unpack(f"<{total_samples}h", raw)
    if n_channels > 1:
        samples = samples[::n_channels]

    samples_per_video_frame = max(1, int(framerate / max(1, fps)))
    total_vframes = max(1, len(samples) // samples_per_video_frame)

    for vf_idx in range(total_vframes):
        chunk = samples[vf_idx * samples_per_video_frame:(vf_idx + 1) * samples_per_video_frame]
        if not chunk:
            continue
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
        open_val = min(1.0, max(0.0, (rms - 0.012) * 8.5))
        t_local = vf_idx / float(fps)
        t_abs = offset_sec + t_local
        char_idx = min(len(letters) - 1, int((vf_idx / max(1, total_vframes)) * len(letters)))
        viseme = _char_to_viseme(letters[char_idx]) if open_val > 0.08 else "viseme_MBP"
        frames_out.append({
            "frame": max(1, int(round(t_abs * fps)) + 1),
            "time_sec": round(t_abs, 3),
            "speaker": speaker,
            "viseme": viseme,
            "open": round(open_val, 3),
        })
    # Ensure mouth closes cleanly at the end of the turn
    if frames_out:
        last_fr = frames_out[-1]["frame"] + 1
        frames_out.append({
            "frame": last_fr,
            "time_sec": round(offset_sec + total_vframes / float(fps), 3),
            "speaker": speaker,
            "viseme": "viseme_MBP",
            "open": 0.0,
        })
    return frames_out
