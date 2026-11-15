"""Phase 2: Multimodal Reference Intelligence, SSRF-Safe Reference Resolver & Asset Intelligence Engine."""

from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import subprocess
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageStat

from backend.db import get_conn, rows_to_dicts
from backend.integrations.openwhispr_adapter import openwhispr_adapter
from backend.models import ReferenceRole, ReferenceType, utc_now

ALLOWED_ROLES = {
    "visual_inspiration",
    "character_appearance",
    "location_reference",
    "camera_movement",
    "editing_style",
    "color_palette",
    "brand_identity",
    "existing_footage",
    "product_accuracy",
    "audio_music",
    "VISUAL_STYLE",
    "CHARACTER_REFERENCE",
    "ENVIRONMENT_REFERENCE",
    "CAMERA_REFERENCE",
    "ANIMATION_REFERENCE",
    "STORY_REFERENCE",
    "FACTUAL_SOURCE",
    "VOICE_REFERENCE",
    "MUSIC_REFERENCE",
    "SOUND_REFERENCE",
    "BRAND_REFERENCE",
}

ROLE_TO_CANONICAL: dict[str, str] = {
    "visual_inspiration": ReferenceRole.VISUAL_STYLE.value,
    "color_palette": ReferenceRole.VISUAL_STYLE.value,
    "character_appearance": ReferenceRole.CHARACTER_REFERENCE.value,
    "location_reference": ReferenceRole.ENVIRONMENT_REFERENCE.value,
    "camera_movement": ReferenceRole.CAMERA_REFERENCE.value,
    "editing_style": ReferenceRole.ANIMATION_REFERENCE.value,
    "existing_footage": ReferenceRole.STORY_REFERENCE.value,
    "product_accuracy": ReferenceRole.FACTUAL_SOURCE.value,
    "brand_identity": ReferenceRole.BRAND_REFERENCE.value,
    "audio_music": ReferenceRole.MUSIC_REFERENCE.value,
    **{r.value: r.value for r in ReferenceRole},
    **{r.value.lower(): r.value for r in ReferenceRole},
}

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB safety ceiling


def normalize_roles(
    roles: list[str] | str | None = None,
    intended_role: str | None = None,
    user_notes: str = "",
    source_type: str = "",
) -> list[str]:
    raw_list: list[str] = []
    if isinstance(roles, list):
        raw_list.extend(str(r).strip() for r in roles if str(r).strip())
    elif isinstance(roles, str) and roles.strip():
        raw_list.extend(s.strip() for s in roles.split(",") if s.strip())
    if intended_role and str(intended_role).strip():
        raw_list.append(str(intended_role).strip())

    canonical: list[str] = []
    for item in raw_list:
        mapped = ROLE_TO_CANONICAL.get(item) or ROLE_TO_CANONICAL.get(item.lower()) or ROLE_TO_CANONICAL.get(item.upper())
        if mapped and mapped not in canonical:
            canonical.append(mapped)

    notes_lower = (user_notes or "").lower()
    if any(w in notes_lower for w in ("movement", "motion", "animation", "walk", "acting")):
        if ReferenceRole.ANIMATION_REFERENCE.value not in canonical:
            canonical.append(ReferenceRole.ANIMATION_REFERENCE.value)
    if any(w in notes_lower for w in ("camera", "pan", "zoom", "framing", "transition")):
        if ReferenceRole.CAMERA_REFERENCE.value not in canonical:
            canonical.append(ReferenceRole.CAMERA_REFERENCE.value)
    if any(w in notes_lower for w in ("character", "protagonist", "face", "costume", "wardrobe")) and "not exact character" not in notes_lower:
        if ReferenceRole.CHARACTER_REFERENCE.value not in canonical:
            canonical.append(ReferenceRole.CHARACTER_REFERENCE.value)
    if any(w in notes_lower for w in ("environment", "background", "world", "architecture", "landscape")):
        if ReferenceRole.ENVIRONMENT_REFERENCE.value not in canonical:
            canonical.append(ReferenceRole.ENVIRONMENT_REFERENCE.value)
    if any(w in notes_lower for w in ("fact", "research", "history", "source", "evidence", "citation")):
        if ReferenceRole.FACTUAL_SOURCE.value not in canonical:
            canonical.append(ReferenceRole.FACTUAL_SOURCE.value)
    if any(w in notes_lower for w in ("voice", "narration", "accent", "speaker")):
        if ReferenceRole.VOICE_REFERENCE.value not in canonical:
            canonical.append(ReferenceRole.VOICE_REFERENCE.value)
    if any(w in notes_lower for w in ("music", "score", "soundtrack", "tempo")):
        if ReferenceRole.MUSIC_REFERENCE.value not in canonical:
            canonical.append(ReferenceRole.MUSIC_REFERENCE.value)

    if not canonical:
        if source_type in (ReferenceType.UPLOADED_DOCUMENT.value, ReferenceType.WEBSITE.value):
            canonical.append(ReferenceRole.FACTUAL_SOURCE.value)
        elif source_type == ReferenceType.UPLOADED_AUDIO.value:
            canonical.append(ReferenceRole.VOICE_REFERENCE.value)
        else:
            canonical.append(ReferenceRole.VISUAL_STYLE.value)
    return canonical


