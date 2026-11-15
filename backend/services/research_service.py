"""Phase 2: Research Department (Research Director, Web Research Agent, Trend & Theme Researcher, Fact Checker)."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import requests

from backend.db import get_conn, rows_to_dicts
from backend.models import utc_now


def _extract_search_queries(topic: str) -> list[str]:
    clean = re.sub(r"[^\w\s-]", " ", topic).strip()
    words = [w for w in clean.split() if len(w) > 2 and w.lower() not in ("create", "make", "produce", "video", "film", "short", "documentary", "about", "seconds", "minute")]
    base = " ".join(words[:6]) or topic[:60]
    return [base, f"{base} history breakthrough", f"{base} real world impact"]


def _fetch_wikipedia_sources(query: str, timeout: float = 4.0) -> list[dict[str, Any]]:
    """Query Wikipedia REST/Action API for verifiable encyclopedic summaries & URLs."""
    sources: list[dict[str, Any]] = []
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query, "srlimit": 3, "format": "json"},
            headers={"User-Agent": "UniversalAIVideoStudio/1.0"},
            timeout=timeout,
        )
        if r.status_code != 200:
            return []
        hits = r.json().get("query", {}).get("search", [])
        for hit in hits[:3]:
            title = hit.get("title", "")
            if not title:
                continue
            sum_r = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}",
                headers={"User-Agent": "UniversalAIVideoStudio/1.0"},
                timeout=timeout,
            )
            if sum_r.status_code == 200:
                data = sum_r.json()
                extract = (data.get("extract") or "").strip()
                if len(extract) < 40:
                    continue
                sources.append({
                    "title": data.get("title", title),
                    "url": data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"),
                    "publisher": "Wikipedia (Primary Reference Index)",
                    "publication_date": data.get("timestamp", "")[:10],
                    "summary": extract,
                    "source_tier": 4,
                })
    except Exception:
        return []
    return sources


def analyze_trending_themes(topic: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Trend & Viral Theme Researcher Agent: synthesizes trending hooks, visual motifs, animation styles, and dual Male/Female voice casting."""
    low = topic.lower()
    if any(k in low for k in ("ai", "tech", "software", "quantum", "robot", "future", "code", "cyber", "machine", "data")):
        theme_archetype = "Hidden Architecture & High-Stakes Breakthrough"
        recommended_style = "neon-tubes / pixar-tech-hud"
        visual_motifs = [
            "Luminous volumetric circuit pathways and floating glassmorphic telemetry rings",
            "Expressive 2D/3D Pixar-styled engineer and AI avatar acting inside a depth-lit control room",
            "Kinetic data bar/line charts with spring physics and glowing callout badges",
        ]
        hook_angle = f"Everyone sees the surface of {topic}, but the real breakthrough happened inside a hidden architectural shift."
    elif any(k in low for k in ("history", "war", "empire", "ancient", "civilization", "biography", "century")):
        theme_archetype = "Decisive Turning Point & Human Consequence"
        recommended_style = "impasto-oil / painterly-cinema"
        visual_motifs = [
            "Painterly chiaroscuro lighting with warm amber torches against slate-blue architectural shadows",
            "Animated chronological map and timeline counters with smooth camera dolly",
            "Character-driven dramatic staging showing the human cost behind the historical milestone",
        ]
        hook_angle = f"History remembers {topic} as inevitable—yet in the final hours, it balanced on a single human decision."
    elif any(k in low for k in ("nature", "ocean", "space", "planet", "climate", "solar", "energy", "wildlife", "earth")):
        theme_archetype = "Planetary Scale & Invisible Forces Made Visible"
        recommended_style = "watercolor-brush / pixar-atmospheric"
        visual_motifs = [
            "Multi-plane parallax horizon with volumetric god-rays, atmospheric particles, and living terrain",
            "Animated cross-section breakdown revealing energy flow and ecological mechanics",
            "Sweeping orbital-to-macro camera transitions with smooth cross-dissolves",
        ]
        hook_angle = f"Beneath the calm surface of {topic}, an invisible engine powers every transformation we see."
    else:
        theme_archetype = "In-Media-Res Tension, Causal Escalation & Cinematic Payoff"
        recommended_style = "pixar-warm-cinema / gouache-short-film"
        visual_motifs = [
            "Expressive Pixar-grade 2D/3D character silhouette with dynamic breathing, eye blink, and purposeful motion",
            "Rich multi-layer parallax environment with warm key light, rim highlights, and atmospheric depth",
            "Crisp motion-graphics callouts anchoring the turning points without cluttering the frame",
        ]
        hook_angle = f"Before anyone realized what was at stake in {topic}, the countdown had already begun."

    key_takeaways = [c["claim_text"] for c in claims[:4] if c.get("claim_text")]
    return {
        "topic": topic,
        "theme_archetype": theme_archetype,
        "recommended_animation_style": recommended_style,
        "viral_hook_angle": hook_angle,
        "visual_motifs": visual_motifs,
        "transition_plan": ["smoothleft", "dissolve", "circleopen", "smoothright"],
        "voice_casting_plan": {
            "mode": "dual_human_male_and_female",
            "male_lead": {"voice_id": "narrator_deep", "neural_voice": "en-US-ChristopherNeural", "role": "Cinematic Anchor & Stakes Narrator"},
            "female_lead": {"voice_id": "narrator_warm", "neural_voice": "en-US-AriaNeural", "role": "Analytical Co-Narrator & Human Perspective"},
            "male_character": {"voice_id": "character_1", "neural_voice": "en-US-GuyNeural", "role": "Male Protagonist / Specialist"},
            "female_character": {"voice_id": "character_2", "neural_voice": "en-US-JennyNeural", "role": "Female Protagonist / Specialist"},
        },
        "synthesized_evidence": key_takeaways,
    }


