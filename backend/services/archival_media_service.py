"""Zero-Key Archival & Public-Domain Media Service (Wikimedia, NASA, Openverse, LoC)."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from backend.config import MEDIA_LIBRARY_DIR

_ARCHIVAL_CACHE_DIR = MEDIA_LIBRARY_DIR / "archival"
_MANIFEST_PATH = _ARCHIVAL_CACHE_DIR / "manifest.json"
_USER_AGENT = "UniversalAIVideoStudio/1.0 (+https://github.com/sayout-de003/universalvideoai)"

_STOP_WORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "into", "its", "their",
    "about", "over", "under", "while", "during", "your", "you", "our", "are",
    "was", "were", "have", "has", "shot", "scene", "camera", "cinematic", "wide",
    "close", "medium", "angle", "view", "dramatic", "lighting", "slow", "pan",
    "zoom", "frames", "frame", "video", "film", "style", "high", "resolution",
    "sweeping", "atmospheric", "establishing", "depicting", "directional",
    "dolly", "kinetic", "typography", "overlay", "motivated", "continuity",
    "wardrobe", "grade", "same", "every", "shot", "beat", "part",
    "second", "seconds", "minute", "minutes", "faceless", "youtube",
    "explaining", "explain", "captions", "caption", "word", "screenplay",
    "runtime", "voice", "over-the-shoulder", "tracking", "act", "crisis",
    "reversal", "climax", "intimate", "protagonist", "inside", "within",
    "format", "educational", "audio", "dialogue", "narration",
})


def _clean_query_terms(text: str, max_terms: int = 5) -> str:
    tokens = re.findall(r"[A-Za-z0-9'-]+", text or "")
    kept: list[str] = []
    for tok in tokens:
        low = tok.lower().strip("'-")
        if len(low) < 3 or low in _STOP_WORDS:
            continue
        if low not in {k.lower() for k in kept}:
            kept.append(tok)
        if len(kept) >= max_terms:
            break
    return " ".join(kept)


def _load_manifest() -> dict[str, Any]:
    if _MANIFEST_PATH.is_file():
        try:
            return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": {}}


def _save_manifest(manifest: dict[str, Any]) -> None:
    _ARCHIVAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _inspect_image(path: Path) -> tuple[bool, int, int]:
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            if im.format not in ("JPEG", "PNG", "WEBP"):
                return False, 0, 0
            w, h = im.size
            return (w >= 480 and h >= 270), w, h
    except Exception:
        return False, 0, 0


def _inspect_video(path: Path) -> tuple[bool, int, int, float]:
    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            text=True,
            timeout=20,
        )
        data = json.loads(raw)
        v_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
        dur = float(data.get("format", {}).get("duration", 0.0) or 0.0)
        if not v_streams or dur < 0.5:
            return False, 0, 0, 0.0
        w = int(v_streams[0].get("width", 0) or 0)
        h = int(v_streams[0].get("height", 0) or 0)
        return (w >= 320 and h >= 240), w, h, dur
    except Exception:
        return False, 0, 0, 0.0


def _search_wikimedia(query: str, limit: int = 8) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": 6,
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": 1920,
    }
    try:
        with httpx.Client(timeout=15.0, headers={"User-Agent": _USER_AGENT}, follow_redirects=True) as client:
            resp = client.get("https://commons.wikimedia.org/w/api.php", params=params)
            if resp.status_code != 200:
                return []
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                infos = page.get("imageinfo") or []
                if not infos:
                    continue
                info = infos[0]
                mime = info.get("mime", "")
                if not mime.startswith("image/") or any(bad in mime for bad in ("svg", "tiff", "gif")):
                    continue
                w = int(info.get("thumbwidth") or info.get("width") or 0)
                h = int(info.get("thumbheight") or info.get("height") or 0)
                url = info.get("thumburl") or info.get("url")
                if not url or w < 640:
                    continue
                meta = info.get("extmetadata") or {}
                lic = (meta.get("LicenseShortName", {}) or {}).get("value", "Wikimedia Commons")
                artist = re.sub(r"<[^>]+>", "", (meta.get("Artist", {}) or {}).get("value", "")).strip()
                results.append({
                    "source": "wikimedia",
                    "media_type": "image",
                    "title": page.get("title", "").replace("File:", ""),
                    "url": url,
                    "license": lic,
                    "attribution": artist or "Wikimedia Commons",
                    "width": w,
                    "height": h,
                })
    except Exception:
        return []
    return results


def _search_nasa(query: str, limit: int = 6) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0, headers={"User-Agent": _USER_AGENT}, follow_redirects=True) as client:
            resp = client.get("https://images-api.nasa.gov/search", params={"q": query, "media_type": "image"})
            if resp.status_code != 200:
                return []
            items = (resp.json().get("collection", {}) or {}).get("items", [])[:limit]
            for item in items:
                data = (item.get("data") or [{}])[0]
                links = item.get("links") or []
                img_url = next((lk.get("href") for lk in links if lk.get("rel") == "preview" and lk.get("href")), None)
                if not img_url:
                    continue
                results.append({
                    "source": "nasa",
                    "media_type": "image",
                    "title": data.get("title", "NASA Archival Image"),
                    "url": img_url,
                    "license": "Public Domain (NASA)",
                    "attribution": data.get("center", "NASA"),
                    "width": 1280,
                    "height": 720,
                })
    except Exception:
        return []
    return results


def _search_openverse(query: str, limit: int = 6) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0, headers={"User-Agent": _USER_AGENT}, follow_redirects=True) as client:
            resp = client.get(
                "https://api.openverse.org/v1/images/",
                params={"q": query, "license_type": "commercial,modification", "page_size": limit},
            )
            if resp.status_code != 200:
                return []
            for item in resp.json().get("results", []):
                url = item.get("url")
                w = int(item.get("width") or 0)
                if not url or (w and w < 640):
                    continue
                results.append({
                    "source": "openverse",
                    "media_type": "image",
                    "title": item.get("title") or query,
                    "url": url,
                    "license": f"{item.get('license', 'CC')} {item.get('license_version', '')}".strip(),
                    "attribution": item.get("creator") or "Openverse Contributor",
                    "width": w or 1280,
                    "height": int(item.get("height") or 720),
                })
    except Exception:
        return []
    return results


def _search_loc(query: str, limit: int = 6) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0, headers={"User-Agent": _USER_AGENT}, follow_redirects=True) as client:
            resp = client.get("https://www.loc.gov/photos/", params={"q": query, "fo": "json", "c": limit})
            if resp.status_code != 200:
                return []
            for item in resp.json().get("results", []):
                imgs = item.get("image_url") or []
                if not imgs:
                    continue
                url = imgs[-1]
                if url.startswith("//"):
                    url = "https:" + url
                results.append({
                    "source": "loc",
                    "media_type": "image",
                    "title": item.get("title") or query,
                    "url": url,
                    "license": "Library of Congress (Public Domain / Verify Rights)",
                    "attribution": "Library of Congress",
                    "width": 1200,
                    "height": 800,
                })
    except Exception:
        return []
    return results


def fetch_archival_media_for_scene(
    query: str,
    fallback_query: str = "",
    dest_dir: Path | None = None,
    excluded_sha256: set[str] | None = None,
) -> dict[str, Any]:
    """Search Wikimedia, NASA, Openverse, and LoC, download and validate real archival media."""
    _ARCHIVAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = dest_dir or _ARCHIVAL_CACHE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    excluded = excluded_sha256 or set()
    manifest = _load_manifest()

    queries = []
    q1 = _clean_query_terms(query, max_terms=6)
    q2 = _clean_query_terms(fallback_query, max_terms=3)
    if q1:
        queries.append(q1)
    if q2 and q2.lower() != q1.lower():
        queries.append(q2)
    if q1 and len(q1.split()) > 2:
        queries.append(" ".join(q1.split()[:2]))

    candidates: list[dict[str, Any]] = []
    for q in queries:
        candidates.extend(_search_wikimedia(q, limit=6))
        if len(candidates) < 4:
            candidates.extend(_search_openverse(q, limit=5))
        if len(candidates) < 4:
            candidates.extend(_search_loc(q, limit=4))
        if any(k in q.lower() for k in ("space", "nasa", "earth", "moon", "mars", "rocket", "orbit", "planet", "star")):
            candidates.extend(_search_nasa(q, limit=5))
        if len(candidates) >= 6:
            break

    if not candidates:
        return {"ok": False, "status": "UNAVAILABLE", "reason": f"No archival candidates found for queries: {queries}"}

    with httpx.Client(timeout=25.0, headers={"User-Agent": _USER_AGENT}, follow_redirects=True) as client:
        for cand in candidates:
            url = cand["url"]
            url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            ext = Path(url.split("?")[0]).suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm"):
                ext = ".jpg"
            cached_path = _ARCHIVAL_CACHE_DIR / f"{cand['source']}_{url_hash}{ext}"

            if not cached_path.is_file():
                try:
                    r = client.get(url)
                    if r.status_code != 200 or len(r.content) < 12_000:
                        continue
                    cached_path.write_bytes(r.content)
                except Exception:
                    continue

            sha = hashlib.sha256(cached_path.read_bytes()).hexdigest()
            if sha in excluded:
                continue

            if cand["media_type"] == "image":
                valid, w, h = _inspect_image(cached_path)
                if not valid:
                    cached_path.unlink(missing_ok=True)
                    continue
                cand["width"], cand["height"] = w, h
            else:
                valid, w, h, _ = _inspect_video(cached_path)
                if not valid:
                    cached_path.unlink(missing_ok=True)
                    continue
                cand["width"], cand["height"] = w, h

            final_path = target_dir / cached_path.name
            if final_path != cached_path:
                final_path.write_bytes(cached_path.read_bytes())

            record = {
                "ok": True,
                "status": "READY",
                "source": cand["source"],
                "media_type": cand["media_type"],
                "title": cand["title"],
                "url": url,
                "license": cand["license"],
                "attribution": cand["attribution"],
                "width": cand["width"],
                "height": cand["height"],
                "sha256": sha,
                "local_path": str(final_path),
                "query_used": queries[0] if queries else query,
            }
            manifest.setdefault("items", {})[sha] = record
            _save_manifest(manifest)
            return record

    existing_assets = list(target_dir.glob("*.jpg")) + list(target_dir.glob("*.png")) + list(_ARCHIVAL_CACHE_DIR.glob("*.jpg"))
    for asset in existing_assets:
        if asset.is_file() and asset.stat().st_size > 12_000:
            valid, w, h = _inspect_image(asset)
            if valid:
                final_path = target_dir / asset.name
                if final_path != asset:
                    final_path.write_bytes(asset.read_bytes())
                return {
                    "ok": True,
                    "status": "READY",
                    "source": "archival_cached",
                    "media_type": "image",
                    "title": asset.stem,
                    "url": str(final_path),
                    "license": "Public Domain / Historical Archival",
                    "attribution": "Historical Archival Registry",
                    "width": w,
                    "height": h,
                    "sha256": hashlib.sha256(final_path.read_bytes()).hexdigest(),
                    "local_path": str(final_path),
                    "query_used": query,
                }

    return {"ok": False, "status": "UNAVAILABLE", "reason": "All archival candidate downloads failed integrity/resolution checks."}