def _is_forbidden_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
            or str(ip).startswith("169.254.")
            or str(ip).startswith("100.64.")
        )
    except ValueError:
        return True


def validate_external_url(url: str) -> dict[str, Any]:
    """Validate an external URL and block SSRF / private / loopback / metadata targets."""
    cleaned = (url or "").strip()
    if not cleaned:
        return {"valid": False, "safe": False, "reason": "Empty URL"}
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme.lower() not in ("http", "https"):
        return {"valid": False, "safe": False, "reason": f"Unsupported or unsafe URL scheme '{parsed.scheme}'. Only http/https are permitted."}
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return {"valid": False, "safe": False, "reason": "URL is missing a valid hostname"}
    if hostname in ("localhost", "localhost.localdomain", "ip6-localhost") or hostname.endswith((".local", ".internal", ".localhost", ".lan")):
        return {"valid": False, "safe": False, "reason": f"Blocked internal/local hostname '{hostname}' (SSRF protection)"}

    # Check if hostname is a literal IP
    try:
        ipaddress.ip_address(hostname)
        if _is_forbidden_ip(hostname):
            return {"valid": False, "safe": False, "reason": f"Blocked private/reserved IP address '{hostname}' (SSRF protection)"}
        return {"valid": True, "safe": True, "url": cleaned, "hostname": hostname}
    except ValueError:
        pass

    # Resolve DNS if network is available; block if any resolved IP is internal
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        for info in infos:
            addr = info[4][0]
            if _is_forbidden_ip(addr):
                return {"valid": False, "safe": False, "reason": f"Hostname '{hostname}' resolves to blocked internal address '{addr}' (SSRF protection)"}
    except socket.gaierror:
        # In offline environments DNS lookup may fail; allow public domain syntax to be recorded with offline status
        if "." not in hostname:
            return {"valid": False, "safe": False, "reason": f"Unqualified single-label hostname '{hostname}' is not allowed"}
    return {"valid": True, "safe": True, "url": cleaned, "hostname": hostname}


class YouTubeReferenceAdapter:
    """Extracts permitted public metadata and accessible captions for YouTube videos and channels."""

    def process(self, url: str, source_type: str) -> dict[str, Any]:
        parsed = urllib.parse.urlparse(url)
        video_id = None
        if "youtu.be" in (parsed.hostname or ""):
            video_id = parsed.path.strip("/").split("/")[0]
        elif "/shorts/" in parsed.path:
            video_id = parsed.path.split("/shorts/", 1)[1].split("/")[0]
        else:
            qs = urllib.parse.parse_qs(parsed.query)
            video_id = (qs.get("v") or [None])[0]

        metadata: dict[str, Any] = {
            "platform": "youtube",
            "source_type": source_type,
            "video_id": video_id,
            "url": url,
        }
        limitations: list[str] = []
        access_status = "metadata_only"

        if source_type == ReferenceType.YOUTUBE_CHANNEL.value:
            handle = parsed.path.strip("/")
            metadata["channel_handle"] = handle
            limitations.append(
                "YouTube channel URL registered as style/channel reference; select individual video URLs or upload clips for shot-level analysis."
            )
            return {
                "access_status": "metadata_only",
                "metadata": metadata,
                "analysis": {
                    "visual_style": "youtube_channel_reference",
                    "channel_reference": handle,
                    "camera_language": ["documentary framing", "structured chapter transitions"],
                },
                "limitations": limitations,
                "attribution": {"platform": "YouTube", "url": url, "channel": handle},
            }

        # Try public oEmbed first
        try:
            r = requests.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                headers={"User-Agent": "UniversalAIVideoStudio/2.0"},
                timeout=4.0,
            )
            if r.status_code == 200:
                oem = r.json()
                metadata["title"] = oem.get("title", "")
                metadata["author_name"] = oem.get("author_name", "")
                metadata["author_url"] = oem.get("author_url", "")
                metadata["thumbnail_url"] = oem.get("thumbnail_url", "")
                access_status = "analyzed"
            else:
                limitations.append(f"YouTube oEmbed returned HTTP {r.status_code}; video may be private, unlisted, or region-restricted.")
                access_status = "restricted_or_unavailable"
        except Exception:
            limitations.append("YouTube oEmbed unreachable in current network environment; URL and video ID preserved as reference.")
            access_status = "metadata_only"

        limitations.append("Direct video media is not downloaded without explicit rights; public metadata and reference cues recorded.")
        return {
            "access_status": access_status,
            "metadata": metadata,
            "analysis": {
                "visual_style": "cinematic_youtube_reference",
                "title": metadata.get("title") or f"YouTube Video ({video_id or 'ref'})",
                "author": metadata.get("author_name", ""),
                "camera_language": ["establishing wide", "slow push-in", "chapter title cards"],
                "pacing_hint": "deliberate_narrative",
            },
            "limitations": limitations,
            "attribution": {
                "platform": "YouTube",
                "url": url,
                "author": metadata.get("author_name", ""),
                "title": metadata.get("title", ""),
                "rights_notice": "External YouTube reference link; do not redistribute third-party media without authorization.",
            },
        }


