#!/usr/bin/env python3
"""Local Agent Room state store and small CLI/MCP-compatible command surface."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from harness import local_cli_command

STATE = Path(os.environ.get("AGENT_ROOM_STATE", Path.home() / ".local/state/omarchy/agent-room/house.json"))
_LOCK = threading.RLock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default() -> dict[str, Any]:
    return {"version": 1, "updated": now(), "rooms": [], "mail": [], "board": [], "work": [], "claims": [], "health": []}


class House:
    def __init__(self, path: str | Path = STATE):
        self.path = Path(path).expanduser()

    def ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(_default())

    def snapshot(self) -> dict[str, Any]:
        with _LOCK:
            self.ensure()
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else _default()
            except (OSError, json.JSONDecodeError):
                return _default()

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["updated"] = now()
        fd, name = tempfile.mkstemp(prefix="house.", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def mutate(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        with _LOCK:
            data = self.snapshot()
            result = fn(data)
            self._write(data)
            return result


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def find_room(data: dict[str, Any], room_id: str) -> dict[str, Any]:
    for room in data.get("rooms", []):
        if room.get("id") == room_id:
            return room
    raise KeyError(room_id)


def create_room(data: dict[str, Any], name: str, goal: str, cwd: str, roles: list[str], harness: str = "multi-agent-cli") -> dict[str, Any]:
    room = {"id": _id("room"), "name": name, "goal": goal, "cwd": cwd, "created": now(), "status": "ready",
            "roles": [{"id": role, "name": role.title(), "status": "idle", "harness": harness, "transport": "tui"} for role in roles]}
    data.setdefault("rooms", []).append(room)
    return room


def send_mail(data: dict[str, Any], room_id: str, sender: str, to: list[str], subject: str, body: str) -> dict[str, Any]:
    find_room(data, room_id)
    message = {"id": _id("mail"), "room_id": room_id, "from": sender, "to": to, "subject": subject, "body": body, "created": now(), "read": False}
    data.setdefault("mail", []).append(message)
    return message


def inbox_for(data: dict[str, Any], name: str, room_id: str) -> list[dict[str, Any]]:
    return [m for m in data.get("mail", []) if m.get("room_id") == room_id and ("*" in m.get("to", []) or name in m.get("to", []))]


def board_post(data: dict[str, Any], room_id: str, author: str, title: str, body: str) -> dict[str, Any]:
    find_room(data, room_id)
    post = {"id": _id("help"), "room_id": room_id, "author": author, "title": title, "body": body, "status": "open", "created": now(), "replies": []}
    data.setdefault("board", []).insert(0, post)
    data.setdefault("health", []).append({"title": "Help requested", "detail": title, "created": now()})
    return post


def board_reply(data: dict[str, Any], post_id: str, author: str, body: str) -> dict[str, Any]:
    for post in data.get("board", []):
        if post.get("id") == post_id:
            reply = {"id": _id("reply"), "author": author, "body": body, "created": now()}
            post.setdefault("replies", []).append(reply)
            return reply
    raise KeyError(post_id)


def create_work(data: dict[str, Any], room_id: str, title: str, detail: str, assignee: str) -> dict[str, Any]:
    find_room(data, room_id)
    item = {"id": _id("work"), "room_id": room_id, "title": title, "detail": detail, "assignee": assignee, "status": "open", "created": now()}
    data.setdefault("work", []).append(item)
    return item


def claim_paths(data: dict[str, Any], room_id: str, owner: str, paths: list[str]) -> list[dict[str, Any]]:
    find_room(data, room_id)
    result = []
    for path in paths:
        claim = {"id": _id("claim"), "room_id": room_id, "owner": owner, "path": path, "created": now()}
        data.setdefault("claims", []).append(claim)
        result.append(claim)
    return result


def local_harness_command(model: str = "local-model", profile: str = "developer") -> tuple[list[str], dict[str, str]]:
    """Build a command that delegates one seat goal to standalone MultiAgentCli."""
    command, extra_env = local_cli_command()
    command += ["run", "--profile", profile, "--agents", "lmstudio", "--model", model, "--no-progress", "--json"]
    return command, extra_env


def run_local_agent(goal: str, model: str = "local-model", profile: str = "developer", timeout: int = 180) -> dict[str, Any]:
    """Run a goal through the standalone LM Studio-first harness."""
    command, extra_env = local_harness_command(model=model, profile=profile)
    command += ["--goal", goal]
    env = os.environ.copy()
    env.update(extra_env)
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env, check=False)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        detail = completed.stderr.strip() or completed.stdout.strip() or str(exc)
        raise RuntimeError(f"MultiAgentCli returned invalid JSON: {detail}") from exc
    if completed.returncode != 0:
        raise RuntimeError(payload.get("content") or payload.get("error") or "MultiAgentCli agent failed")
    return payload


def call_tool(name: str, args: dict[str, Any], house: House | None = None) -> Any:
    house = house or House()
    room_id = os.environ.get("AGENT_ROOM_ID", args.get("room_id", ""))
    actor = os.environ.get("AGENT_ROOM_NAME", args.get("author", "Agent"))
    if name == "room_create": return house.mutate(lambda d: create_room(d, args["name"], args["goal"], args["cwd"], args["roles"], args.get("harness", "multi-agent-cli")))
    if name == "send_mail": return house.mutate(lambda d: send_mail(d, room_id, actor, args.get("to", ["*"]), args.get("subject", ""), args["body"]))
    if name == "fetch_inbox": return inbox_for(house.snapshot(), actor, room_id)
    if name == "ask_help": return house.mutate(lambda d: board_post(d, room_id, actor, args["title"], args["body"]))
    if name == "board_list": return house.snapshot().get("board", [])
    if name == "list_work": return house.snapshot().get("work", [])
    if name == "run_local_agent": return run_local_agent(
        goal=args["goal"], model=args.get("model", "local-model"),
        profile=args.get("profile", "developer"), timeout=int(args.get("timeout", 180)),
    )
    raise KeyError(name)


def mcp_tools() -> list[dict[str, Any]]:
    """Describe the local Agent Room tools using the MCP tool schema."""
    return [
        {"name": "room_create", "description": "Create a local agent room", "inputSchema": {"type": "object"}},
        {"name": "send_mail", "description": "Send a room message", "inputSchema": {"type": "object"}},
        {"name": "fetch_inbox", "description": "Read room messages", "inputSchema": {"type": "object"}},
        {"name": "ask_help", "description": "Post a help request", "inputSchema": {"type": "object"}},
        {"name": "board_list", "description": "List help requests", "inputSchema": {"type": "object"}},
        {"name": "list_work", "description": "List work items", "inputSchema": {"type": "object"}},
        {"name": "run_local_agent", "description": "Run one goal through MultiAgentCli and LM Studio", "inputSchema": {"type": "object"}},
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-room")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init")
    sub.add_parser("snapshot")
    mcp = sub.add_parser("mcp")
    mcp.add_argument("--stdio", action="store_true")
    seat = sub.add_parser("exec-seat")
    seat.add_argument("program")
    seat.add_argument("prompt")
    local = sub.add_parser("run-local", help="Run one goal through standalone MultiAgentCli/LM Studio")
    local.add_argument("goal")
    local.add_argument("--model", default="local-model")
    local.add_argument("--profile", default="developer")
    local.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    house = House()
    if args.command == "init": house.ensure(); return 0
    if args.command == "snapshot": print(json.dumps(house.snapshot(), indent=2)); return 0
    if args.command == "exec-seat":
        return subprocess.call([args.program] if not args.prompt else [args.program, args.prompt])
    if args.command == "run-local":
        try:
            print(json.dumps(run_local_agent(args.goal, args.model, args.profile, args.timeout)))
            return 0
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            print(json.dumps({"success": False, "error": str(exc)}))
            return 1
    if args.command == "mcp":
        for line in sys.stdin:
            try:
                request = json.loads(line)
                method = request.get("method", "")
                params = request.get("params", {}) or {}
                if method == "initialize":
                    result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "omarchy-agent-room", "version": "1.0.0"}}
                elif method in {"notifications/initialized", "initialized"}:
                    continue
                elif method == "tools/list":
                    result = {"tools": mcp_tools()}
                elif method == "tools/call":
                    result = call_tool(params["name"], params.get("arguments", {}), house)
                else:
                    result = call_tool(method, params.get("arguments", params), house)
                response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result if method in {"initialize", "tools/list"} else {"content": [{"type": "text", "text": json.dumps(result)}]}}
            except Exception as exc:
                response = {"jsonrpc": "2.0", "id": request.get("id") if 'request' in locals() else None, "error": {"code": -32000, "message": str(exc)}}
            print(json.dumps(response), flush=True)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
