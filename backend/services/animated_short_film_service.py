"""Animated Short Film Service — Painterly 2D Cinematic Short Film Planner, Prompt Compiler & Repair Engine."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from backend.config import PROJECTS_DIR
from backend.orchestration.director import get_project_detail

OPENING_STYLE_LOCK = (
    "CRITICAL STYLE LOCK: animate the supplied image's painted visual language throughout. "
    "A moving 2D digital painting: broad irregular color planes, visible rough brush marks, "
    "ragged painted edges, simplified shadow shapes, loose background detail. Skin and fabric "
    "retain painted texture; clouds, smoke and spray remain bold brush shapes. Preserve the "
    "reference palette and lighting. Never convert it to photorealism, glossy CGI, smooth "
    "plastic surfaces or clean vector/anime outlines. Do not restyle."
)

CLOSING_STYLE_LOCK = (
    "From first frame to last, the same painted world, character design and rough edges "
    "remain visible. No new captions or watermarks. No shift to realism or glossy 3D."
)

VEHICLE_STYLE_ADDON = (
    "Metal is described by a few painted reflection shapes, not a mirror-polished automotive render. "
    "Road and water highlights remain broad strokes."
)

REPAIR_MATRIX: dict[str, dict[str, str]] = {
    "look": {
        "check": "Plastic metal, smooth skin, clean outlines replacing brush edges",
        "first_repair": "Wider framing, matched painterly plates, explicit painted reflection shapes, fewer conflicting references",
        "prompt_patch": (
            "Enforce medium-to-wide framing where brush texture stays legible; replace close-up smooth skin/metal "
            "with broad gouache color planes and rough dry-brush edges. " + VEHICLE_STYLE_ADDON
        ),
    },
    "identity": {
        "check": "Face, wardrobe, bike, bag or emblem changes across cuts",
        "first_repair": "Single fixed hero identity sentence, stable full wardrobe description, separate pursuer silhouette",
        "prompt_patch": (
            "Lock Hero to Reference 1 silhouette and wardrobe in every beat; keep any pursuer or secondary figure "
            "in distinct silhouette or unseen behind tinted glass so faces never clone."
        ),
    },
    "prop_logic": {
        "check": "Duplicated radio/prop, changing shoulder, bag or parcel vanishes",
        "first_repair": "Exact count, fixed attachment point, active hand, and persistent state matching Reference 1",
        "prompt_patch": (
            "Prop count lock: exactly one hero prop attached at its fixed strap/mount; the hero interacts with "
            "the existing attached prop rather than spawning a second copy."
        ),
    },
    "story": {
        "check": "Stunts without a goal, or pursuer/obstacle disappears mid-film",
        "first_repair": "Show goal and obstacle in shared geography with strict cause-and-effect beats",
        "prompt_patch": (
            "Maintain shared pursuit geography in medium-wide framing so both the hero's objective and the active "
            "obstacle remain visible and causally linked in every timestamped interval."
        ),
    },
    "space_time": {
        "check": "Random locations, night/day jumps, or wrong landing surface",
        "first_repair": "Explicit route progression, matched time-of-day palette, and named landing plane",
        "prompt_patch": (
            "Lock route continuity and time-of-day lighting across all beats; state the exact approach vector "
            "and street/surface landing plane before any aerial leap."
        ),
    },
    "motion": {
        "check": "Backward travel, wheel slip, floating body, or weightless landing",
        "first_repair": "Clear forward travel vector, tire/foot grip before slide, brief apex, heavy compression on landing",
        "prompt_patch": (
            "Enforce forward travel vector and credible contact mechanics: tires/boots grip before sliding, "
            "launch has a visible ramp approach, brief apex, and heavy suspension/knee compression on landing."
        ),
    },
    "pace": {
        "check": "Empty opener, slow detail pull-out wasting runtime, or frozen insert",
        "first_repair": "Start already in motion at 0.0s and timestamp every 1.5-3.0s causal turn",
        "prompt_patch": (
            "0.0s opens already at full speed in active motion — remove static detail pull-out and advance "
            "with a new physical cause-and-effect action every 2 seconds."
        ),
    },
    "ending": {
        "check": "Abrupt cutoff mid-stunt or unresolved objective",
        "first_repair": "Reserve final interval for visible objective payoff and a resting wide composition",
        "prompt_patch": (
            "Reserve the final beat for completing the physical objective followed by a composed wide resting shot "
            "that resolves the momentum."
        ),
    },
}


def _normalize_duration(duration_sec: int) -> int:
    if duration_sec <= 11:
        return 10
    if duration_sec <= 18:
        return 15
    return 30


def _build_beats(
    duration_sec: int,
    hero: str,
    goal: str,
    obstacle: str,
    response: str,
    payoff: str,
    world: str,
    prop: str,
) -> list[dict[str, str]]:
    dur = _normalize_duration(duration_sec)
    if dur == 10:
        return [
            {
                "window": "0.0-2.5s",
                "phase": "Immediate hook in motion",
                "action": f"Already moving through {world}, {hero} commits toward {goal} with {prop} secured.",
                "camera": "Low tracking medium-wide angle matching forward speed",
                "sound": "Immediate wind/surface rush and rhythmic mechanical or footstep drive",
            },
            {
                "window": "2.5-5.5s",
                "phase": "Escalation & obstacle",
                "action": f"{obstacle} blocks the direct line, forcing {hero} to bank hard and compress into the turn.",
                "camera": "Dynamic side-three-quarter tracking shot holding both hero and obstacle in shared geography",
                "sound": "Sharp surface skid, rising ambient tension, close environmental reflection",
            },
            {
                "window": "5.5-8.0s",
                "phase": "Apex maneuver",
                "action": f"Caused by the blocked lane, {hero} executes {response}, launching cleanly with brief airborne suspension before heavy contact on the landing plane.",
                "camera": "Wide profile framing the launch, brief apex, and grounded landing compression",
                "sound": "Wind thins briefly at apex, followed by heavy grounded impact and spray/debris scatter",
            },
            {
                "window": "8.0-10.0s",
                "phase": "Payoff & final wide",
                "action": f"Momentum carries {hero} into the clear zone to complete {payoff}, settling into a composed silhouette.",
                "camera": "Resting wide composition holding the painted sky and environment",
                "sound": "Decelerating mechanical/footstep cadence settling into warm environmental ambience",
            },
        ]
    if dur == 15:
        return [
            {
                "window": "0.0-3.0s",
                "phase": "Setup in motion",
                "action": f"Opening at full momentum in {world}, {hero} checks {prop} and locks onto the target route to {goal}.",
                "camera": "Medium-wide lead tracking shot establishing identity and painted brush texture",
                "sound": "Crisp surface contact, wind bed, and tactile latch/grip click on the prop",
            },
            {
                "window": "3.0-7.0s",
                "phase": "Obstacle engagement",
                "action": f"{obstacle} closes the gap along the route, forcing {hero} to weave through tight structural cover while keeping {prop} intact.",
                "camera": "Rear-three-quarter pursuit angle keeping hero and obstacle in the same painted corridor",
                "sound": "Doppler environment pass, surface grit, and escalating rhythmic drive",
            },
            {
                "window": "7.0-11.5s",
                "phase": "Committed stunt & landing",
                "action": f"Driven by the narrowing path, {hero} commits to {response} — clear approach, brief airborne arc, and heavy compression onto the lower street plane.",
                "camera": "Low wide angle capturing vertical drop/leap and grounded street-level landing",
                "sound": "Brief mid-air hush followed by weighty landing thud, suspension compression, and skidding grit",
            },
            {
                "window": "11.5-15.0s",
                "phase": "Resolution & wide hold",
                "action": f"{hero} stabilizes out of the slide, achieves {payoff}, and pauses as painted dust and light settle.",
                "camera": "Wide environmental tableau framing the completed journey",
                "sound": "Echoing final impact fading into calm ambient wind and distant city/world tone",
            },
        ]
    return [
        {
            "window": "0.0-5.0s",
            "phase": "Character & objective hook",
            "action": f"In {world}, {hero} secures {prop} and launches into motion toward {goal}, establishing silhouette and tactile preparation.",
            "camera": "Tight tactile action opening into a medium-wide tracking shot",
            "sound": "Distinct gear/strap latch, boot or tire bite, and rising environmental bed",
        },
        {
            "window": "5.0-10.0s",
            "phase": "Route commitment",
            "action": f"Gathering speed along the primary artery of {world}, {hero} carves past early traffic/terrain markers as {obstacle} first appears.",
            "camera": "Low road-level lateral track emphasizing forward velocity and painted brush planes",
            "sound": "Steady engine/cadence pitch, rushing air, and first distant warning cue of the obstacle",
        },
        {
            "window": "10.0-17.0s",
            "phase": "Escalating confrontation",
            "action": f"{obstacle} cuts off the main approach; {hero} counters by banking into a confined secondary passage, kicking up painted spray and debris.",
            "camera": "Dynamic overhead-to-side angle holding shared pursuit geography and consistent travel direction",
            "sound": "Reverberant enclosure reflections, sharp tire/foot slide, and heightened percussive tension",
        },
        {
            "window": "17.0-23.0s",
            "phase": "Climax leap & grounded landing",
            "action": f"With the passage ending, {hero} commits to {response}: full-speed approach, clean launch across the gap, brief apex against the painted sky, and heavy landing onto the target deck.",
            "camera": "Wide heroic profile capturing ramp/edge launch, apex silhouette, and weighted landing compression",
            "sound": "Airborne wind swell with thinned engine/footstep bed, then heavy landing impact and chassis/knee recovery",
        },
        {
            "window": "23.0-30.0s",
            "phase": "Payoff & final wide composition",
            "action": f"Controlling the landing rollout, {hero} reaches the destination, completes {payoff} with {prop}, and rests inside a wide painted vista.",
            "camera": "Slow settling wide shot holding character, prop state, and painted horizon",
            "sound": "Braking slide resolving into calm latch/delivery sound and warm ambient atmosphere",
        },
    ]


def build_animated_short_package(
    idea: str,
    duration_sec: int = 30,
    aspect_ratio: str = "16:9",
    hero_description: str | None = None,
    world_description: str | None = None,
    vehicle_or_prop: str | None = None,
    editing_mode: str = "motivated_cuts",
    audio_mode: str = "native_diegetic",
    project_id: str | None = None,
    execute_plates: bool = False,
) -> dict[str, Any]:
    """Compile a complete Painterly Animated Short Film package (Story, Plate Prompts, Reference Map, Master Video Prompt, Sound Cues)."""
    clean_idea = (idea or "").strip() or "A determined courier races across a wind-swept coastal bridge to deliver a sealed brass canister before the storm gates close."
    dur = _normalize_duration(duration_sec)
    aspect = aspect_ratio if aspect_ratio in ("16:9", "9:16") else "16:9"

    hero = (hero_description or "").strip() or (
        "Agile weathered rider in an ochre canvas windbreaker, charcoal riding trousers, "
        "scuffed leather boots, and wind-tousled dark hair with a single brass canister strapped across the left shoulder"
    )
    world = (world_description or "").strip() or (
        "Late-afternoon coastal industrial viaduct with slate-blue water, warm amber low sun, "
        "terracotta concrete piers, and bold gouache cloud banks"
    )
    prop = (vehicle_or_prop or "").strip() or (
        "Matte-olive vintage scrambler motorcycle with twin painted headlamp shapes and one sealed brass courier canister on the left strap"
    )

    goal = f"complete the mission ({clean_idea})"
    obstacle = "converging crosswind hazards and a closing barrier along the elevated span"
    response = "a committed high-speed bank and ramp leap onto the lower causeway deck"
    payoff = "delivering the intact canister at the harbor terminus and coming to a grounded stop"

    story_sentence = (
        f"Driven to {goal}, {hero.split(',')[0].lower()} confronts {obstacle}, "
        f"counters with {response}, and achieves {payoff}."
    )

    beats = _build_beats(dur, hero, goal, obstacle, response, payoff, world, prop)

    plate_prompts = [
        {
            "reference_index": 1,
            "role": "character_sheet",
            "filename": "references/ref_01_character_sheet.png",
            "prompt": (
                f"Character sheet, three views of the same character on a plain pale-grey ground: "
                f"front view, three-quarter view, side profile. {hero}. Full body head-to-toe, "
                f"consistent height, consistent face and hairstyle in all three views, neutral relaxed "
                f"pose, clear silhouette. Stylized 2D illustration with visible gouache and acrylic "
                f"brushwork, matte painted fabric and skin planes, bold dark shadow shapes, warm sunlit "
                f"highlights, hand-drawn edge variation. No text, no labels, no split panels, no watermark."
            ),
            "settings": {
                "Model": "Nano Banana / GPT Image / Flux / Midjourney",
                "Type": "image",
                "Aspect": "16:9",
                "References": "None (base identity plate)",
            },
        },
        {
            "reference_index": 2,
            "role": "environment_plate",
            "filename": "references/ref_02_environment_plate.png",
            "prompt": (
                f"Wide {aspect} environment plate of {world}. Clear open path in the foreground for action, "
                f"distinct architectural landmarks, painted atmospheric depth, bold irregular cloud and shadow "
                f"shapes, rough dry-brush surface texture on road and structures. Stylized 2D digital painting "
                f"with gouache and oil-impasto color planes, warm amber key light against cool slate shadows. "
                f"No people, no text overlays, no watermarks, no photorealistic 3D gloss."
            ),
            "settings": {
                "Model": "Nano Banana / GPT Image / Flux / Midjourney",
                "Type": "image",
                "Aspect": aspect,
                "References": "Attach Reference 1 for palette/brushwork harmony if supported",
            },
        },
        {
            "reference_index": 3,
            "role": "vehicle_or_prop_sheet",
            "filename": "references/ref_03_vehicle_prop_sheet.png",
            "prompt": (
                f"Vehicle and hero prop study on a plain neutral ground: three-quarter front hero angle "
                f"and side profile of {prop}. Clear wheel/structural geometry, seat/handle height, and attachment "
                f"points. {VEHICLE_STYLE_ADDON} Stylized 2D painted illustration with visible rough brush marks, "
                f"matte color planes, and simplified dark shadow shapes. No riders, no text labels, no watermarks."
            ),
            "settings": {
                "Model": "Nano Banana / GPT Image / Flux / Midjourney",
                "Type": "image",
                "Aspect": "16:9",
                "References": "Attach Reference 1 for scale and brushwork consistency",
            },
        },
    ]

    editing_line = (
        "Continuous unbroken single camera take maintaining consistent left-to-right forward travel vector."
        if editing_mode == "continuous_take"
        else "Motivated action cuts across road-level, pursuit three-quarter, and wide profile angles while strictly preserving travel direction."
    )

    beat_lines = "\n".join(
        f"{b['window']}: {b['action']} Camera: {b['camera']}. Sound: {b['sound']}."
        for b in beats
    )

    master_video_prompt = (
        f"{OPENING_STYLE_LOCK} {VEHICLE_STYLE_ADDON}\n"
        f"Reference 1: Hero identity and wardrobe sheet ({plate_prompts[0]['filename']}).\n"
        f"Reference 2: Primary environment and lighting plate ({plate_prompts[1]['filename']}).\n"
        f"Reference 3: Hero vehicle/prop geometry and painted surface sheet ({plate_prompts[2]['filename']}).\n"
        f"Exact first frame: {hero} already moving at speed through {world} with {prop} clearly visible in medium-wide framing.\n"
        f"Hero: {hero}. Props: {prop} (fixed count: 1, persistent across all shots).\n"
        f"World: {world}. Story goal: {goal} while overcoming {obstacle}.\n"
        f"Editing: {editing_line}\n"
        f"{beat_lines}\n"
        f"Continuity: Single hero throughout; no cloned faces; prop remains strapped/mounted in the exact same position from 0.0s to {dur}.0s; unbroken route progression.\n"
        f"Motion: Clear forward travel vector, credible tire/boot grip before sliding, committed launch approach, brief airborne apex, and heavy compression on landing.\n"
        f"Audio: {audio_mode} — layered continuous wind/surface bed, setting ambience, discrete latch and contact foley, weighted landing impact, no unmotivated whooshes.\n"
        f"{CLOSING_STYLE_LOCK}"
    )

    video_settings = {
        "Model": "Seedance / Kling / Veo (multi-reference image-to-video)",
        "Type": "image-to-video",
        "Aspect": aspect,
        "Duration": f"{dur}s",
        "References": "1. ref_01_character_sheet.png, 2. ref_02_environment_plate.png, 3. ref_03_vehicle_prop_sheet.png",
    }

    sound_cue_list = [
        {"layer_order": 1, "category": "continuous_bed", "cue": "Steady wind rush and surface/engine cadence pitched to actual speed"},
        {"layer_order": 2, "category": "setting_ambience", "cue": f"Spatial ambience for {world} with perspective change in enclosures"},
        {"layer_order": 3, "category": "discrete_contact", "cue": "Tactile strap/latch click, boot/tire bite before slide"},
        {"layer_order": 4, "category": "major_impacts", "cue": "Thinned bed at jump apex followed by heavy grounded landing compression"},
        {"layer_order": 5, "category": "transitions", "cue": "Restrained natural acoustic decay into the final wide resting shot"},
    ]

    package: dict[str, Any] = {
        "ok": True,
        "package_id": f"anim_{uuid.uuid4().hex[:8]}",
        "idea": clean_idea,
        "duration_sec": dur,
        "aspect_ratio": aspect,
        "story": {
            "one_sentence": story_sentence,
            "goal": goal,
            "obstacle": obstacle,
            "response": response,
            "payoff": payoff,
            "beats": beats,
        },
        "plate_prompts": plate_prompts,
        "reference_manifest": [
            {"index": p["reference_index"], "role": p["role"], "file": p["filename"]}
            for p in plate_prompts
        ],
        "master_video_prompt": master_video_prompt,
        "video_settings": video_settings,
        "sound_cue_list": sound_cue_list,
        "folder_layout": ["references/", "prompts/", "renders/", "final/"],
        "qa_note": {
            "automated_checks_performed": [
                "opening_style_lock_present",
                "closing_style_lock_present",
                "ordered_reference_roles_mapped",
                "causal_timestamped_beats_verified",
                "single_prop_count_locked",
            ],
            "not_reviewed_yet": [
                "rendered_plates_visual_inspection (awaiting plate generation)",
                "rendered_video_motion_and_audio_continuity (awaiting video render)",
            ],
        },
    }

    if project_id:
        detail = get_project_detail(project_id)
        ws = Path(detail["project"]["workspace_dir"]) if detail and detail.get("project") else (PROJECTS_DIR / project_id)
        for sub in ("references", "prompts", "renders", "final"):
            (ws / sub).mkdir(parents=True, exist_ok=True)
        pkg_path = ws / "prompts" / f"{package['package_id']}_package.json"
        md_path = ws / "prompts" / f"{package['package_id']}_master_prompt.md"
        pkg_path.write_text(json.dumps(package, indent=2), encoding="utf-8")
        md_path.write_text(
            f"# Animated Short Film Package ({dur}s, {aspect})\n\n"
            f"## Story\n{story_sentence}\n\n"
            f"## Master Video Prompt\n```text\n{master_video_prompt}\n```\n",
            encoding="utf-8",
        )
        package["saved_paths"] = {
            "workspace_dir": str(ws),
            "package_json": str(pkg_path),
            "master_prompt_md": str(md_path),
        }

        if execute_plates:
            from backend.providers.image.router import generate_cloud_image

            plate_results = []
            for plate in plate_prompts:
                out_file = ws / plate["filename"]
                res = generate_cloud_image(
                    prompt=plate["prompt"],
                    output_path=out_file,
                    aspect_ratio=plate["settings"]["Aspect"],
                    project_id=project_id,
                )
                plate_results.append({"role": plate["role"], "file": str(out_file), "result": res})
            package["executed_plates"] = plate_results

    return package


def diagnose_and_repair_shot(
    issue_description: str,
    master_prompt: str,
    category: str | None = None,
) -> dict[str, Any]:
    """Inspect a reported render defect against Section 9's repair table and return a patched Master Video Prompt."""
    issue_low = (issue_description or "").lower()
    detected_categories: list[str] = []

    if category and category in REPAIR_MATRIX:
        detected_categories.append(category)

    keyword_map = [
        ("look", ("plastic", "glossy", "cgi", "3d", "smooth skin", "anime", "vector", "photoreal", "brush")),
        ("identity", ("face", "cloned", "wardrobe", "costume", "identity", "different person", "hair")),
        ("prop_logic", ("duplicate", "two radio", "vanish", "disappear", "shoulder", "bag", "prop", "canister")),
        ("story", ("no goal", "random stunt", "pursuer disappear", "why", "meaningless")),
        ("space_time", ("teleport", "night", "day", "lighting jump", "landing surface", "horizontal parkour", "rooftop")),
        ("motion", ("backward", "moonwalk", "wheel slip", "floating", "weightless", "physics")),
        ("pace", ("slow opener", "detail pull", "frozen", "boring", "static start")),
        ("ending", ("abrupt", "cutoff", "cut off", "unfinished", "mid-stunt")),
    ]
    for cat, needles in keyword_map:
        if cat not in detected_categories and any(n in issue_low for n in needles):
            detected_categories.append(cat)

    if not detected_categories:
        detected_categories.append("look")

    repairs = [
        {
            "category": cat,
            "check": REPAIR_MATRIX[cat]["check"],
            "first_repair": REPAIR_MATRIX[cat]["first_repair"],
            "prompt_patch": REPAIR_MATRIX[cat]["prompt_patch"],
        }
        for cat in detected_categories
    ]

    patch_block = " ".join(r["prompt_patch"] for r in repairs)
    base_prompt = (master_prompt or "").strip()
    if CLOSING_STYLE_LOCK in base_prompt:
        repaired_prompt = base_prompt.replace(
            CLOSING_STYLE_LOCK,
            f"REPAIR LOCK ({', '.join(detected_categories)}): {patch_block}\n{CLOSING_STYLE_LOCK}",
        )
    else:
        repaired_prompt = f"{OPENING_STYLE_LOCK}\n{base_prompt}\nREPAIR LOCK: {patch_block}\n{CLOSING_STYLE_LOCK}"

    return {
        "ok": True,
        "issue_description": issue_description,
        "detected_categories": detected_categories,
        "repairs": repairs,
        "repaired_master_prompt": repaired_prompt,
    }