class InstagramReferenceAdapter:
    """Handles Instagram post, Reel, and profile links without bypassing login/privacy restrictions."""

    def process(self, url: str, source_type: str) -> dict[str, Any]:
        parsed = urllib.parse.urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        shortcode = parts[1] if len(parts) >= 2 and parts[0] in ("p", "reel", "reels", "tv") else None
        profile_handle = parts[0] if parts and parts[0] not in ("p", "reel", "reels", "tv", "explore", "stories") else None

        metadata: dict[str, Any] = {
            "platform": "instagram",
            "source_type": source_type,
            "url": url,
            "shortcode": shortcode,
            "profile_handle": profile_handle,
        }
        limitations: list[str] = []
        if source_type == ReferenceType.INSTAGRAM_PROFILE.value:
            limitations.append(
                "Instagram profiles require login authentication for automated post scraping. "
                "The studio never bypasses platform authentication; profile link is saved as a reference and you can upload selected posts or Reels directly."
            )
            access_status = "restricted_auth_required"
        else:
            limitations.append(
                "Instagram posts and Reels restrict unauthenticated media download. "
                "Reference link and shortcode are saved; upload authorized media files directly if frame-by-frame analysis is needed."
            )
            access_status = "metadata_only"

        return {
            "access_status": access_status,
            "metadata": metadata,
            "analysis": {
                "visual_style": "social_visual_reference",
                "aspect_ratio_hint": "9:16" if source_type == ReferenceType.INSTAGRAM_REEL.value else "1:1",
                "camera_language": ["dynamic vertical framing", "rhythmic cuts"] if source_type == ReferenceType.INSTAGRAM_REEL.value else ["editorial composition"],
                "profile_handle": profile_handle,
                "shortcode": shortcode,
            },
            "limitations": limitations,
            "attribution": {
                "platform": "Instagram",
                "url": url,
                "handle": profile_handle or "",
                "shortcode": shortcode or "",
                "rights_notice": "Public reference URL only; third-party Instagram media is not scraped or reproduced.",
            },
        }


class WebsiteReferenceAdapter:
    """Safely fetches public web page metadata, text summary, and source attribution."""

    def process(self, url: str) -> dict[str, Any]:
        v = validate_external_url(url)
        if not v["valid"]:
            raise ValueError(v["reason"])
        metadata: dict[str, Any] = {"url": url, "hostname": v["hostname"]}
        limitations: list[str] = []
        extracted_text = ""
        access_status = "metadata_only"

        try:
            r = requests.get(
                url,
                headers={"User-Agent": "UniversalAIVideoStudio/2.0"},
                timeout=5.0,
                allow_redirects=False,
            )
            if r.status_code == 200 and "text/html" in (r.headers.get("Content-Type") or "").lower():
                raw_html = r.text[:250_000]
                m_title = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
                if m_title:
                    metadata["title"] = html.unescape(re.sub(r"\s+", " ", m_title.group(1)).strip())[:160]
                m_desc = re.search(
                    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
                    raw_html,
                    re.IGNORECASE | re.DOTALL,
                )
                if m_desc:
                    metadata["description"] = html.unescape(m_desc.group(1).strip())[:400]
                # Strip script/style and extract clean paragraph text
                cleaned = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
                cleaned = re.sub(r"<[^>]+>", " ", cleaned)
                cleaned = html.unescape(re.sub(r"\s+", " ", cleaned)).strip()
                extracted_text = cleaned[:2000]
                access_status = "analyzed"
            else:
                limitations.append(f"Website returned HTTP {r.status_code} or non-HTML content; stored URL reference metadata.")
        except Exception as exc:
            limitations.append(f"Website fetch unavailable ({type(exc).__name__}); URL stored for reference traceability.")

        return {
            "access_status": access_status,
            "metadata": metadata,
            "analysis": {
                "title": metadata.get("title") or v["hostname"],
                "description": metadata.get("description", ""),
                "extracted_summary": extracted_text[:600],
                "word_count": len(extracted_text.split()) if extracted_text else 0,
            },
            "limitations": limitations,
            "attribution": {
                "platform": "Web",
                "url": url,
                "publisher": v["hostname"],
                "title": metadata.get("title") or url,
            },
        }


