#!/usr/bin/env python3
"""Omarchy Agent Room — local house, MCP Mail, and a help board.

No HTTP server. State lives in ~/.local/state/omarchy/agent-room/house.json.
Agents talk through the stdio MCP server (`agent-room mcp`) and the native
Omarchy console watches the same file.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
PLUGIN_ID = "io.github.franzferdinan51.agent-room"
STATE_DIR = Path.home() / ".local/state/omarchy/agent-room"
HOUSE_PATH = STATE_DIR / "house.json"
LOCK_PATH = STATE_DIR / "house.lock"
BRIEFS_DIR = STATE_DIR / "briefs"
DEFAULT_WORKSPACE = "agent-house"
DEFAULT_ROLES = [
    "coordinator",
    "builder",
    "reviewer",
    "judge",
    "creative-director",
]
MAX_CMDS = 400
MAX_MAIL = 2000
MAX_BOARD = 500
MAX_WORK = 400

AGENT_LAUNCH = {
    "grok": ["grok", "--permission-mode", "bypassPermissions"],
    "codex": ["codex", "--approve-for-me"],
    "claude": ["claude", "--permission-mode", "auto"],
    "opencode": ["opencode", "--auto"],
    "gemini": ["gemini", "--yolo"],
    "copilot": ["copilot", "--allow-all"],
    "crush": ["crush", "--yolo"],
    "omp": ["omp", "--auto-approve"],
    "pi": ["pi"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_hhmm() -> str:
    return datetime.now().strftime("%H:%M")


def nid(prefix: str = "") -> str:
    return (prefix + uuid.uuid4().hex[:12]) if prefix else uuid.uuid4().hex[:12]


def slugify(name: str) -> str:
    out = []
    for ch in name.lower().strip():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_." and (not out or out[-1] != "-"):
            out.append("-")
    return "".join(out).strip("-")[:40] or "room"


def empty_house() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": now_iso(),
        "house": {
            "name": "Agent House",
            "workspace": DEFAULT_WORKSPACE,
            "default_program": default_program(),
        },
        "rooms": [],
        "mail": [],
        "board": [],
        "work": [],
        "claims": [],
        "cmds": [],
        "plan": [],
        "context": [],
        "health": [],
    }


def default_program() -> str:
    try:
        out = subprocess.check_output(
            ["omarchy-default-agent"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        if out:
            return out
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    for name in ("grok", "codex", "claude", "opencode"):
        if shutil.which(name):
            return name
    return "grok"


def omarchy_version() -> str:
    try:
        return subprocess.check_output(
            ["omarchy", "version"], text=True, stderr=subprocess.DEVNULL
        ).strip().splitlines()[0]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "omarchy"


class House:
    def __init__(self, path: Path = HOUSE_PATH):
        self.path = path
        self.state_dir = path.parent
        self.lock_path = self.state_dir / "house.lock"

    def ensure(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(empty_house())

    def _lock(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        fh = open(self.lock_path, "a+")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        return fh

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return empty_house()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return empty_house()
        if not isinstance(data, dict):
            return empty_house()
        base = empty_house()
        base.update(data)
        for key in (
            "rooms",
            "mail",
            "board",
            "work",
            "claims",
            "cmds",
            "plan",
            "context",
            "health",
        ):
            if not isinstance(base.get(key), list):
                base[key] = []
        if not isinstance(base.get("house"), dict):
            base["house"] = empty_house()["house"]
        return base

    def _write(self, data: dict[str, Any]) -> None:
        data["updated_at"] = now_iso()
        decorate_house(data)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def mutate(self, fn) -> dict[str, Any]:
        self.ensure()
        lock = self._lock()
        try:
            data = self._read()
            result = fn(data)
            self._write(data)
            return result if result is not None else data
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()

    def load(self) -> dict[str, Any]:
        self.ensure()
        lock = self._lock()
        try:
            return self._read()
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()

    def snapshot(self) -> dict[str, Any]:
        data = self.load()
        rooms = data.get("rooms") or []
        mail = data.get("mail") or []
        work = data.get("work") or []
        claims = data.get("claims") or []
        board = data.get("board") or []
        running_agents = 0
        for room in rooms:
            for role in room.get("roles") or []:
                if role.get("status") == "running":
                    running_agents += 1
        data["stats"] = {
            "teams": len(rooms),
            "running": running_agents,
            "messages": len(mail),
            "open_board": sum(1 for p in board if p.get("status") == "open"),
            "active_work": sum(1 for w in work if w.get("status") == "active"),
            "blocked_work": sum(1 for w in work if w.get("status") == "blocked"),
            "claims": len(claims),
            "cmds": len(data.get("cmds") or []),
            "plan": len(data.get("plan") or []),
            "health": len(data.get("health") or []),
            "context": len(data.get("context") or []),
        }
        data["meta"] = {
            "program": (data.get("house") or {}).get("default_program") or default_program(),
            "omarchy": omarchy_version(),
            "version": VERSION,
            "plugin_id": PLUGIN_ID,
            "state_path": str(self.path),
        }
        return data


def decorate_house(data: dict[str, Any]) -> dict[str, Any]:
    """Fill stats/meta/health so the console FileView does not need a second snapshot."""
    rooms = data.get("rooms") or []
    mail = data.get("mail") or []
    work = data.get("work") or []
    claims = data.get("claims") or []
    board = data.get("board") or []
    running_agents = 0
    for room in rooms:
        for role in room.get("roles") or []:
            if role.get("status") == "running":
                running_agents += 1
    data["health"] = derive_health(data)
    data["stats"] = {
        "teams": len(rooms),
        "running": running_agents,
        "messages": len(mail),
        "open_board": sum(1 for p in board if p.get("status") == "open"),
        "active_work": sum(1 for w in work if w.get("status") == "active"),
        "blocked_work": sum(1 for w in work if w.get("status") == "blocked"),
        "claims": len(claims),
        "cmds": len(data.get("cmds") or []),
        "plan": len(data.get("plan") or []),
        "health": len(data["health"]),
        "context": len(data.get("context") or []),
    }
    data["meta"] = {
        "program": (data.get("house") or {}).get("default_program") or default_program(),
        "omarchy": omarchy_version(),
        "version": VERSION,
        "plugin_id": PLUGIN_ID,
        "state_path": str(HOUSE_PATH),
    }
    return data


def derive_health(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for post in data.get("board") or []:
        if post.get("status") == "open":
            items.append(
                {
                    "id": "board-" + post["id"],
                    "level": "warn",
                    "title": "Help requested",
                    "message": f"{post.get('author', '?')} · {post.get('title', '')}",
                }
            )
    for work in data.get("work") or []:
        if work.get("status") == "blocked":
            items.append(
                {
                    "id": "work-" + work["id"],
                    "level": "warn",
                    "title": "Work blocked",
                    "message": work.get("title") or work["id"],
                }
            )
    claimed = {}
    for claim in data.get("claims") or []:
        path = claim.get("path")
        if not path:
            continue
        claimed.setdefault(path, []).append(claim)
    for path, holders in claimed.items():
        exclusive = [c for c in holders if c.get("exclusive")]
        if len(exclusive) > 1:
            names = ", ".join(c.get("agent", "?") for c in exclusive)
            items.append(
                {
                    "id": "claim-" + path,
                    "level": "error",
                    "title": "Claim collision",
                    "message": f"{path} held by {names}",
                }
            )
    if not (data.get("rooms") or []):
        items.append(
            {
                "id": "empty-house",
                "level": "info",
                "title": "House is empty",
                "message": "Create a room to put agents on a shared goal.",
            }
        )
    return items[-40:]


def log_cmd(data: dict[str, Any], agent: str, cmd: str, status: str = "ok") -> None:
    data.setdefault("cmds", []).append(
        {
            "id": nid("cmd-"),
            "ts": now_iso(),
            "time": local_hhmm(),
            "agent": agent,
            "cmd": cmd,
            "status": status,
        }
    )
    data["cmds"] = data["cmds"][-MAX_CMDS:]


def find_room(data: dict[str, Any], room_id: str) -> dict[str, Any]:
    for room in data.get("rooms") or []:
        if room.get("id") == room_id or room.get("slug") == room_id or room.get("name") == room_id:
            return room
    raise KeyError(f"room not found: {room_id}")


def find_role(room: dict[str, Any], name: str) -> dict[str, Any] | None:
    want = name.lower()
    for role in room.get("roles") or []:
        if role.get("id") == want or role.get("name", "").lower() == want:
            return role
    return None


def create_room(
    data: dict[str, Any],
    name: str,
    goal: str,
    cwd: str | None = None,
    roles: list[str] | None = None,
    program: str | None = None,
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("room name is required")
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("room goal is required")
    role_ids = [r.strip().lower() for r in (roles or DEFAULT_ROLES) if r.strip()]
    if not role_ids:
        role_ids = list(DEFAULT_ROLES)
    program = program or (data.get("house") or {}).get("default_program") or default_program()
    cwd = os.path.expanduser(cwd or str(Path.home() / "Work"))
    room = {
        "id": nid("rm-"),
        "slug": slugify(name),
        "name": name,
        "goal": goal,
        "cwd": cwd,
        "status": "idle",
        "program": program,
        "created_at": now_iso(),
        "monitor_hidden": False,
        "roles": [
            {
                "id": rid,
                "name": rid.replace("-", " ").title(),
                "program": program,
                "status": "idle",
                "pid": 0,
            }
            for rid in role_ids
        ],
    }
    data.setdefault("rooms", []).append(room)
    log_cmd(data, "house", f"create-room {name}", "ok")
    return room


def send_mail(
    data: dict[str, Any],
    room_id: str,
    sender: str,
    to: list[str] | str,
    subject: str,
    body: str,
    thread_id: str | None = None,
) -> dict[str, Any]:
    room = find_room(data, room_id)
    if isinstance(to, str):
        to_list = [part.strip() for part in to.split(",") if part.strip()]
    else:
        to_list = [str(x).strip() for x in to if str(x).strip()]
    if not to_list:
        to_list = ["*"]
    msg = {
        "id": nid("msg-"),
        "room_id": room["id"],
        "room": room["name"],
        "from": sender,
        "to": to_list,
        "subject": subject or "",
        "body": body or "",
        "thread_id": thread_id or nid("th-"),
        "created_at": now_iso(),
        "time": local_hhmm(),
        "acked": False,
    }
    data.setdefault("mail", []).append(msg)
    data["mail"] = data["mail"][-MAX_MAIL:]
    log_cmd(data, sender, f"send-mail {subject or '(no subject)'}", "ok")
    return msg


def inbox_for(data: dict[str, Any], agent: str, room_id: str | None = None) -> list[dict[str, Any]]:
    want = agent.lower()
    out = []
    for msg in data.get("mail") or []:
        if room_id and msg.get("room_id") not in (room_id,) and msg.get("room") != room_id:
            try:
                room = find_room(data, room_id)
            except KeyError:
                continue
            if msg.get("room_id") != room["id"]:
                continue
        recipients = [str(x).lower() for x in (msg.get("to") or [])]
        if "*" in recipients or "all" in recipients or want in recipients:
            out.append(msg)
        elif msg.get("from", "").lower() == want:
            out.append(msg)
    return out[-200:]


def board_post(
    data: dict[str, Any],
    room_id: str,
    author: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    room = find_room(data, room_id)
    post = {
        "id": nid("bd-"),
        "room_id": room["id"],
        "room": room["name"],
        "author": author,
        "title": title or "Help",
        "body": body or "",
        "status": "open",
        "created_at": now_iso(),
        "time": local_hhmm(),
        "replies": [],
    }
    data.setdefault("board", []).append(post)
    data["board"] = data["board"][-MAX_BOARD:]
    log_cmd(data, author, f"board-post {post['title']}", "ok")
    return post


def board_reply(data: dict[str, Any], post_id: str, author: str, body: str) -> dict[str, Any]:
    for post in data.get("board") or []:
        if post.get("id") == post_id:
            reply = {
                "id": nid("rp-"),
                "author": author,
                "body": body or "",
                "created_at": now_iso(),
                "time": local_hhmm(),
            }
            post.setdefault("replies", []).append(reply)
            log_cmd(data, author, f"board-reply {post_id}", "ok")
            return post
    raise KeyError(f"board post not found: {post_id}")


def create_work(
    data: dict[str, Any],
    room_id: str,
    title: str,
    brief: str,
    owner: str = "",
    status: str = "active",
    nxt: str = "",
) -> dict[str, Any]:
    room = find_room(data, room_id)
    item = {
        "id": nid("wk-"),
        "room_id": room["id"],
        "room": room["name"],
        "title": title,
        "brief": brief,
        "status": status,
        "owner": owner or room.get("program") or "codex",
        "next": nxt,
        "cwd": room.get("cwd") or "",
        "files": 0,
        "claims": 0,
        "created_at": now_iso(),
    }
    data.setdefault("work", []).append(item)
    data["work"] = data["work"][-MAX_WORK:]
    log_cmd(data, owner or "house", f"create-work {title}", "ok")
    return item


def claim_work(data: dict[str, Any], work_id: str, agent: str) -> dict[str, Any]:
    for item in data.get("work") or []:
        if item.get("id") == work_id:
            item["owner"] = agent
            item["status"] = "active"
            log_cmd(data, agent, f"claim-work {item.get('title')}", "ok")
            return item
    raise KeyError(f"work not found: {work_id}")


def complete_work(data: dict[str, Any], work_id: str, agent: str, nxt: str = "") -> dict[str, Any]:
    for item in data.get("work") or []:
        if item.get("id") == work_id:
            item["status"] = "completed"
            if nxt:
                item["next"] = nxt
            log_cmd(data, agent, f"complete-work {item.get('title')}", "ok")
            return item
    raise KeyError(f"work not found: {work_id}")


def claim_paths(
    data: dict[str, Any],
    room_id: str,
    agent: str,
    paths: list[str],
    exclusive: bool = True,
    ttl: int = 3600,
) -> list[dict[str, Any]]:
    room = find_room(data, room_id)
    made = []
    for path in paths:
        path = path.strip()
        if not path:
            continue
        claim = {
            "id": nid("cl-"),
            "room_id": room["id"],
            "agent": agent,
            "path": path,
            "exclusive": bool(exclusive),
            "ttl": int(ttl),
            "created_at": now_iso(),
        }
        data.setdefault("claims", []).append(claim)
        made.append(claim)
        for work in data.get("work") or []:
            if work.get("room_id") == room["id"] and work.get("status") == "active":
                work["claims"] = int(work.get("claims") or 0) + 1
    log_cmd(data, agent, f"claim-paths {len(made)}", "ok")
    return made


def release_claim(data: dict[str, Any], claim_id: str, agent: str) -> dict[str, Any]:
    kept = []
    found = None
    for claim in data.get("claims") or []:
        if claim.get("id") == claim_id:
            found = claim
            continue
        kept.append(claim)
    if not found:
        raise KeyError(f"claim not found: {claim_id}")
    data["claims"] = kept
    log_cmd(data, agent, f"release-claim {claim_id}", "ok")
    return found


def add_plan(data: dict[str, Any], room_id: str, author: str, text: str) -> dict[str, Any]:
    room = find_room(data, room_id)
    item = {
        "id": nid("pl-"),
        "room_id": room["id"],
        "room": room["name"],
        "author": author,
        "text": text,
        "status": "open",
        "created_at": now_iso(),
        "time": local_hhmm(),
    }
    data.setdefault("plan", []).append(item)
    log_cmd(data, author, "plan-add", "ok")
    return item


def add_context(data: dict[str, Any], room_id: str, author: str, text: str) -> dict[str, Any]:
    room = find_room(data, room_id)
    item = {
        "id": nid("cx-"),
        "room_id": room["id"],
        "room": room["name"],
        "author": author,
        "text": text,
        "created_at": now_iso(),
        "time": local_hhmm(),
    }
    data.setdefault("context", []).append(item)
    log_cmd(data, author, "context-write", "ok")
    return item


def briefing_text(room: dict[str, Any], role: dict[str, Any]) -> str:
    others = ", ".join(
        f"{r['name']} ({r['id']})" for r in room.get("roles") or [] if r["id"] != role["id"]
    )
    return f"""You are {role['name']} in Omarchy Agent Room "{room['name']}".

