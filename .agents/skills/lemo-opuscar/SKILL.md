---
name: lemo-opuscar
description: Direct and produce a short film made entirely in code, in one of the 99 styles of the Lemo-Opuscar library (e.g. Impasto Oil Painting 油画厚涂, Watercolor Brush 水彩笔刷, Ukiyo-e 浮世绘, Satellite Briefing 卫星简报, Exploded Teardown 产品拆解, Neon Tubes 霓虹灯管, Swiss Motion Graphics 瑞士动态排版). Use when the user asks for a video, film, short, promo, explainer or animation in a named style, when they want a film about their own topic and haven't chosen a style, when they want to customize or create a style, or when they ask which Lemo-Opuscar film styles are available. Integrated with Universal AI Video Studio MCP tools (opuscar_list_styles, opuscar_get_style, opuscar_render_page).
---

# Lemo-Opuscar (Integrated with Universal AI Video Studio & Antigravity)

The 99 film styles, guides (`AGENTS.md`, `DIRECTOR.md`, `TECHNIQUE.md`, `MY-STYLES.md`) and frame-deterministic rendering tools (`core/render/`) live in `integrations/lemo-opuscar` inside the Universal AI Video Studio repository (or `~/lemo-opuscar` when used outside the repository).

## Quick MCP Tools (Inside Universal AI Video Studio)
When connected to the `universal-video-studio` MCP server in Antigravity, you can also call:
- `opuscar_list_styles` — List or filter all 99 Lemo-Opuscar styles by category or keyword.
- `opuscar_get_style` — Load the full `STYLE.md`, `DEMO.md`, `style.json`, and guide paths for any style slug or name.
- `opuscar_render_page` — Render an Opuscar HTML/Canvas/WebGL film folder (`index.html` with `window.READY` and `window.render(t)`) directly to MP4.

## Standard Lemo-Opuscar Workflow

1. **Locate the library.** If `integrations/lemo-opuscar/AGENTS.md` exists in the workspace, set `LIB="$(pwd)/integrations/lemo-opuscar"`. Otherwise run `LEMO_OPUSCAR_HOME="${LEMO_OPUSCAR_HOME:-}" sh "<skill base directory>/scripts/setup.sh"`, which clones/updates the library and prints `LIB=<path>`.
2. **Ensure core tools are installed.** Run `LEMO_OPUSCAR_HOME="$LIB" sh "<skill base directory>/scripts/setup.sh" deps` (in the background if needed). Add `deps voice` or `deps music` later only if the film needs them (`$LIB/TECHNIQUE.md` §1).
3. **Follow the library guides.** Read `$LIB/AGENTS.md`, `$LIB/DIRECTOR.md`, `$LIB/TECHNIQUE.md`, and `$LIB/styles/<slug>/STYLE.md`:
   - Write `TREATMENT.md` in the film's project folder (`projects/<name>/` or `<name>/`) before inspecting demo code.
   - Render style frames with `cd "$LIB" && node core/render/still.mjs "<project_dir>" 1.5 3`.
   - Produce voice, score, animation (`index.html` setting `window.DUR`, `window.READY = true`, `window.render(t)`, `window.TEXTS(t)`), run `node core/render/readcheck.mjs "<project_dir>"`, render video with `node core/render/video.mjs "<project_dir>" --out "<project_dir>/out/video.mp4"`, and mux audio with `sh core/render/mux.sh`.

## Skill Mode Reference

| Item | Rule |
|---|---|
| Project folder | `projects/<name>/` (in studio workspace) or `<name>/` in the current folder |
| Running tools | From `$LIB` with the project's absolute path: `cd "$LIB" && node core/render/still.mjs "<project>" 1.5 3` |
| Library files in pages | Absolute URLs: `/core/lib.js`, `/node_modules/three/…` (served at `/@film/`) |
| Library files in scripts | `$LIB/…`, with `LIB=<path>` at the top of `build.sh` |
| Demo source | Run `LEMO_OPUSCAR_HOME="$LIB" sh "<skill base directory>/scripts/setup.sh" demo <slug>` only after `TREATMENT.md` is written |

Deliver what `$LIB/DIRECTOR.md` §11 lists in the project folder and report the final MP4 path to the user.