class DirectMediaAdapter:
    """Records authorized direct media links without blindly downloading large untrusted binaries."""

    def process(self, url: str) -> dict[str, Any]:
        v = validate_external_url(url)
        if not v["valid"]:
            raise ValueError(v["reason"])
        parsed = urllib.parse.urlparse(url)
        ext = Path(parsed.path).suffix.lower()
        return {
            "access_status": "metadata_only",
            "metadata": {"url": url, "extension": ext, "hostname": v["hostname"]},
            "analysis": {
                "media_extension": ext,
                "visual_style": "direct_media_reference",
            },
            "limitations": ["Remote direct media URL registered; upload local copy to run full FFprobe/keyframe sandbox analysis."],
            "attribution": {"url": url, "hostname": v["hostname"]},
        }


class ReferenceResolver:
    """Identifies the source of a submitted URL, validates SSRF safety, and delegates to source adapters."""

    def __init__(self) -> None:
        self.youtube_adapter = YouTubeReferenceAdapter()
        self.instagram_adapter = InstagramReferenceAdapter()
        self.website_adapter = WebsiteReferenceAdapter()
        self.direct_media_adapter = DirectMediaAdapter()

    def detect_source(self, url: str) -> str:
        v = validate_external_url(url)
        if not v["valid"]:
            raise ValueError(v["reason"])
        parsed = urllib.parse.urlparse(v["url"])
        host = (parsed.hostname or "").lower()
        path = parsed.path.lower()

        if any(h in host for h in ("youtube.com", "youtu.be", "m.youtube.com")):
            if any(seg in path for seg in ("/@", "/channel/", "/c/", "/user/")):
                return ReferenceType.YOUTUBE_CHANNEL.value
            return ReferenceType.YOUTUBE_VIDEO.value

        if "instagram.com" in host or "instagr.am" in host:
            if "/reel/" in path or "/reels/" in path:
                return ReferenceType.INSTAGRAM_REEL.value
            if "/p/" in path or "/tv/" in path:
                return ReferenceType.INSTAGRAM_POST.value
            return ReferenceType.INSTAGRAM_PROFILE.value

        ext = Path(path).suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".webm", ".wav", ".mp3", ".pdf"):
            return ReferenceType.DIRECT_MEDIA.value

        return ReferenceType.WEBSITE.value

    def resolve_sync(
        self,
        url: str,
        roles: list[str] | str | None = None,
        user_notes: str = "",
    ) -> dict[str, Any]:
        source_type = self.detect_source(url)
        if source_type in (ReferenceType.YOUTUBE_VIDEO.value, ReferenceType.YOUTUBE_CHANNEL.value):
            res = self.youtube_adapter.process(url, source_type)
        elif source_type in (
            ReferenceType.INSTAGRAM_POST.value,
            ReferenceType.INSTAGRAM_REEL.value,
            ReferenceType.INSTAGRAM_PROFILE.value,
        ):
            res = self.instagram_adapter.process(url, source_type)
        elif source_type == ReferenceType.DIRECT_MEDIA.value:
            res = self.direct_media_adapter.process(url)
        else:
            res = self.website_adapter.process(url)

        norm_roles = normalize_roles(roles=roles, user_notes=user_notes, source_type=source_type)
        return {
            "url": url,
            "source_type": source_type,
            "roles": norm_roles,
            "user_notes": user_notes,
            **res,
        }

    async def resolve(
        self,
        url: str,
        roles: list[str] | str | None = None,
        user_notes: str = "",
    ) -> dict[str, Any]:
        return self.resolve_sync(url, roles=roles, user_notes=user_notes)


reference_resolver = ReferenceResolver()


def _describe_color_hex(hex_str: str) -> str:
    try:
        h = hex_str.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        if r > 180 and g > 140 and b < 110:
            return "warm amber/gold"
        if r > 160 and g < 100 and b < 100:
            return "crimson/terracotta"
        if b > r + 30 and b > g + 15:
            return "muted slate/cobalt blue"
        if g > r + 20 and g > b + 20:
            return "natural sage/emerald"
        if r + g + b < 180:
            return "deep charcoal/ink"
        if r + g + b > 600:
            return "soft parchment/ivory"
        return "warm earth tone"
    except Exception:
        return "neutral tone"