ROOM GOAL
{room['goal']}

WORKING DIRECTORY
{room['cwd']}

YOUR ROLE
You are the {role['id']}. Coordinate through MCP Mail and the help board — do not wait for the human unless you are blocked.

TEAMMATES
{others or '(solo)'}

HOW TO TALK
This machine has an MCP server named `agent-room`. Use it. There is no web UI and no HTTP port.

MCP Mail (addressed chat):
- send_mail(room_id="{room['id']}", sender="{role['name']}", to=["Coordinator"] or ["*"], subject=..., body=...)
- fetch_inbox(agent_name="{role['name']}", room_id="{room['id']}")
- reply_mail(message_id=..., sender="{role['name']}", body=...)

Help board (ask for help when stuck):
- ask_help(room_id="{room['id']}", author="{role['name']}", title=..., body=...)
- board_list(room_id="{room['id']}")
- board_reply(post_id=..., author="{role['name']}", body=...)

Work + file claims (avoid collisions):
- list_work(room_id="{room['id']}")
- claim_work(work_id=..., agent="{role['name']}")
- complete_work(work_id=..., agent="{role['name']}", next="what happens next")
- claim_paths(room_id="{room['id']}", agent="{role['name']}", paths=["src/foo.py"], exclusive=true)
- release_claim(claim_id=..., agent="{role['name']}")

