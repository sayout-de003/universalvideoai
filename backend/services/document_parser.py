"""Universal File Reader & Structured Screenplay Parser.

Supports reading any file type (.md, .txt, .pdf, .docx, .doc, .rtf, .html, .json, .csv, .srt, .vtt, .fountain, images, audio, video)
and parsing structured screenplay markdown/text into clean title, subject, character bible, and scene specs.
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any


_NOT_SPEAKERS = {
    "visual", "visuals", "camera", "lighting", "narration", "vo", "dialogue",
    "speech", "spoken", "narrator", "audio", "sound", "sfx", "text", "action",
    "description", "desc", "format", "runtime", "voice", "title", "screenplay",
    "scene", "transition", "music", "props", "prop", "location", "int", "ext",
    "est", "on-screen text", "on screen text", "guide", "style", "setting",
    "characters", "character", "cast", "plot", "theme", "tone", "pacing",
    "duration", "notes", "instructions", "instruction", "outline", "breakdown",
    "beat", "beats", "prompt", "screenplay guide", "production guide",
}


def _parse_time_range(text: str) -> tuple[float | None, float | None, float | None]:
    """Parse time ranges like '0–8 seconds', '0-8s', '8 to 15 sec' into (start, end, duration)."""
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:–|—|-|to)\s*(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b",
        text or "",
        flags=re.IGNORECASE,
    )
    if m:
        start = float(m.group(1))
        end = float(m.group(2))
        if end > start:
            return start, end, round(end - start, 2)
    dur_m = re.search(r"\((\d+(?:\.\d+)?)\s*s\)", text or "", flags=re.IGNORECASE)
    if dur_m:
        return None, None, float(dur_m.group(1))
    return None, None, None


def _normalize_speaker_name(raw: str) -> str:
    s = re.sub(r"^(?:the|a|an)\s+", "", (raw or "").strip(), flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip(" :,-.")
    if not s:
        return ""
    low = s.lower()
    if low in ("boss", "manager", "supervisor"):
        return "Boss"
    if low in ("employee", "worker", "coworker", "colleague"):
        return "Employee"
    if low in ("friend", "buddy", "pal"):
        return "Friend"
    return s.title() if s.islower() or s.isupper() else s


def _extract_quoted_dialogue_turns(body: str) -> list[dict[str, Any]]:
    """Extract every quoted dialogue line in a scene with explicit speaker attribution."""
    turns: list[dict[str, Any]] = []
    text = body or ""
    speech_verbs = (
        r"(?:says|asks|replies|answers|whispers|shouts|yells|mutters|smirks|laughs|"
        r"scoffs|groans|sighs|responds|adds|continues|exclaims|jokes|chimes\s+in)"
    )
    for idx, m in enumerate(re.finditer(r'["“]([^"”]{2,})["”]', text)):
        line = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(line) < 2:
            continue
        # Look backward up to 90 chars (on same sentence/line) for speaker attribution
        pre = text[max(0, m.start() - 90):m.start()]
        pre_line = pre.splitlines()[-1] if pre.splitlines() else pre
        speaker = ""
        # Pattern 1: "Boss:" or "**Boss**:"
        m_colon = re.search(r"(?:\*\*)?([A-Za-z][A-Za-z0-9 .'\-]{1,24}?)(?:\*\*)?\s*:\s*$", pre_line)
        if m_colon:
            cand = _normalize_speaker_name(m_colon.group(1))
            if cand.lower() not in _NOT_SPEAKERS:
                speaker = cand
        # Pattern 2: "The Boss says," / "Friend smirks and says," / "Employee asks:"
        if not speaker:
            m_verb = re.search(
                rf"(?:^|[.!?]\s+|\n|\b)(?:the\s+)?([A-Za-z][A-Za-z0-9 '\-]{{1,22}}?)\s+(?:[a-z]+\s+and\s+)?{speech_verbs}\b[^\"“\n]{{0,24}}$",
                pre_line,
                flags=re.IGNORECASE,
            )
            if m_verb:
                cand = _normalize_speaker_name(m_verb.group(1))
                if cand.lower() not in _NOT_SPEAKERS:
                    speaker = cand
        # Pattern 3: explicit role keyword anywhere near the end of pre_line
        if not speaker:
            m_role = list(re.finditer(r"\b(boss|employee|friend)\b", pre_line, flags=re.IGNORECASE))
            if m_role:
                speaker = _normalize_speaker_name(m_role[-1].group(1))
        # Pattern 4: trailing attribution '"...", says the Boss'
        if not speaker:
            post = text[m.end():min(len(text), m.end() + 60)]
            m_post = re.search(
                rf"^\s*,?\s*(?:{speech_verbs}\s+)?(?:the\s+)?([A-Za-z][A-Za-z0-9 '\-]{{1,22}}?)(?:\s+{speech_verbs})?(?:[.!?\n]|$)",
                post,
                flags=re.IGNORECASE,
            )
            if m_post:
                cand = _normalize_speaker_name(m_post.group(1))
                if cand.lower() not in _NOT_SPEAKERS:
                    speaker = cand

        turns.append({
            "speaker": speaker or "Narrator",
            "line": line,
            "order": idx,
        })
    return turns


def _extract_character_and_scene_bible(text: str) -> dict[str, Any]:
    """Extract character descriptions, wardrobe, props, setting, and animation style."""
    low = (text or "").lower()
    is_purple = "purple" in low
    characters: list[dict[str, Any]] = []

    if re.search(r"\bboss\b", low):
        wardrobe = ["black tie"] if "black tie" in low else ["office shirt and tie"]
        characters.append({
            "name": "Boss",
            "role": "boss",
            "color": "purple" if is_purple else "stylized",
            "wardrobe": wardrobe,
            "props": [],
            "expression": "serious" if "serious" in low else "stern",
            "gestures": ["nervous_gesture"] if "nervous" in low else ["talk"],
        })
    if re.search(r"\bemployee\b", low):
        wardrobe = ["blue ID card"] if "id card" in low or "blue id" in low else ["office lanyard"]
        props = ["coffee cup"] if "coffee" in low else []
        characters.append({
            "name": "Employee",
            "role": "employee",
            "color": "purple" if is_purple else "stylized",
            "wardrobe": wardrobe,
            "props": props,
            "expression": "shocked" if "shocked" in low or "spit" in low else "expressive",
            "gestures": ["coffee_spit"] if "spit" in low else ["talk"],
        })
    if re.search(r"\bfriend\b", low):
        wardrobe = ["headphones"] if "headphone" in low else ["casual jacket"]
        characters.append({
            "name": "Friend",
            "role": "friend",
            "color": "purple" if is_purple else "stylized",
            "wardrobe": wardrobe,
            "props": ["headphones"] if "headphone" in low else [],
            "expression": "sarcastic" if "sarcastic" in low or "smirk" in low else "relaxed",
            "gestures": ["raise_hand"] if "raise" in low or "hand" in low else ["talk"],
        })

    setting = "office break room" if ("break room" in low or "break-room" in low or "office" in low) else "studio"
    env_props = [p for p in ("table", "chairs", "coffee cup", "coffee cups") if p in low]
    anim_style = "3d_stylized" if any(k in low for k in ("3d", "pixar", "blender", "cgi")) else "auto"

    return {
        "character_bible": characters,
        "environment_bible": {
            "setting": setting,
            "props": env_props,
        },
        "animation_style": anim_style,
    }


def extract_dialogue_turns(text: str) -> list[dict[str, str]]:
    """Pull spoken lines only. Stage directions, camera notes, and field labels are not turns."""
    turns: list[dict[str, str]] = []
    for match in re.finditer(
        r"(?m)^[ \t]*(?:\*\*)?([A-Za-z][A-Za-z0-9 .'\-]{0,22}?)(?:\*\*)?\s*:\s*(.+)$",
        text or "",
    ):
        name = match.group(1).strip()
        line = match.group(2).strip().strip('"').strip()
        key = re.sub(r"\s+", " ", name.lower().rstrip("."))
        if key in _NOT_SPEAKERS or "narration" in key or key.startswith(("scene", "on-screen", "on screen")):
            continue
        if len(line) < 2:
            continue
        turns.append({"speaker": name, "line": clean_markdown_inline(line)})
    if len({turn["speaker"].lower() for turn in turns}) >= 2:
        return turns

    fountain: list[dict[str, str]] = []
    lines = (text or "").splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index].strip()
        name = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
        if (
            name
            and name == name.upper()
            and re.fullmatch(r"[A-Z][A-Z0-9 .'\-]{1,22}", name)
            and name.lower() not in _NOT_SPEAKERS
            and not name.startswith(("INT.", "EXT.", "EST.", "FADE", "CUT"))
        ):
            index += 1
            if index < len(lines) and lines[index].strip().startswith("("):
                index += 1
            spoken: list[str] = []
            while index < len(lines) and lines[index].strip():
                nxt = lines[index].strip()
                cue = re.sub(r"\s*\([^)]*\)\s*$", "", nxt).strip()
                if cue == cue.upper() and re.fullmatch(r"[A-Z][A-Z0-9 .'\-]{1,22}", cue or "x"):
                    break
                if nxt.startswith(("INT.", "EXT.", "EST.", "##", "**")):
                    break
                spoken.append(nxt)
                index += 1
            line = clean_markdown_inline(" ".join(spoken))
            if line:
                fountain.append({"speaker": name.title(), "line": line})
            continue
        index += 1
    if len({turn["speaker"].lower() for turn in fountain}) >= 2:
        return fountain
    return []


def _scenes_from_dialogue_turns(turns: list[dict[str, str]]) -> list[dict[str, Any]]:
    speakers = []
    for turn in turns:
        if turn["speaker"] not in speakers:
            speakers.append(turn["speaker"])
    other = {speakers[i]: speakers[(i + 1) % len(speakers)] for i in range(len(speakers))}
    scenes: list[dict[str, Any]] = []
    for idx, turn in enumerate(turns):
        words = len(turn["line"].split())
        duration = max(2.5, round(words / 2.4 + 0.6, 1))
        partner = other.get(turn["speaker"], speakers[0])
        scenes.append({
            "order_index": idx,
            "title": turn["speaker"],
            "purpose": f"{turn['speaker']} speaks to {partner}",
            "narration_segment": turn["line"],
            "visual_description": (
                f"{turn['speaker']} faces {partner} and speaks. "
                "Picture follows the chosen visual style. No screenplay notes, camera labels, or title cards."
            ),
            "shot_type": "two_shot",
            "camera_angle": "eye_level",
            "camera_movement": "static",
            "lighting": "soft_daylight",
            "composition": "two_shot",
            "on_screen_text": turn["speaker"][:48],
            "sound_cue": "room_tone",
            "duration_sec": duration,
            "transition": "cut" if idx == 0 else "dissolve",
            "speaker_name": turn["speaker"],
            "dialogue": [{"speaker": turn["speaker"], "line": turn["line"]}],
            "silent_action_sec": 0.25,
            "pause_sec": 0.2,
        })
    return scenes


def clean_markdown_inline(text: str) -> str:
    """Strip markdown formatting tokens (#, *, **, quotes, screenplay labels) from a single-line title or field."""
    s = re.sub(r"^#+\s*", "", (text or "").strip())
    s = re.sub(r"^(?:SCREENPLAY\s*:|TITLE\s*:|SCENE\s*\d*\s*[:\-]?)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = s.strip().strip('"').strip("'").strip("“”‘’").strip()
    return re.sub(r"\s+", " ", s)


def parse_structured_screenplay(raw_text: str) -> dict[str, Any]:
    """Parse structured screenplay markdown/text (markdown, Fountain, AV, multi-scene) into clean metadata and scenes."""
    from backend.orchestration.audio_studio import sanitize_spoken_voiceover

    text = (raw_text or "").strip()
    if not text:
        return {"is_structured": False, "title": "Untitled Production", "subject": "Untitled Production", "scenes": []}

    # Normalize inline single-line pasted screenplays where ## SCENE or **VISUAL:** were pasted without newlines
    normalized = re.sub(r"\s*(##+\s*SCENE\s+\d+|(?:\n|^)\s*SCENE\s+\d+|(?:\n|^)\s*Scene\s+\d+)", r"\n\1", text, flags=re.IGNORECASE)
    normalized = re.sub(
        r"\s*(\*\*(?:VISUAL|CAMERA|LIGHTING|NARRATION\s*/?\s*VO|NARRATION|VO|ON-SCREEN\s+TEXT|SOUND|DIALOGUE|SPEECH)\s*:\*\*)",
        r"\n\1",
        normalized,
        flags=re.IGNORECASE,
    )

    # 1. Extract clean title
    title = ""
    m_scr = re.search(r"#?\s*SCREENPLAY\s*:\s*([^\n*#|]+)", normalized, flags=re.IGNORECASE)
    if m_scr:
        title = clean_markdown_inline(m_scr.group(1))
    else:
        first_line = normalized.splitlines()[0].strip()
        if first_line.startswith("#") or first_line.lower().startswith("title:"):
            title = clean_markdown_inline(re.split(r"\*Format:|\| Runtime:|\| Voice:", first_line, flags=re.IGNORECASE)[0])

    # 2. Extract header metadata (*Format: ... | Runtime: 28.0s | Voice: ...*)
    header_format = None
    header_runtime: float | None = None
    header_voice_gender: str | None = None

    m_fmt = re.search(r"Format\s*:\s*([^|*\n]+)", normalized, flags=re.IGNORECASE)
    if m_fmt:
        header_format = clean_markdown_inline(m_fmt.group(1))

    m_run = re.search(r"Runtime\s*:\s*(\d+(?:\.\d+)?)\s*s", normalized, flags=re.IGNORECASE)
    if m_run:
        header_runtime = float(m_run.group(1))

    m_voice = re.search(r"Voice\s*:\s*([^|*\n]+)", normalized, flags=re.IGNORECASE)
    if m_voice:
        v_low = m_voice.group(1).lower()
        if "female" in v_low and "male" not in v_low.replace("female", ""):
            header_voice_gender = "female"
        elif "male" in v_low and "female" not in v_low:
            header_voice_gender = "male"

    bible = _extract_character_and_scene_bible(normalized)

    # 3. Universal Scene Block Matching (including natural time-ranged headings like 'Scene 1 (0–8 seconds):' or '0-8 seconds:')
    header_regex = re.compile(
        r"(?:^|\n)\s*((?:##+\s*(?:SCENE|ACT)\b|(?:\(?\bACT\s+\d+.*?\bSCENE\s+\d+\)?)|SCENE\s+\d+|Scene\s+\d+|\[\s*SCENE\s+\d+\s*\]|\(\s*(?:ACT\s+\d+.*?)?Scene\s+\d+\s*\)|\d+\.\s*Scene\b|(?:\*\*)?\d+(?:\.\d+)?\s*(?:–|—|-|to)\s*\d+(?:\.\d+)?\s*(?:seconds?|secs?|s)\b|EXT\.|INT\.)[^\n]*)",
        re.IGNORECASE,
    )
    headers = list(header_regex.finditer(normalized))

    dialogue_turns = extract_dialogue_turns(normalized)
    has_voice_field = bool(re.search(
        r"(?:\*\*)?\s*(?:NARRATION|VO|DIALOGUE|SPEECH|SPOKEN)\b[^:\n]{0,24}:",
        normalized,
        flags=re.IGNORECASE,
    ))
    if len(dialogue_turns) >= 2 and not has_voice_field and len(headers) <= 1:
        scenes = _scenes_from_dialogue_turns(dialogue_turns)
        if not title:
            names = []
            for turn in dialogue_turns:
                if turn["speaker"] not in names:
                    names.append(turn["speaker"])
            title = " and ".join(names[:2]) or "Conversation"
        total_dur = header_runtime or round(sum(s["duration_sec"] for s in scenes), 1)
        return {
            "is_structured": True,
            "title": title[:80],
            "subject": title[:80],
            "header_format": header_format,
            "duration_sec": total_dur,
            "target_duration_sec": total_dur,
            "voice_gender": header_voice_gender,
            "character_name": dialogue_turns[0]["speaker"][:48],
            "character_description": f"Two people in a 2D animated conversation: {title}.",
            **bible,
            "scenes": scenes,
        }

    blocks: list[tuple[str, str]] = []

    if headers:
        for idx, h in enumerate(headers):
            h_line = h.group(1).strip()
            body_start = h.end()
            body_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(normalized)
            body_text = normalized[body_start:body_end].strip()
            # If the scene heading line itself has inline prose after ':' (e.g. 'Scene 1 (0–8 seconds): Boss says, "..."'),
            # split the heading from the inline body so quotes and visual descriptions are parsed!
            m_inline = re.match(
                r"^((?:##+\s*)?(?:SCENE|ACT)\s+\d+(?:\s*\([^)]*\))?|\d+(?:\.\d+)?\s*(?:–|—|-|to)\s*\d+(?:\.\d+)?\s*(?:seconds?|secs?|s)\b)\s*:\s*(.+)$",
                h_line,
                flags=re.IGNORECASE,
            )
            if m_inline:
                h_line = m_inline.group(1).strip()
                inline_rest = m_inline.group(2).strip()
                body_text = f"{inline_rest}\n{body_text}".strip() if body_text else inline_rest
            blocks.append((h_line, body_text))
    elif re.search(r"(?:\*\*)?\s*(?:VISUAL|NARRATION|VO|DIALOGUE|NARRATOR)\s*:", normalized, flags=re.IGNORECASE):
        # Structured content without explicit scene headings - parse as single/intro scene
        blocks.append(("Scene 1", normalized))

    scenes: list[dict[str, Any]] = []
    running_cursor = 0.0

    for idx, (h_line, body) in enumerate(blocks):
        # Extract explicit time range (e.g. 0–8 seconds) or duration (5.3s) from header or body start
        start_sec, end_sec, sc_dur = _parse_time_range(h_line)
        if sc_dur is None and body:
            first_body_line = body.splitlines()[0] if body.splitlines() else ""
            start_sec, end_sec, sc_dur = _parse_time_range(first_body_line)

        # Extract clean scene title
        title_raw = re.sub(r"\(\d+(?:\.\d+)?\s*(?:–|—|-|to)\s*\d+(?:\.\d+)?\s*(?:seconds?|secs?|s)\)", "", h_line, flags=re.IGNORECASE)
        title_raw = re.sub(r"\((\d+(?:\.\d+)?)\s*s\)", "", title_raw, flags=re.IGNORECASE)
        title_raw = re.sub(
            r"^(?:##+\s*)?(?:\(?\s*(?:ACT\s+\d+.*?)?SCENE\s+\d+\s*\)?|\[\s*SCENE\s+\d+\s*\]|\d+\.\s*Scene\b)[:\-]?\s*",
            "",
            title_raw,
            flags=re.IGNORECASE,
        )
        sc_title = clean_markdown_inline(title_raw).strip("():- ").strip() or f"Scene {idx + 1}"

        def _extract_field(field_regex: str) -> str:
            # Check bolded **FIELD:** or unbolded FIELD:
            fm = re.search(
                rf"(?:\*\*)?(?:{field_regex})(?:\*\*)?\s*:\s*(.*?)(?=\n(?:\*\*)?[A-Z/\s-]+(?:\*\*)?\s*:|\n##|\Z)",
                body,
                flags=re.IGNORECASE | re.DOTALL,
            )
            return clean_markdown_inline(fm.group(1)) if fm else ""

        visual = _extract_field(r"VISUAL|VISUALS?|ACTION|DESC|DESCRIPTION|VIDEO")
        camera_raw = _extract_field(r"CAMERA")
        lighting = _extract_field(r"LIGHTING") or "dramatic_cinematic"
        raw_narration = _extract_field(r"NARRATION\s*/?\s*VO|NARRATION|VO|DIALOGUE|SPEECH|SPOKEN|NARRATOR|AUDIO")

        # Extract ALL quoted dialogue turns in this scene with explicit speaker attribution
        scene_turns = _extract_quoted_dialogue_turns(body)
        if not scene_turns and raw_narration:
            # Check if raw_narration has explicit speaker turns
            inline_turns = extract_dialogue_turns(raw_narration)
            if inline_turns:
                scene_turns = [{"speaker": t["speaker"], "line": t["line"], "order": i} for i, t in enumerate(inline_turns)]

        if scene_turns:
            # Preserve exact user-written dialogue verbatim (joined for compatibility, turns kept separate)
            narration = " ".join(t["line"] for t in scene_turns)
        elif raw_narration:
            narration = sanitize_spoken_voiceover(raw_narration, default="")
        else:
            m_colon_dial = re.search(r"(?:^([A-Z0-9_\s]{2,20})\s*:\s*)([^\n]+)", body, flags=re.MULTILINE)
            if m_colon_dial:
                cand_label = re.sub(r"\s+", " ", m_colon_dial.group(1).strip().lower())
                if cand_label not in _NOT_SPEAKERS and "screenplay" not in cand_label and "guide" not in cand_label:
                    narration = sanitize_spoken_voiceover(m_colon_dial.group(2).strip(), default="")
                else:
                    narration = ""
            else:
                narration = ""

        # If natural scene prose (no explicit VISUAL: field), preserve body as visual_description
        if not visual and body:
            visual = re.sub(r"\s+", " ", body).strip()[:600]

        on_screen_text = _extract_field(r"ON-SCREEN\s+TEXT|TEXT") or sc_title
        on_screen_text = clean_markdown_inline(on_screen_text)
        sound_cue = _extract_field(r"SOUND|SFX") or "ambient_swell"
        if "whoosh" in sound_cue.lower():
            sound_cue = "subtle_chime"

        # Auto-compute duration based on narration word count if not explicit
        if not sc_dur:
            w_count = len(narration.split()) if narration else 0
            sc_dur = max(3.0, round(w_count / 2.5 + 0.8, 1)) if w_count > 0 else 4.0

        if start_sec is None:
            start_sec = round(running_cursor, 2)
        if end_sec is None:
            end_sec = round(start_sec + sc_dur, 2)
        running_cursor = end_sec

        shot_type, cam_angle, cam_move = "medium", "eye_level", "slow_push_in"
        if camera_raw:
            parts = [p.strip() for p in re.split(r"[/,|]", camera_raw) if p.strip()]
            if len(parts) >= 1:
                shot_type = parts[0]
            if len(parts) >= 2:
                cam_angle = parts[1]
            if len(parts) >= 3:
                cam_move = parts[2]

        # Determine primary speaker/voice casting per scene
        if scene_turns:
            speaker_name = scene_turns[0]["speaker"]
            voice_gender = "male"
            voice_id = "character_1"
        elif header_voice_gender == "male":
            voice_gender = "male"
            voice_id = "narrator_deep"
            speaker_name = "Narrator (Male — ChristopherNeural)"
        elif header_voice_gender == "female":
            voice_gender = "female"
            voice_id = "narrator_warm"
            speaker_name = "Narrator (Female — AriaNeural)"
        else:
            voice_gender = "male" if idx % 2 == 0 else "female"
            voice_id = "narrator_deep" if idx % 2 == 0 else "narrator_warm"
            speaker_name = "Lead Anchor (Male)" if idx % 2 == 0 else "Co-Narrator (Female)"

        scenes.append({
            "order_index": idx,
            "title": sc_title.title() if sc_title.isupper() else sc_title,
            "purpose": f"Deliver '{sc_title}'",
            "start_sec": start_sec,
            "end_sec": end_sec,
            "narration_segment": narration,
            "dialogue_turns": scene_turns,
            "dialogue": scene_turns,
            "visual_description": visual or f"Cinematic 3D animated scene depicting {sc_title}.",
            "shot_type": shot_type,
            "camera_angle": cam_angle,
            "camera_movement": cam_move,
            "lighting": lighting,
            "composition": "rule_of_thirds",
            "on_screen_text": on_screen_text[:48],
            "sound_cue": sound_cue,
            "duration_sec": max(2.0, sc_dur),
            "transition": "cut" if idx == 0 else ("smoothleft", "dissolve", "circleopen", "smoothright")[(idx - 1) % 4],
            "voice_gender": voice_gender,
            "voice_id": voice_id,
            "speaker_name": speaker_name,
            "preferred_scene_engine": "blender" if bible["animation_style"] == "3d_stylized" else ("hyperframes" if idx % 3 != 1 else "remotion"),
            "animation_theme": "3d_stylized" if bible["animation_style"] == "3d_stylized" else ("painterly_parallax" if "historic" in (visual + lighting).lower() else "pixar_character_world"),
            "silent_action_sec": 0.4,
            "pause_sec": 0.3,
        })

    if not title:
        # Derive a clean concise title from first sentence without markdown clutter or screenplay-guide framing
        cleaned = re.sub(r"\*\*[A-Z/\s-]+\s*:\*\*", " ", normalized)
        cleaned = re.sub(r"##+\s*SCENE\s+\d+\s*:", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\*Format:[^*]+\*", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"^(?:\d+\s*-?\s*(?:sec|second|seconds|min|minute|minutes|s)\s+)?(?:screenplay|production|video|script)\s+(?:guide|instructions?|outline|template|prompt)\b[:\-]?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = clean_markdown_inline(cleaned)
        words = [w for w in cleaned.split() if w]
        title = " ".join(words[:7]).title() if words else "Untitled Production"

    if title.isupper():
        title = title.title()

    # Extract concise character visual description from Scene 1 visual if available
    character_desc = f"Consistent protagonist identity, wardrobe, and silhouette for {title}."
    if scenes and scenes[0].get("visual_description"):
        first_sent = re.split(r"(?<=[.!?])\s+", scenes[0]["visual_description"])[0]
        character_desc = first_sent[:220]

    total_dur = header_runtime or (round(sum(s["duration_sec"] for s in scenes), 1) if scenes else None)

    return {
        "is_structured": len(scenes) >= 1 or bool(m_scr),
        "title": title[:80],
        "subject": title[:80],
        "header_format": header_format,
        "duration_sec": total_dur,
        "target_duration_sec": total_dur,
        "voice_gender": header_voice_gender,
        "character_name": title[:48],
        "character_description": character_desc,
        **bible,
        "scenes": scenes,
    }


def _parse_srt_or_vtt_to_scenes(text: str) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for idx, block in enumerate(blocks):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip() and ln.strip() != "WEBVTT"]
        if len(lines) < 2 or "-->" not in block:
            continue
        timing = next((ln for ln in lines if "-->" in ln), "")
        body = " ".join(ln for ln in lines if "-->" not in ln and not ln.isdigit())
        if not body:
            continue
        dur = 4.5
        try:
            start_s, end_s = [p.strip().split()[0].replace(",", ".") for p in timing.split("-->")]
            def _to_sec(ts: str) -> float:
                parts = [float(x) for x in ts.split(":")]
                return parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
            dur = max(2.5, round(_to_sec(end_s) - _to_sec(start_s), 2))
        except Exception:
            pass
        cues.append({
            "order_index": len(cues),
            "title": f"Beat {len(cues) + 1}",
            "narration_segment": body,
            "visual_description": f"2D/3D animated visual illustrating: {body}",
            "duration_sec": dur,
        })
    return cues


def extract_text_from_any_file(file_path: Path, filename: str | None = None) -> dict[str, Any]:
    """Read and extract structured text/scenes/metadata from ANY uploaded file format."""
    name = filename or file_path.name
    ext = Path(name).suffix.lower()
    size_bytes = file_path.stat().st_size if file_path.exists() else 0

    raw_text = ""
    file_kind = "document"
    extra_meta: dict[str, Any] = {}

    try:
        if ext in (".md", ".txt", ".fountain", ".rst", ".log", ".yaml", ".yml", ".ini", ".cfg", ".py", ".js", ".ts"):
            raw_text = file_path.read_text(encoding="utf-8", errors="replace")
            file_kind = "text"

        elif ext in (".srt", ".vtt"):
            raw_text = file_path.read_text(encoding="utf-8", errors="replace")
            file_kind = "subtitles"
            cues = _parse_srt_or_vtt_to_scenes(raw_text)
            extra_meta["parsed_subtitle_scenes"] = cues

        elif ext == ".json":
            raw_json = file_path.read_text(encoding="utf-8", errors="replace")
            file_kind = "json"
            try:
                data = json.loads(raw_json)
                if isinstance(data, dict) and "scenes" in data and isinstance(data["scenes"], list):
                    lines = [f"# SCREENPLAY: {data.get('title') or data.get('subject') or Path(name).stem}"]
                    for i, s in enumerate(data["scenes"]):
                        if isinstance(s, dict):
                            lines.append(f"## SCENE {i + 1}: {s.get('title', f'Scene {i + 1}')} ({s.get('duration_sec', 5.0)}s)")
                            lines.append(f"**VISUAL:** {s.get('visual_description') or s.get('description') or ''}")
                            lines.append(f"**NARRATION / VO:** {s.get('narration_segment') or s.get('narration') or s.get('text') or ''}")
                    raw_text = "\n".join(lines)
                else:
                    raw_text = json.dumps(data, indent=2)
            except Exception:
                raw_text = raw_json

        elif ext in (".csv", ".tsv"):
            content = file_path.read_text(encoding="utf-8", errors="replace")
            file_kind = "spreadsheet"
            delim = "\t" if ext == ".tsv" else ","
            reader = list(csv.reader(io.StringIO(content), delimiter=delim))
            lines = [f"# SCREENPLAY: {Path(name).stem.replace('_', ' ').title()}"]
            for i, row in enumerate(reader[1:] if len(reader) > 1 else reader):
                joined = " | ".join(c.strip() for c in row if c.strip())
                if joined:
                    lines.append(f"## SCENE {i + 1}: Beat {i + 1} (5.0s)\n**VISUAL:** {joined}\n**NARRATION / VO:** {joined}")
            raw_text = "\n".join(lines)

        elif ext in (".html", ".htm", ".xml", ".svg"):
            content = file_path.read_text(encoding="utf-8", errors="replace")
            file_kind = "markup"
            stripped = re.sub(r"<script\b[^>]*>.*?</script>", " ", content, flags=re.IGNORECASE | re.DOTALL)
            stripped = re.sub(r"<style\b[^>]*>.*?</style>", " ", stripped, flags=re.IGNORECASE | re.DOTALL)
            stripped = re.sub(r"<[^>]+>", "\n", stripped)
            raw_text = html.unescape(re.sub(r"\n{3,}", "\n\n", stripped)).strip()

        elif ext == ".docx":
            file_kind = "docx"
            with zipfile.ZipFile(file_path, "r") as zf:
                if "word/document.xml" in zf.namelist():
                    xml_bytes = zf.read("word/document.xml")
                    root = ET.fromstring(xml_bytes)
                    paras: list[str] = []
                    for p in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                        texts = [t.text for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if t.text]
                        if texts:
                            paras.append("".join(texts))
                    raw_text = "\n".join(paras)

        elif ext in (".doc", ".rtf", ".odt") and shutil.which("textutil"):
            file_kind = "office_document"
            out = subprocess.check_output(["textutil", "-convert", "txt", "-stdout", str(file_path)], text=True, timeout=15)
            raw_text = out.strip()

        elif ext == ".pdf":
            file_kind = "pdf"
            try:
                import pypdf  # type: ignore
                reader = pypdf.PdfReader(str(file_path))
                raw_text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            except Exception:
                if shutil.which("pdftotext"):
                    raw_text = subprocess.check_output(["pdftotext", str(file_path), "-"], text=True, timeout=15).strip()
                else:
                    # Fallback stream text extraction
                    data = file_path.read_bytes()
                    chunks = re.findall(rb"\(([^\(\)]{4,200})\)", data)
                    raw_text = " ".join(c.decode("latin-1", errors="ignore") for c in chunks[:400]).strip()

        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
            file_kind = "image"
            from PIL import Image
            with Image.open(file_path) as im:
                w, h = im.size
                extra_meta["width"] = w
                extra_meta["height"] = h
                extra_meta["mode"] = im.mode
            raw_text = f"Reference image '{name}' ({extra_meta.get('width')}x{extra_meta.get('height')})."

        elif ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".m4a", ".aac", ".flac"):
            file_kind = "video" if ext in (".mp4", ".mov", ".mkv", ".webm", ".avi") else "audio"
            if shutil.which("ffprobe"):
                out = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
                    text=True, timeout=15,
                ).strip()
                extra_meta["duration_sec"] = round(float(out or 0.0), 2)
            raw_text = f"Uploaded {file_kind} asset '{name}' (duration: {extra_meta.get('duration_sec', 'unknown')}s)."

        else:
            # Universal fallback: try UTF-8 text, then macOS textutil, then printable strings
            raw_bytes = file_path.read_bytes()
            try:
                raw_text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raw_text = raw_bytes.decode("latin-1", errors="replace")
    except Exception as exc:
        raw_text = f"File '{name}' ({size_bytes} bytes) attached ({exc})."

    parsed = parse_structured_screenplay(raw_text)
    if not parsed["scenes"] and extra_meta.get("parsed_subtitle_scenes"):
        parsed["scenes"] = extra_meta["parsed_subtitle_scenes"]
        parsed["is_structured"] = True

    return {
        "ok": True,
        "filename": name,
        "extension": ext,
        "size_bytes": size_bytes,
        "file_kind": file_kind,
        "extracted_text": raw_text,
        "parsed_screenplay": parsed,
        "metadata": extra_meta,
    }