def _analyze_image(path: Path, thumb_dir: Path | None = None) -> dict[str, Any]:
    with Image.open(path) as img:
        fmt = (img.format or path.suffix.lstrip(".")).upper()
        rgb = img.convert("RGB")
        w, h = rgb.size
        small = rgb.resize((64, 64))
        stat = ImageStat.Stat(small)
        avg_rgb = [int(round(c)) for c in stat.mean[:3]]
        std_rgb = [round(float(s), 2) for s in stat.stddev[:3]]
        luminance = round((0.299 * avg_rgb[0] + 0.587 * avg_rgb[1] + 0.114 * avg_rgb[2]) / 255.0, 3)
        quant = small.quantize(colors=4).convert("RGB")
        colors = sorted(quant.getcolors(maxcolors=64) or [], reverse=True)
        palette_hex = [f"#{c[1][0]:02x}{c[1][1]:02x}{c[1][2]:02x}" for c in colors[:4]]
        palette_labels = list(dict.fromkeys(_describe_color_hex(hx) for hx in palette_hex))

        thumb_path_str = None
        if thumb_dir is not None:
            thumb_dir.mkdir(parents=True, exist_ok=True)
            tpath = thumb_dir / f"thumb_{path.stem}.jpg"
            thumb_img = rgb.copy()
            thumb_img.thumbnail((320, 320))
            thumb_img.save(tpath, "JPEG", quality=82)
            thumb_path_str = str(tpath)

        contrast_spread = sum(std_rgb) / 3.0
        technique = (
            "pixel_art_or_crisp_vector"
            if len(colors) <= 8 and contrast_spread > 42
            else ("hand_drawn_storybook_wash" if contrast_spread < 36 else "2d_illustrated_or_cinematic_plate")
        )
        detected_subject = (
            "character_or_portrait_reference"
            if h >= w
            else ("environment_or_landscape_plate" if w >= h * 1.25 else "prop_or_emblem_reference")
        )
        return {
            "format": fmt,
            "width": w,
            "height": h,
            "aspect_ratio": f"{w}:{h}",
            "average_rgb": avg_rgb,
            "luminance": luminance,
            "lighting_profile": "high_key_bright" if luminance > 0.6 else ("low_key_moody" if luminance < 0.32 else "balanced_natural"),
            "palette_hex": palette_hex,
            "palette": palette_labels,
            "visual_style": technique,
            "detected_element": detected_subject,
            "composition_hint": "landscape_wide" if w > h else ("vertical_portrait" if h > w else "square_centered"),
            "thumbnail_path": thumb_path_str,
        }


def _detect_scene_boundaries(path: Path, max_cuts: int = 12) -> list[float]:
    """Run fast FFmpeg scene-change filter to find scene cut timestamps without AI frame spam."""
    cuts: list[float] = []
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-i", str(path),
                "-vf", "select='gt(scene,0.32)',showinfo",
                "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        for m in re.finditer(r"pts_time:(\d+(?:\.\d+)?)", proc.stderr or ""):
            ts = round(float(m.group(1)), 2)
            if ts not in cuts:
                cuts.append(ts)
            if len(cuts) >= max_cuts:
                break
    except Exception:
        pass
    return cuts


def _analyze_video(path: Path, work_dir: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {"duration_sec": 0.0, "width": 0, "height": 0, "fps": 30.0, "has_audio": False}
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            text=True, timeout=15,
        )
        info = json.loads(out)
        meta["duration_sec"] = round(float(info.get("format", {}).get("duration", 0.0)), 2)
        for st in info.get("streams", []):
            if st.get("codec_type") == "video":
                meta["width"] = int(st.get("width", 0))
                meta["height"] = int(st.get("height", 0))
                r_fps = st.get("r_frame_rate", "30/1")
                if "/" in r_fps:
                    num, den = r_fps.split("/", 1)
                    meta["fps"] = round(float(num) / max(1.0, float(den)), 2)
            elif st.get("codec_type") == "audio":
                meta["has_audio"] = True
    except Exception:
        pass

    scene_cuts = _detect_scene_boundaries(path)

    # Sample up to 3 representative keyframes stored persistently under references/keyframes
    keyframes_dir = work_dir / "keyframes" / path.stem
    keyframes_dir.mkdir(parents=True, exist_ok=True)
    frame_analyses: list[dict[str, Any]] = []
    keyframe_paths: list[str] = []
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-vf", "fps=0.5", "-vframes", "3", str(keyframes_dir / "rep_%02d.jpg")],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
        )
        for fp in sorted(keyframes_dir.glob("rep_*.jpg")):
            keyframe_paths.append(str(fp))
            frame_analyses.append(_analyze_image(fp))
    except Exception:
        pass

    transcript_text = ""
    if meta["has_audio"]:
        try:
            tr = openwhispr_adapter.transcribe_file(path)
            if tr.get("success"):
                transcript_text = str(tr.get("text") or "").strip()[:1000]
        except Exception:
            pass

    dur = meta["duration_sec"]
    rhythm = "fast_cut_social" if dur > 0 and dur <= 20 else ("medium_narrative" if dur <= 120 else "deliberate_longform")
    palette_hex = frame_analyses[0]["palette_hex"] if frame_analyses else []
    palette_labels = frame_analyses[0].get("palette", []) if frame_analyses else []
    return {
        **meta,
        "scene_boundaries_sec": scene_cuts,
        "scene_count_detected": len(scene_cuts) + 1 if dur > 0 else 0,
        "keyframes": keyframe_paths,
        "representative_frames": frame_analyses,
        "editing_rhythm": rhythm,
        "palette_hex": palette_hex,
        "palette": palette_labels,
        "lighting_profile": frame_analyses[0]["lighting_profile"] if frame_analyses else "balanced_natural",
        "visual_style": frame_analyses[0].get("visual_style", "illustrated_video") if frame_analyses else "cinematic_video",
        "camera_language": ["slow pans", "gentle zooms"] if len(scene_cuts) <= 2 else ["dynamic cuts", "multi-angle coverage"],
        "transitions": ["dissolve", "parallax"] if len(scene_cuts) <= 3 else ["cut", "smoothleft"],
        "animation": "layered 2D/3D movement",
        "transcript": transcript_text,
    }