Start by fetching your inbox and listing work. Claim one assignment. Mail the team what you took. When you need help, post on the board instead of guessing.

Identity for this seat:
AGENT_ROOM_ID={room['id']}
AGENT_ROOM_NAME={role['name']}
AGENT_ROOM_ROLE={role['id']}
"""


def write_brief(room: dict[str, Any], role: dict[str, Any]) -> Path:
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    path = BRIEFS_DIR / f"{room['id']}-{role['id']}.md"
    path.write_text(briefing_text(room, role), encoding="utf-8")
    return path


def launch_command(program: str, prompt: str) -> list[str]:
    base = list(AGENT_LAUNCH.get(program, [program]))
    if program == "pi":
        return base + [prompt]
    if program == "crush":
        return ["crush", "run", prompt]
    if program == "gemini":
        return ["gemini", "--yolo", "--prompt-interactive", prompt]
    if program == "copilot":
        return ["copilot", "--allow-all", "--interactive", prompt]
    return base + ["--", prompt]


def start_room(house: House, room_id: str) -> dict[str, Any]:
    data = house.load()
    room = find_room(data, room_id)

    def _start(current: dict[str, Any]) -> dict[str, Any]:
        r = find_room(current, room["id"])
        r["status"] = "running"
        for role in r.get("roles") or []:
            if role.get("status") == "running" and role.get("pid"):
                continue
            brief = write_brief(r, role)
            prompt = (
                f"Read the briefing file {brief} and follow it. "
                f"You are {role['name']} in room {r['name']}."
            )
            program = role.get("program") or r.get("program") or default_program()
            env = os.environ.copy()
            env["AGENT_ROOM_ID"] = r["id"]
            env["AGENT_ROOM_NAME"] = role["name"]
            env["AGENT_ROOM_ROLE"] = role["id"]
            env["AGENT_ROOM_CWD"] = r.get("cwd") or str(Path.home() / "Work")
            plugin = Path(__file__).resolve().parent
            launch = plugin / "bin" / "launch-seat"
            try:
                proc = subprocess.Popen(
                    [
                        str(launch),
                        r["id"],
                        role["id"],
                        program,
                        r.get("cwd") or str(Path.home() / "Work"),
                        prompt,
                    ],
                    env=env,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                role["status"] = "running"
                role["pid"] = proc.pid
                role["started_at"] = now_iso()
            except OSError as exc:
                role["status"] = "error"
                role["error"] = str(exc)
        log_cmd(current, "house", f"start-room {r['name']}", "ok")
        return r

    started = house.mutate(_start)
    return started


def stop_room(house: House, room_id: str) -> dict[str, Any]:
    def _stop(current: dict[str, Any]) -> dict[str, Any]:
        r = find_room(current, room_id)
        r["status"] = "idle"
        for role in r.get("roles") or []:
            pid = int(role.get("pid") or 0)
            if pid > 1:
                try:
                    os.kill(pid, 15)
                except OSError:
                    pass
            role["status"] = "idle"
            role["pid"] = 0
        log_cmd(current, "house", f"stop-room {r['name']}", "ok")
        return r

    return house.mutate(_stop)


# ---------------------------------------------------------------------------
# MCP stdio (no web server)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "house_status",
        "description": "Snapshot of Agent House: rooms, stats, health.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "room_list",
        "description": "List rooms in the house.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "room_create",
        "description": "Create a room with a goal and agent roles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "goal": {"type": "string"},
                "cwd": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
                "program": {"type": "string"},
            },
            "required": ["name", "goal"],
        },
    },
    {
        "name": "room_start",
        "description": "Launch every seat in a room on the agent-house workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {"room_id": {"type": "string"}},
            "required": ["room_id"],
        },
    },
    {
        "name": "whoami",
        "description": "This seat's room/role from AGENT_ROOM_* env.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "send_mail",
        "description": "Send MCP Mail to teammates in a room. to=['*'] broadcasts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "sender": {"type": "string"},
                "to": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "thread_id": {"type": "string"},
            },
            "required": ["body"],
        },
    },
    {
        "name": "fetch_inbox",
        "description": "Read MCP Mail visible to this agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string"},
                "room_id": {"type": "string"},
            },
        },
    },
    {
        "name": "reply_mail",
        "description": "Reply on an existing MCP Mail thread.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "sender": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["message_id", "body"],
        },
    },
    {
        "name": "ask_help",
        "description": "Post on the room message board asking teammates for help.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "author": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "board_list",
        "description": "List help-board posts for a room.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "status": {"type": "string"},
            },
        },
    },
    {
        "name": "board_reply",
        "description": "Reply to a help-board post.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string"},
                "author": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["post_id", "body"],
        },
    },
    {
        "name": "create_work",
        "description": "Add a task capsule the team can claim.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "title": {"type": "string"},
                "brief": {"type": "string"},
                "owner": {"type": "string"},
                "next": {"type": "string"},
            },
            "required": ["title", "brief"],
        },
    },
    {
        "name": "list_work",
        "description": "List task capsules.",
        "inputSchema": {
            "type": "object",
            "properties": {"room_id": {"type": "string"}},
        },
    },
    {
        "name": "claim_work",
        "description": "Claim a task capsule.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "work_id": {"type": "string"},
                "agent": {"type": "string"},
            },
            "required": ["work_id"],
        },
    },
    {
        "name": "complete_work",
        "description": "Mark a task capsule complete.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "work_id": {"type": "string"},
                "agent": {"type": "string"},
                "next": {"type": "string"},
            },
            "required": ["work_id"],
        },
    },
    {
        "name": "claim_paths",
        "description": "Advisory exclusive lease on file paths so teammates do not collide.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "agent": {"type": "string"},
                "paths": {"type": "array", "items": {"type": "string"}},
                "exclusive": {"type": "boolean"},
                "ttl": {"type": "integer"},
            },
            "required": ["paths"],
        },
    },
    {
        "name": "list_claims",
        "description": "List file path claims.",
        "inputSchema": {
            "type": "object",
            "properties": {"room_id": {"type": "string"}},
        },
    },
    {
        "name": "release_claim",
        "description": "Release a file path claim.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string"},
                "agent": {"type": "string"},
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "plan_add",
        "description": "Add a plan item the console Plan tab shows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "author": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "context_write",
        "description": "Leave a context note for the room.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "author": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
    },
]


def env_identity() -> dict[str, str]:
    return {
        "room_id": os.environ.get("AGENT_ROOM_ID", ""),
        "name": os.environ.get("AGENT_ROOM_NAME", "") or os.environ.get("AGENT_ROOM_ROLE", "agent"),
        "role": os.environ.get("AGENT_ROOM_ROLE", ""),
        "cwd": os.environ.get("AGENT_ROOM_CWD", ""),
    }


def _room_id_arg(args: dict[str, Any], house: House) -> str:
    rid = args.get("room_id") or env_identity()["room_id"]
    if rid:
        return str(rid)
    data = house.load()
    rooms = data.get("rooms") or []
    if len(rooms) == 1:
        return rooms[0]["id"]
    running = [r for r in rooms if r.get("status") == "running"]
    if len(running) == 1:
        return running[0]["id"]
    raise ValueError("room_id is required (or set AGENT_ROOM_ID)")


def _resolved_room(args: dict[str, Any], house: House) -> str:
    """Resolve room id *before* taking the house lock."""
    return _room_id_arg(args, house)


def _agent_arg(args: dict[str, Any], key: str = "sender") -> str:
    return str(args.get(key) or args.get("agent") or args.get("author") or env_identity()["name"] or "agent")


def call_tool(name: str, args: dict[str, Any], house: House) -> Any:
    args = args or {}
    ident = env_identity()

    if name == "house_status":
        return house.snapshot()
    if name == "room_list":
        return house.snapshot().get("rooms") or []
    if name == "whoami":
        return ident
    if name == "room_create":
        return house.mutate(
            lambda d: create_room(
                d,
                args.get("name", ""),
                args.get("goal", ""),
                args.get("cwd"),
                args.get("roles"),
                args.get("program"),
            )
        )
    if name == "room_start":
        return start_room(house, _resolved_room(args, house))
    if name == "send_mail":
        room_id = _resolved_room(args, house)
        sender = _agent_arg(args, "sender")
        return house.mutate(
            lambda d: send_mail(
                d,
                room_id,
                sender,
                args.get("to") or ["*"],
                args.get("subject") or "",
                args.get("body") or "",
                args.get("thread_id"),
            )
        )
    if name == "fetch_inbox":
        data = house.load()
        agent = _agent_arg(args, "agent_name")
        rid = args.get("room_id") or ident["room_id"] or None
        return inbox_for(data, agent, rid)
    if name == "reply_mail":

        def _reply(d: dict[str, Any]) -> dict[str, Any]:
            original = None
            for msg in d.get("mail") or []:
                if msg.get("id") == args.get("message_id"):
                    original = msg
                    break
            if not original:
                raise KeyError("message not found")
            return send_mail(
                d,
                original["room_id"],
                _agent_arg(args, "sender"),
                [original.get("from") or "*"],
                "Re: " + (original.get("subject") or ""),
                args.get("body") or "",
                original.get("thread_id"),
            )

        return house.mutate(_reply)
    if name == "ask_help":
        room_id = _resolved_room(args, house)
        author = _agent_arg(args, "author")
        return house.mutate(
            lambda d: board_post(
                d,
                room_id,
                author,
                args.get("title") or "Help",
                args.get("body") or "",
            )
        )
    if name == "board_list":
        data = house.load()
        rid = args.get("room_id") or ident["room_id"]
        status = args.get("status")
        posts = data.get("board") or []
        if rid:
            room = find_room(data, rid)
            posts = [p for p in posts if p.get("room_id") == room["id"]]
        if status:
            posts = [p for p in posts if p.get("status") == status]
        return posts
    if name == "board_reply":
        return house.mutate(
            lambda d: board_reply(d, args["post_id"], _agent_arg(args, "author"), args.get("body") or "")
        )
    if name == "create_work":
        room_id = _resolved_room(args, house)
        owner = _agent_arg(args, "owner") if args.get("owner") else ""
        return house.mutate(
            lambda d: create_work(
                d,
                room_id,
                args.get("title") or "",
                args.get("brief") or "",
                owner,
                "active",
                args.get("next") or "",
            )
        )
    if name == "list_work":
        data = house.load()
        items = data.get("work") or []
        rid = args.get("room_id") or ident["room_id"]
        if rid:
            room = find_room(data, rid)
            items = [w for w in items if w.get("room_id") == room["id"]]
        return items
    if name == "claim_work":
        return house.mutate(lambda d: claim_work(d, args["work_id"], _agent_arg(args, "agent")))
    if name == "complete_work":
        return house.mutate(
            lambda d: complete_work(d, args["work_id"], _agent_arg(args, "agent"), args.get("next") or "")
        )
    if name == "claim_paths":
        room_id = _resolved_room(args, house)
        agent = _agent_arg(args, "agent")
        return house.mutate(
            lambda d: claim_paths(
                d,
                room_id,
                agent,
                list(args.get("paths") or []),
                bool(args.get("exclusive", True)),
                int(args.get("ttl") or 3600),
            )
        )
    if name == "list_claims":
        data = house.load()
        items = data.get("claims") or []
        rid = args.get("room_id") or ident["room_id"]
        if rid:
            room = find_room(data, rid)
            items = [c for c in items if c.get("room_id") == room["id"]]
        return items
    if name == "release_claim":
        return house.mutate(lambda d: release_claim(d, args["claim_id"], _agent_arg(args, "agent")))
    if name == "plan_add":
        room_id = _resolved_room(args, house)
        author = _agent_arg(args, "author")
        return house.mutate(lambda d: add_plan(d, room_id, author, args.get("text") or ""))
    if name == "context_write":
        room_id = _resolved_room(args, house)
        author = _agent_arg(args, "author")
        return house.mutate(lambda d: add_context(d, room_id, author, args.get("text") or ""))
    raise ValueError(f"unknown tool: {name}")


def mcp_write(msg: dict[str, Any]) -> None:
    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    sys.stdout.buffer.flush()


def mcp_read() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\n", b"\r\n"):
            break
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if ":" in text:
            key, val = text.split(":", 1)
            headers[key.strip().lower()] = val.strip()
    n = int(headers.get("content-length") or 0)
    if n <= 0:
        return None
    raw = sys.stdin.buffer.read(n)
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def run_mcp() -> int:
    house = House()
    house.ensure()
    while True:
        try:
            req = mcp_read()
        except Exception as exc:  # noqa: BLE001
            mcp_write(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"parse error: {exc}"},
                }
            )
            continue
        if req is None:
            return 0
        if not isinstance(req, dict):
            continue
        method = req.get("method")
        req_id = req.get("id")
        if method is None:
            continue
        if req_id is None:
            continue
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "agent-room", "version": VERSION},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = req.get("params") or {}
                name = params.get("name")
                arguments = params.get("arguments") or {}
                value = call_tool(str(name), arguments, house)
                result = {
                    "content": [{"type": "text", "text": json.dumps(value, indent=2, default=str)}],
                    "isError": False,
                }
            else:
                mcp_write(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"unknown method {method}"},
                    }
                )
                continue
            mcp_write({"jsonrpc": "2.0", "id": req_id, "result": result})
        except Exception as exc:  # noqa: BLE001
            if method == "tools/call":
                mcp_write(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": str(exc)}],
                            "isError": True,
                        },
                    }
                )
            else:
                mcp_write(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32000, "message": str(exc)},
                    }
                )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_json(value: Any) -> None:
    json.dump(value, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-room", description="Omarchy Agent Room (no web server)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create local state")
    sub.add_parser("status", help="Print house snapshot JSON")
    sub.add_parser("mcp", help="Run the stdio MCP server")
    sub.add_parser("snapshot", help="Alias for status")

    p_create = sub.add_parser("create-room")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--goal", required=True)
    p_create.add_argument("--cwd", default="")
    p_create.add_argument("--roles", default=",".join(DEFAULT_ROLES))
    p_create.add_argument("--program", default="")

    p_start = sub.add_parser("start-room")
    p_start.add_argument("room_id")
    p_stop = sub.add_parser("stop-room")
    p_stop.add_argument("room_id")

    p_mail = sub.add_parser("send")
    p_mail.add_argument("--room", required=True)
    p_mail.add_argument("--from", dest="sender", required=True)
    p_mail.add_argument("--to", default="*")
    p_mail.add_argument("--subject", default="")
    p_mail.add_argument("--body", required=True)

    p_inbox = sub.add_parser("inbox")
    p_inbox.add_argument("--agent", required=True)
    p_inbox.add_argument("--room", default="")

    p_board = sub.add_parser("board-post")
    p_board.add_argument("--room", required=True)
    p_board.add_argument("--author", required=True)
    p_board.add_argument("--title", required=True)
    p_board.add_argument("--body", required=True)

    p_work = sub.add_parser("create-work")
    p_work.add_argument("--room", required=True)
    p_work.add_argument("--title", required=True)
    p_work.add_argument("--brief", required=True)
    p_work.add_argument("--owner", default="")
    p_work.add_argument("--next", default="")

    p_hide = sub.add_parser("set-monitor")
    p_hide.add_argument("room_id")
    p_hide.add_argument("--hidden", choices=["true", "false"], required=True)

    p_review = sub.add_parser("review")
    p_review.add_argument("--room", default="")

    args = parser.parse_args(argv)
    house = House()
    house.ensure()

    if args.cmd == "mcp":
        return run_mcp()
    if args.cmd in ("status", "snapshot", "init"):
        print_json(house.snapshot())
        return 0
    if args.cmd == "create-room":
        roles = [r.strip() for r in args.roles.split(",") if r.strip()]
        room = house.mutate(
            lambda d: create_room(d, args.name, args.goal, args.cwd or None, roles, args.program or None)
        )
        print_json(room)
        return 0
    if args.cmd == "start-room":
        print_json(start_room(house, args.room_id))
        return 0
    if args.cmd == "stop-room":
        print_json(stop_room(house, args.room_id))
        return 0
    if args.cmd == "send":
        msg = house.mutate(
            lambda d: send_mail(d, args.room, args.sender, args.to, args.subject, args.body)
        )
        print_json(msg)
        return 0
    if args.cmd == "inbox":
        print_json(inbox_for(house.load(), args.agent, args.room or None))
        return 0
    if args.cmd == "board-post":
        print_json(
            house.mutate(lambda d: board_post(d, args.room, args.author, args.title, args.body))
        )
        return 0
    if args.cmd == "create-work":
        print_json(
            house.mutate(
                lambda d: create_work(d, args.room, args.title, args.brief, args.owner, "active", args.next)
            )
        )
        return 0
    if args.cmd == "set-monitor":
        hidden = args.hidden == "true"

        def _hide(d: dict[str, Any]) -> dict[str, Any]:
            room = find_room(d, args.room_id)
            room["monitor_hidden"] = hidden
            return room

        print_json(house.mutate(_hide))
        return 0
    if args.cmd == "review":
        data = house.load()
        rid = args.room
        if not rid:
            rooms = data.get("rooms") or []
            if not rooms:
                raise SystemExit("no rooms")
            rid = rooms[-1]["id"]

        def _review(d: dict[str, Any]) -> dict[str, Any]:
            room = find_room(d, rid)
            post = board_post(
                d,
                room["id"],
                "operator",
                "REVIEW requested",
                "The operator hit REVIEW. Coordinator: synthesize the team's work into one result. "
                "Reviewer and Judge: check it.",
            )
            work = create_work(
                d,
                room["id"],
                f"Review {room['name']}",
                "Produce the coordinator's integrated result and a reviewer/judge pass.",
                "Coordinator",
                "active",
                "Coordinator integrates; Reviewer and Judge respond on MCP Mail.",
            )
            send_mail(
                d,
                room["id"],
                "operator",
                ["*"],
                "REVIEW",
                "Operator requested a review pass on this room.",
            )
            return {"board": post, "work": work}

        print_json(house.mutate(_review))
        return 0
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(cli())
    except BrokenPipeError:
        raise SystemExit(0)
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