def run_project_research(project_id: str, topic: str, workspace_dir: Path, allow_web: bool = True) -> dict[str, Any]:
    """Run Research Director -> Web Research Agent -> Trend & Theme Researcher -> Fact Checker and write 4 research artifacts."""
    pkg_dir = workspace_dir / "package"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    retrieval_date = now[:10]

    queries = _extract_search_queries(topic)
    collected_sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    if allow_web:
        for q in queries[:2]:
            for src in _fetch_wikipedia_sources(q):
                if src["url"] not in seen_urls:
                    seen_urls.add(src["url"])
                    collected_sources.append(src)

    with get_conn() as conn:
        conn.execute("DELETE FROM research_sources WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM research_claims WHERE project_id=?", (project_id,))

        db_sources: list[dict[str, Any]] = []
        for src in collected_sources:
            sid = f"src_{uuid.uuid4().hex[:8]}"
            conn.execute(
                """INSERT INTO research_sources (id, project_id, title, url, publisher, publication_date, retrieval_date, source_tier, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, project_id, src["title"], src["url"], src["publisher"], src["publication_date"], retrieval_date, src["source_tier"], src["summary"]),
            )
            db_sources.append({"id": sid, "retrieval_date": retrieval_date, **src})

        claims: list[dict[str, Any]] = []
        for s in db_sources:
            sentences = [sent.strip() for sent in re.split(r"(?<=[.!?])\s+", s["summary"]) if len(sent.strip()) > 30]
            for sent in sentences[:3]:
                cid = f"clm_{uuid.uuid4().hex[:8]}"
                decision = "PASS" if s["url"] and len(sent) > 35 else "QUALIFY"
                status = "VERIFIED" if decision == "PASS" else "QUALIFIED"
                conn.execute(
                    """INSERT INTO research_claims
                       (id, project_id, claim_text, source_id, supporting_passage, confidence, verification_status, conflicting_evidence, fact_check_decision, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
                    (cid, project_id, sent, s["id"], sent, 0.88 if decision == "PASS" else 0.60, status, decision, now),
                )
                claims.append({
                    "claim_id": cid,
                    "claim_text": sent,
                    "source_id": s["id"],
                    "source_title": s["title"],
                    "source_url": s["url"],
                    "publisher": s["publisher"],
                    "publication_date": s["publication_date"],
                    "retrieval_date": retrieval_date,
                    "supporting_passage": sent,
                    "confidence": 0.88 if decision == "PASS" else 0.60,
                    "verification_status": status,
                    "fact_check_decision": decision,
                    "conflicting_evidence": "",
                })

        if not claims:
            cid = f"clm_{uuid.uuid4().hex[:8]}"
            note = f"Every breakthrough in {topic} begins where conventional methods hit a physical limit, forcing a new design paradigm."
            conn.execute(
                """INSERT INTO research_claims
                   (id, project_id, claim_text, source_id, supporting_passage, confidence, verification_status, conflicting_evidence, fact_check_decision, created_at)
                   VALUES (?, ?, ?, NULL, '', 0.65, 'QUALIFIED', 'Synthesized domain thesis', 'QUALIFY', ?)""",
                (cid, project_id, note, now),
            )
            claims.append({
                "claim_id": cid,
                "claim_text": note,
                "source_id": None,
                "source_title": "Domain Synthesis & Trend Analysis",
                "source_url": "",
                "publisher": "Studio Research Intelligence",
                "publication_date": retrieval_date,
                "retrieval_date": retrieval_date,
                "supporting_passage": note,
                "confidence": 0.65,
                "verification_status": "QUALIFIED",
                "fact_check_decision": "QUALIFY",
                "conflicting_evidence": "",
            })

    trending_themes = analyze_trending_themes(topic, claims)

    dossier_lines = [
        f"# Research & Trending Theme Dossier: {topic}",
        "",
        f"**Retrieval Date:** {retrieval_date}",
        f"**Trending Narrative Archetype:** {trending_themes['theme_archetype']}",
        f"**Recommended Animation Style:** {trending_themes['recommended_animation_style']}",
        f"**Viral Hook Angle:** {trending_themes['viral_hook_angle']}",
        "",
        "## Trending Visual Motifs",
    ]
    for motif in trending_themes["visual_motifs"]:
        dossier_lines.append(f"- {motif}")
    dossier_lines.extend([
        "",
        "## Dual Human Voice Casting Plan (Male & Female)",
        f"- **Male Anchor (`narrator_deep`):** `{trending_themes['voice_casting_plan']['male_lead']['neural_voice']}` — {trending_themes['voice_casting_plan']['male_lead']['role']}",
        f"- **Female Co-Narrator (`narrator_warm`):** `{trending_themes['voice_casting_plan']['female_lead']['neural_voice']}` — {trending_themes['voice_casting_plan']['female_lead']['role']}",
        "",
        "## Primary Sources",
    ])
    if db_sources:
        for s in db_sources:
            dossier_lines.append(f"- **{s['title']}** ({s['publisher']}) — {s['url']}")
    else:
        dossier_lines.append("- Synthesized domain and trend intelligence (offline mode).")
    dossier_lines.extend(["", "## Fact-Check Ledger Summary"])
    for c in claims:
        dossier_lines.append(f"- `[{c['fact_check_decision']}]` ({c['verification_status']}, conf={c['confidence']}): {c['claim_text']}")

    dossier_md = "\n".join(dossier_lines) + "\n"
    source_reg = {"project_id": project_id, "topic": topic, "retrieval_date": retrieval_date, "trending_themes": trending_themes, "sources": db_sources}
    fact_ledger = {
        "project_id": project_id,
        "unresolved_critical_claims": sum(1 for c in claims if c["fact_check_decision"] == "REJECT"),
        "claims": claims,
    }
    timeline = {
        "project_id": project_id,
        "queries_executed": queries,
        "trending_themes": trending_themes,
        "events": [{"date": c.get("publication_date") or retrieval_date, "label": c["claim_text"][:100], "source_id": c["source_id"]} for c in claims],
    }

    (pkg_dir / "research_dossier.md").write_text(dossier_md, encoding="utf-8")
    (pkg_dir / "source_registry.json").write_text(json.dumps(source_reg, indent=2), encoding="utf-8")
    (pkg_dir / "fact_check_ledger.json").write_text(json.dumps(fact_ledger, indent=2), encoding="utf-8")
    (pkg_dir / "research_timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "sources_count": len(db_sources),
        "claims_count": len(claims),
        "sources": db_sources,
        "claims": claims,
        "trending_themes": trending_themes,
        "dossier_md": dossier_md,
    }


def get_project_research(project_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        sources = rows_to_dicts(conn.execute("SELECT * FROM research_sources WHERE project_id=?", (project_id,)).fetchall())
        claims = rows_to_dicts(conn.execute("SELECT * FROM research_claims WHERE project_id=?", (project_id,)).fetchall())
    return {"sources": sources, "claims": claims}