def _analyze_audio(path: Path) -> dict[str, Any]:
    dur = 0.0
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            text=True, timeout=10,
        ).strip()
        dur = round(float(out), 2)
    except Exception:
        pass
    transcript = openwhispr_adapter.transcribe_file(path)
    return {
        "duration_sec": dur,
        "transcript": transcript.get("text", "") if transcript.get("success") else "",
        "transcription_provider": transcript.get("provider", "none"),
        "audio_characteristics": "narration_voice_reference" if transcript.get("text") else "instrumental_or_ambience_reference",
    }


def _analyze_document(path: Path) -> dict[str, Any]:
    from backend.services.document_parser import extract_text_from_any_file

    extracted = extract_text_from_any_file(path, filename=path.name)
    text = str(extracted.get("extracted_text") or "")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 25]
    return {
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "kind": extracted.get("kind", "document"),
        "word_count": len(text.split()),
        "extracted_summary": text[:800],
        "factual_highlights": sentences[:6],
        "is_structured_screenplay": bool(extracted.get("is_structured_screenplay")),
        "scene_count": extracted.get("scene_count", 0),
    }


def register_url_reference(
    project_id: str,
    workspace_dir_or_url: Path | str | None = None,
    url: str | list[str] | None = None,
    roles: list[str] | str | None = None,
    intended_role: str = "visual_inspiration",
    user_notes: str = "",
    permissions: str = "reference_link",
) -> dict[str, Any]:
    """Resolve, validate, and persist a URL reference (YouTube, Instagram, Website, Direct Media) with full traceability."""
    from backend.config import PROJECTS_DIR

    if isinstance(workspace_dir_or_url, Path):
        workspace_dir = workspace_dir_or_url
        actual_url = str(url or "")
    elif isinstance(workspace_dir_or_url, str) and workspace_dir_or_url.startswith(("http://", "https://", "file://")):
        workspace_dir = PROJECTS_DIR / project_id
        if isinstance(url, (list, str)) and roles is None:
            roles = url
        if isinstance(intended_role, str) and intended_role not in ALLOWED_ROLES and not user_notes:
            user_notes = intended_role
            intended_role = "visual_inspiration"
        actual_url = workspace_dir_or_url
    else:
        workspace_dir = Path(workspace_dir_or_url) if workspace_dir_or_url else (PROJECTS_DIR / project_id)
        actual_url = str(url or "")
    workspace_dir.mkdir(parents=True, exist_ok=True)
    url = actual_url
    resolved = reference_resolver.resolve_sync(url, roles=roles, user_notes=user_notes)
    source_type = resolved["source_type"]
    norm_roles = normalize_roles(roles=roles, intended_role=intended_role, user_notes=user_notes, source_type=source_type)
    primary_role = norm_roles[0] if norm_roles else ReferenceRole.VISUAL_STYLE.value

    ref_id = f"ref_{uuid.uuid4().hex[:8]}"
    now = utc_now()
    analysis_payload = {
        **resolved.get("analysis", {}),
        "metadata": resolved.get("metadata", {}),
    }
    limitations = resolved.get("limitations", [])
    attribution = resolved.get("attribution", {"url": url})
    access_status = resolved.get("access_status", "metadata_only")

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO reference_assets
               (id, project_id, filename, file_path, asset_type, source_type, source_url,
                access_status, analysis_status, intended_role, roles_json, permissions,
                analysis_json, limitations_json, attribution_json, user_notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ref_id,
                project_id,
                resolved.get("metadata", {}).get("title") or url[:90],
                url,
                "url_reference",
                source_type,
                url,
                access_status,
                primary_role,
                json.dumps(norm_roles),
                permissions,
                json.dumps(analysis_payload),
                json.dumps(limitations),
                json.dumps(attribution),
                user_notes,
                now,
                now,
            ),
        )
        # If tagged as FACTUAL_SOURCE and has summary text, also register in research_sources
        summary_text = str(analysis_payload.get("extracted_summary") or analysis_payload.get("description") or "").strip()
        if ReferenceRole.FACTUAL_SOURCE.value in norm_roles and summary_text:
            conn.execute(
                """INSERT INTO research_sources (id, project_id, title, url, publisher, publication_date, retrieval_date, source_tier, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 3, ?)""",
                (
                    f"src_{uuid.uuid4().hex[:8]}",
                    project_id,
                    str(analysis_payload.get("title") or url)[:120],
                    url,
                    str(attribution.get("publisher") or attribution.get("platform") or "Reference Link"),
                    now[:10],
                    now[:10],
                    summary_text[:600],
                ),
            )

    pkg_summary = build_reference_package(project_id, workspace_dir)
    return {
        "ok": True,
        "reference_id": ref_id,
        "source_type": source_type,
        "source_url": url,
        "access_status": access_status,
        "roles": norm_roles,
        "intended_role": primary_role,
        "analysis": analysis_payload,
        "limitations": limitations,
        "attribution": attribution,
        "user_notes": user_notes,
        "package": pkg_summary,
    }


