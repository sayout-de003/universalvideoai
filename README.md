# universalvideoai

Universal AI Video Production Studio — guided creative intake, research & fact-checking, 25-format professional screenwriting, 28-artifact versioned production package, approval gates, multi-engine rendering, audio studio, QA, and Antigravity native plugin/MCP integration.

## Quick Setup (Antigravity or Local)

```bash
chmod +x scripts/install.sh scripts/run_studio.sh
./scripts/install.sh
```

## Launch Desktop Studio UI

```bash
./scripts/run_studio.sh
```

## Produce a Video via CLI

```bash
PYTHONPATH=. .venv/bin/python -m backend.cli produce "Create a 30-second documentary about solar energy" --bundle
```
