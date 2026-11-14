"""Adapter for OpenMontage (AGPL-3.0) tool registry, pipelines, checkpoints, and Backlot."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from backend.config import OPENMONTAGE_DIR


def _ensure_openmontage_on_path() -> None:
    om_str = str(OPENMONTAGE_DIR)
    if om_str not in sys.path:
        sys.path.insert(0, om_str)


class OpenMontageAdapter:
    """Thin, non-invasive adapter over OpenMontage's tool registry and pipeline loader."""

    def __init__(self) -> None:
        self._discovered = False
        self._registry = None

    def _init_registry(self) -> Any:
        _ensure_openmontage_on_path()
        from tools.tool_registry import registry  # type: ignore

        if not self._discovered:
            registry.ensure_discovered("tools")
            self._discovered = True
        self._registry = registry
        return registry

    def is_available(self) -> bool:
        return (OPENMONTAGE_DIR / "tools" / "tool_registry.py").exists()

    def list_pipelines(self) -> list[dict[str, Any]]:
        _ensure_openmontage_on_path()
        from lib.pipeline_loader import list_pipelines, load_pipeline  # type: ignore

        names = list_pipelines()
        results = []
        for name in names:
            try:
                p = load_pipeline(name)
                results.append(
                    {
                        "name": name,
                        "display_name": p.get("display_name", name),
                        "description": p.get("description", ""),
                        "stages": [s.get("name") for s in p.get("stages", [])],
                    }
                )
            except Exception as exc:
                results.append({"name": name, "error": str(exc)})
        return results

    def discover_tools(self) -> dict[str, Any]:
        registry = self._init_registry()
        tools = []
        for name in registry.list_all():
            tool = registry.get(name)
            if tool is None:
                continue
            category = getattr(tool, "capability", "other")
            requires_env = list(getattr(tool, "requires_env", []) or [])
            configured = all(bool(os.environ.get(k, "").strip()) for k in requires_env)
            tools.append(
                {
                    "name": name,
                    "category": str(category),
                    "description": getattr(tool, "description", ""),
                    "requires_env": requires_env,
                    "configured": configured,
                }
            )

        summary = {}
        if hasattr(registry, "provider_menu_summary"):
            try:
                summary = registry.provider_menu_summary()
            except Exception:
                summary = {}

        return {
            "total_tools": len(tools),
            "configured_tools": sum(1 for t in tools if t["configured"]),
            "tools": tools,
            "provider_menu_summary": summary,
        }

    def execute_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        registry = self._init_registry()
        tool = registry.get(tool_name)
        if tool is None:
            return {"success": False, "error": f"OpenMontage tool '{tool_name}' not found"}
        try:
            result = tool.execute(params)
            return {
                "success": bool(getattr(result, "success", True)),
                "artifacts": getattr(result, "artifacts", {}),
                "metadata": getattr(result, "metadata", {}),
                "error": getattr(result, "error", None),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def write_openmontage_checkpoint(
        self,
        project_workspace: Path,
        stage: str,
        status: str,
        data: dict[str, Any],
        human_approved: bool = False,
    ) -> Path:
        import json
        from datetime import datetime, timezone

        project_workspace.mkdir(parents=True, exist_ok=True)
        ckpt_path = project_workspace / f"checkpoint_{stage}.json"
        payload = {
            "stage": stage,
            "status": status,
            "human_approved": human_approved,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        ckpt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return ckpt_path


openmontage_adapter = OpenMontageAdapter()