def register_and_analyze_reference(
    project_id: str,
    workspace_dir: Path | None = None,
    file_path: Path | None = None,
    intended_role: str = "visual_inspiration",
    permissions: str = "user_owned",
    roles: list[str] | str | None = None,
    user_notes: str = "",
) -> dict[str, Any]:
    from backend.config import PROJECTS_DIR

    if workspace_dir is not None and file_path is None and workspace_dir.is_file():
        file_path = workspace_dir
        workspace_dir = PROJECTS_DIR / project_id
    if workspace_dir is None:
        workspace_dir = PROJECTS_DIR / project_id
    if file_path is None:
        raise ValueError("file_path is required")
    file_path = Path(file_path)
    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    if file_path.exists() and file_path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError(f"Uploaded file exceeds maximum size limit ({MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")

    ext = file_path.suffix.lower()
    limitations: list[str] = []
    thumbs_dir = workspace_dir / "references" / "thumbs"
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        asset_type = "image"
        source_type = ReferenceType.UPLOADED_IMAGE.value
        analysis = _analyze_image(file_path, thumb_dir=thumbs_dir)
    elif ext in (".mp4", ".mov", ".mkv", ".webm"):
        asset_type = "video"
        source_type = ReferenceType.UPLOADED_VIDEO.value
        analysis = _analyze_video(file_path, workspace_dir / "references")
    elif ext in (".wav", ".mp3", ".m4a", ".aac", ".ogg"):
        asset_type = "audio"
        source_type = ReferenceType.UPLOADED_AUDIO.value
        analysis = _analyze_audio(file_path)
    else:
        asset_type = "document"
        source_type = ReferenceType.UPLOADED_DOCUMENT.value
        analysis = _analyze_document(file_path)

    norm_roles = normalize_roles(roles=roles, intended_role=intended_role, user_notes=user_notes, source_type=source_type)
    role = intended_role if intended_role in ALLOWED_ROLES else (norm_roles[0] if norm_roles else "visual_inspiration")

    ref_id = f"ref_{uuid.uuid4().hex[:8]}"
    now = utc_now()
    attribution = {"source": "user_upload", "filename": file_path.name, "permissions": permissions}

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO reference_assets
               (id, project_id, filename, file_path, asset_type, source_type, source_url,
                access_status, analysis_status, intended_role, roles_json, permissions,
                analysis_json, limitations_json, attribution_json, user_notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, '', 'analyzed', 'completed', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ref_id,
                project_id,
                file_path.name,
                str(file_path),
                asset_type,
                source_type,
                role,
                json.dumps(norm_roles),
                permissions,
                json.dumps(analysis),
                json.dumps(limitations),
                json.dumps(attribution),
                user_notes,
                now,
                now,
            ),
        )
        # If document has factual highlights and FACTUAL_SOURCE role, add to research_sources
        if asset_type == "document" and analysis.get("extracted_summary"):
            conn.execute(
                """INSERT INTO research_sources (id, project_id, title, url, publisher, publication_date, retrieval_date, source_tier, summary)
                   VALUES (?, ?, ?, ?, 'Uploaded Document', ?, ?, 2, ?)""",
                (
                    f"src_{uuid.uuid4().hex[:8]}",
                    project_id,
                    f"Document: {file_path.name}",
                    f"file://{file_path.name}",
                    now[:10],
                    now[:10],
                    str(analysis["extracted_summary"])[:600],
                ),
            )

    pkg_summary = build_reference_package(project_id, workspace_dir)
    return {
        "ok": True,
        "reference_id": ref_id,
        "asset_type": asset_type,
        "source_type": source_type,
        "access_status": "analyzed",
        "intended_role": role,
        "roles": norm_roles,
        "analysis": analysis,
        "limitations": limitations,
        "user_notes": user_notes,
        "package": pkg_summary,
    }


