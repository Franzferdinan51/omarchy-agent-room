#!/usr/bin/env python3
"""Drive one Agent Room seat over ACP stdio (newline-delimited JSON-RPC).

Spawns the harness ACP adapter, initializes a session, sends the briefing
prompt, and appends session/update events to a jsonl log the console tails.
No HTTP server.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import harness as hx

STATE_DIR = Path.home() / ".local/state/omarchy/agent-room"
LOG_DIR = STATE_DIR / "acp"


def _log(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")


def _send(proc: subprocess.Popen, msg: dict[str, Any]) -> None:
    line = json.dumps(msg, ensure_ascii=False) + "\n"
    assert proc.stdin is not None
    proc.stdin.write(line.encode("utf-8"))
    proc.stdin.flush()


def _handle_server_request(proc: subprocess.Popen, msg: dict[str, Any], log_path: Path) -> bool:
    """Answer ACP server requests that would otherwise leave a seat waiting."""
    if msg.get("method") != "session/request_permission" or "id" not in msg:
        return False
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
    options = params.get("options") if isinstance(params.get("options"), list) else []
    selected = next(
        (
            option for option in options
            if isinstance(option, dict) and "allow" in str(option.get("kind", "")).lower()
        ),
        None,
    )
    if selected and selected.get("optionId"):
        result = {"outcome": {"outcome": "selected", "optionId": selected["optionId"]}}
    else:
        result = {"outcome": {"outcome": "cancelled"}}
    response = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
    _log(log_path, {"type": "rpc", "dir": "out", "method": msg.get("method"), "id": msg.get("id"), "payload": response})
    _send(proc, response)
    return True


def _close_proc(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proc.kill()
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        if stream:
            try:
                stream.close()
            except OSError:
                pass


def _read_json_line(proc: subprocess.Popen, timeout: float = 30.0) -> dict[str, Any] | None:
    assert proc.stdout is not None
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        if proc.poll() is not None and not buf:
            return None
        remaining = max(0.0, deadline - time.time())
        try:
            ready, _, _ = select.select([proc.stdout], [], [], min(remaining, 0.25))
        except (OSError, ValueError):
            return None
        if not ready:
            continue
        chunk = proc.stdout.readline()
        if not chunk:
            continue
        for line in chunk.splitlines():
            if not line:
                continue
            try:
                return json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
        if len(buf) > 8_000_000:
            buf = b""
    return None


def run_seat(harness_id: str, cwd: str, prompt: str, log_path: Path, env: dict[str, str]) -> int:
    argv = hx.acp_argv(harness_id)
    if harness_id in ("grok", "grok-local") and argv[:1] == [harness_id]:
        if harness_id == "grok":
            argv = ["grok", "--permission-mode", "bypassPermissions"] + argv[1:]
        else:
            # Grok Local exposes native ACP through `agent stdio`; keep the
            # ACP seat unattended just like its TUI launch.
            argv = ["grok-local", "--always-approve"] + argv[1:]
        model = str(env.get("AGENT_ROOM_MODEL") or "").strip()
        if model:
            argv[1:1] = ["--model", model]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _log(log_path, {"type": "spawn", "argv": argv, "cwd": cwd, "harness": harness_id})
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": 1,
                "clientInfo": {"name": "omarchy-agent-room", "version": "1.0.0"},
                "clientCapabilities": {"fs": {"readTextFile": True, "writeTextFile": True}},
            },
        },
    )
    init = _read_json_line(proc, 20)
    _log(log_path, {"type": "rpc", "dir": "in", "payload": init})
    if not init or init.get("error") or not init.get("result"):
        _log(log_path, {"type": "error", "message": "ACP initialize failed"})
        _close_proc(proc)
        return 2
    _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    next_id = 2
    auth_methods = init.get("result", {}).get("authMethods") or []
    if any(isinstance(method, dict) and method.get("id") == "cached_token" for method in auth_methods):
        _send(proc, {"jsonrpc": "2.0", "id": next_id, "method": "authenticate", "params": {"methodId": "cached_token"}})
        auth = _read_json_line(proc, 20)
        _log(log_path, {"type": "rpc", "dir": "in", "payload": auth})
        if not auth or auth.get("error"):
            _log(log_path, {"type": "error", "message": "ACP authentication failed"})
            _close_proc(proc)
            return 2
        next_id += 1
    session_id_request = next_id
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": session_id_request,
            "method": "session/new",
            "params": {
                "cwd": cwd,
                "mcpServers": [{
                    "name": "agent-room",
                    "command": str(Path(__file__).resolve().with_name("bin") / "agent-room"),
                    "args": ["mcp"],
                    "env": [{"name": key, "value": value} for key, value in env.items() if key.startswith("AGENT_ROOM_")],
                }],
            },
        },
    )
    session = None
    while True:
        msg = _read_json_line(proc, 20)
        if msg is None:
            break
        _log(log_path, {"type": "rpc", "dir": "in", "payload": msg})
        if _handle_server_request(proc, msg, log_path):
            continue
        if msg.get("id") == session_id_request and "result" in msg:
            session = msg["result"]
            break
        if msg.get("error") and msg.get("id") == session_id_request:
            _log(log_path, {"type": "error", "message": msg["error"]})
            _close_proc(proc)
            return 2
    session_id = ""
    if isinstance(session, dict):
        session_id = str(session.get("sessionId") or session.get("session_id") or "")
    if not session_id:
        _log(log_path, {"type": "error", "message": "ACP session/new did not return sessionId"})
        _close_proc(proc)
        return 3
    prompt_id = session_id_request + 1
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": prompt_id,
            "method": "session/prompt",
            "params": {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": prompt}],
                "_meta": {"mode": "agent"},
            },
        },
    )
    # Drain until prompt result or process exit. Keep a long window — agents work.
    idle_rounds = 0
    while idle_rounds < 600:
        msg = _read_json_line(proc, 2)
        if msg is None:
            if proc.poll() is not None:
                break
            idle_rounds += 1
            continue
        idle_rounds = 0
        _log(log_path, {"type": "rpc", "dir": "in", "payload": msg})
        if _handle_server_request(proc, msg, log_path):
            continue
        if msg.get("id") == prompt_id:
            break
    _log(log_path, {"type": "done", "returncode": proc.poll()})
    _close_proc(proc)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 4:
        print("usage: acp_host.py <harness> <cwd> <log.jsonl> <prompt>", file=sys.stderr)
        return 2
    harness_id, cwd, log, prompt = args[0], args[1], args[2], args[3]
    env = os.environ.copy()
    return run_seat(harness_id, cwd, prompt, Path(log), env)


if __name__ == "__main__":
    raise SystemExit(main())
