"""Stdio MCP Server for Universal AI Video Studio."""

from __future__ import annotations

import json
import sys
from typing import Any

from backend.db import init_db
from backend.models import ProjectCreateRequest
from backend.orchestration.director import create_project, get_project_detail, run_production
from backend.services.format_catalog import FORMAT_CATALOG
from backend.services.intake_service import start_intake, submit_intake_answers
from backend.services.package_service import approve_all_mandatory_gates, list_package_artifacts

TOOLS = [
    {"name": "studio_list_formats", "description": "List all 25 supported video formats and their rules.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "studio_start_intake", "description": "Start guided creative intake (asks video type & duration first).", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "studio_answer_intake", "description": "Submit answers to creative intake questions.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}, "answers": {"type": "object"}}, "required": ["project_id", "answers"]}},
    {"name": "studio_create_project", "description": "Plan a full 28-artifact production package for a video prompt.", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}, "target_duration_sec": {"type": "number"}}, "required": ["prompt"]}},
    {"name": "studio_get_package", "description": "Fetch the 28-artifact production package for a project.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}},
    {"name": "studio_approve_gates", "description": "Approve mandatory screenplay, storyboard, and production plan gates.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}},
    {"name": "studio_produce_video", "description": "Render, mix audio, and QA-verify an approved project.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}, "enforce_approval": {"type": "boolean"}}, "required": ["project_id"]}},
]


def handle_tool_call(name: str, args: dict[str, Any]) -> Any:
    init_db()
    if name == "studio_list_formats":
        return {"formats": list(FORMAT_CATALOG.keys())}
    if name == "studio_start_intake":
        return start_intake(args["prompt"])
    if name == "studio_answer_intake":
        return submit_intake_answers(args["project_id"], args["answers"])
    if name == "studio_create_project":
        return create_project(ProjectCreateRequest(prompt=args["prompt"], target_duration_sec=args.get("target_duration_sec")))
    if name == "studio_get_package":
        return {"detail": get_project_detail(args["project_id"]), "artifacts": list_package_artifacts(args["project_id"])}
    if name == "studio_approve_gates":
        return approve_all_mandatory_gates(args["project_id"])
    if name == "studio_produce_video":
        return run_production(args["project_id"], enforce_approval=bool(args.get("enforce_approval", True)))
    raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
        try:
            if method == "initialize":
                res = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "universal-video-studio", "version": "2.0.0"}}
            elif method == "tools/list":
                res = {"tools": TOOLS}
            elif method == "tools/call":
                out = handle_tool_call(params["name"], params.get("arguments") or {})
                res = {"content": [{"type": "text", "text": json.dumps(out, default=str)}]}
            else:
                res = {"ok": True}
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": res}) + "\n")
        except Exception as exc:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