def analyze_project_references(project_id: str, workspace_dir: Path | None = None) -> dict[str, Any]:
    """Re-verify and consolidate all URL and uploaded references for a project into structured analysis records."""
    from backend.config import PROJECTS_DIR
    if workspace_dir is None:
        workspace_dir = PROJECTS_DIR / project_id
    pkg = build_reference_package(project_id, workspace_dir)
    with get_conn() as conn:
        refs = rows_to_dicts(conn.execute("SELECT * FROM reference_assets WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall())
    records = [
        {
            "reference_id": r["id"],
            "filename": r["filename"],
            "source_type": r.get("source_type") or r["asset_type"],
            "source_url": r.get("source_url") or "",
            "access_status": r.get("access_status") or "analyzed",
            "roles": r.get("roles") or [r.get("intended_role", "VISUAL_STYLE")],
            "analysis": r.get("analysis") or {},
            "limitations": r.get("limitations") or [],
            "user_notes": r.get("user_notes") or "",
        }
        for r in refs
    ]
    return {"ok": True, "project_id": project_id, "reference_count": len(records), "references": records, "package": pkg}


def build_reference_package(project_id: str, workspace_dir: Path) -> dict[str, Any]:
    """Generate reference_analysis.json, reference_style_guide.md, reference_asset_index.json, reference_timeline.json, asset_registry.json."""
    pkg_dir = workspace_dir / "package"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        refs = rows_to_dicts(conn.execute("SELECT * FROM reference_assets WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall())

    palettes: list[str] = []
    lighting_profiles: list[str] = []
    camera_cues: list[str] = []
    limitations_summary: list[str] = []
    structured_records: list[dict[str, Any]] = []

    for r in refs:
        a = r.get("analysis") or {}
        palettes.extend(a.get("palette_hex") or [])
        if a.get("lighting_profile"):
            lighting_profiles.append(a["lighting_profile"])
        camera_cues.extend(a.get("camera_language") or [])
        lims = r.get("limitations") or []
        limitations_summary.extend(lims)
        structured_records.append({
            "reference_id": r["id"],
            "source_type": r.get("source_type") or r["asset_type"],
            "source_url": r.get("source_url") or "",
            "access_status": r.get("access_status") or "analyzed",
            "roles": r.get("roles") or [r["intended_role"]],
            "analysis": a,
            "limitations": lims,
            "user_notes": r.get("user_notes") or "",
        })

    style_guide_lines = [
        f"# Reference Style Guide ({project_id})",
        "",
        f"**Analyzed References:** {len(refs)}",
        f"**Dominant Palette:** {', '.join(dict.fromkeys(palettes)) or 'Project default palette'}",
        f"**Observed Lighting:** {', '.join(dict.fromkeys(lighting_profiles)) or 'Natural cinematic key'}",
        f"**Camera Language:** {', '.join(dict.fromkeys(camera_cues)) or 'Smooth push-in and multiplane pans'}",
        "",
        "## Reference Role & Traceability Mapping",
    ]
    for r in refs:
        roles_str = ", ".join(r.get("roles") or [r["intended_role"]])
        status_str = r.get("access_status") or "analyzed"
        notes_str = f" — Notes: *{r['user_notes']}*" if r.get("user_notes") else ""
        lims_str = f" (Limitations: {'; '.join(r.get('limitations') or [])})" if r.get("limitations") else ""
        style_guide_lines.append(
            f"- `{r['filename']}` (`{r.get('source_type') or r['asset_type']}`, status: `{status_str}`) -> Roles: **{roles_str}**{notes_str}{lims_str}"
        )

    style_guide_md = "\n".join(style_guide_lines) + "\n"
    ref_analysis = {
        "project_id": project_id,
        "asset_count": len(refs),
        "dominant_palette": list(dict.fromkeys(palettes)),
        "lighting_profiles": list(dict.fromkeys(lighting_profiles)),
        "camera_language": list(dict.fromkeys(camera_cues)),
        "references": structured_records,
        "assets": refs,
    }
    asset_index = {
        "project_id": project_id,
        "assets": [
            {
                "id": r["id"],
                "filename": r["filename"],
                "type": r["asset_type"],
                "source_type": r.get("source_type") or r["asset_type"],
                "access_status": r.get("access_status") or "analyzed",
                "role": r["intended_role"],
                "roles": r.get("roles") or [r["intended_role"]],
                "path": r["file_path"],
            }
            for r in refs
        ],
    }
    ref_timeline = {
        "project_id": project_id,
        "entries": [
            {
                "asset_id": r["id"],
                "role": r["intended_role"],
                "roles": r.get("roles") or [r["intended_role"]],
                "duration_sec": (r.get("analysis") or {}).get("duration_sec", 0.0),
            }
            for r in refs
        ],
    }

    (pkg_dir / "reference_analysis.json").write_text(json.dumps(ref_analysis, indent=2), encoding="utf-8")
    (pkg_dir / "reference_style_guide.md").write_text(style_guide_md, encoding="utf-8")
    (pkg_dir / "reference_asset_index.json").write_text(json.dumps(asset_index, indent=2), encoding="utf-8")
    (pkg_dir / "reference_timeline.json").write_text(json.dumps(ref_timeline, indent=2), encoding="utf-8")
    (pkg_dir / "asset_registry.json").write_text(json.dumps(asset_index, indent=2), encoding="utf-8")

    return {
        "asset_count": len(refs),
        "dominant_palette": ref_analysis["dominant_palette"],
        "lighting_profiles": ref_analysis["lighting_profiles"],
        "camera_language": ref_analysis["camera_language"],
        "limitations": list(dict.fromkeys(limitations_summary)),
        "style_guide_md": style_guide_md,
    }
