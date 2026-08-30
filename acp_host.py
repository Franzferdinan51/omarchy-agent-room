#!/usr/bin/env python3
"""Drive one Agent Room seat over ACP stdio (newline-delimited JSON-RPC).

Spawns the harness ACP adapter, initializes a session, sends the briefing
prompt, and appends session/update events to a jsonl log the console tails.
No HTTP server.
"""

from __future__ import annotations

import json
import os
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


def _read_json_line(proc: subprocess.Popen, timeout: float = 30.0) -> dict[str, Any] | None:
    assert proc.stdout is not None
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        if proc.poll() is not None and not buf:
            return None
        ch = proc.stdout.read(1)
        if not ch:
            time.sleep(0.02)
            continue
        if ch in (b"\n", b"\r"):
            if not buf:
                continue
            try:
                return json.loads(buf.decode("utf-8"))
            except json.JSONDecodeError:
                buf = b""
                continue
        buf += ch
        if len(buf) > 8_000_000:
            buf = b""
    return None


def run_seat(harness_id: str, cwd: str, prompt: str, log_path: Path, env: dict[str, str]) -> int:
    argv = hx.acp_argv(harness_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _log(log_path, {"type": "spawn", "argv": argv, "cwd": cwd, "harness": harness_id})
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
                "capabilities": {"fs": {"readTextFile": True, "writeTextFile": True}},
            },
        },
    )
    init = _read_json_line(proc, 20)
    _log(log_path, {"type": "rpc", "dir": "in", "payload": init})
    _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "session/new",
            "params": {"cwd": cwd, "mcpServers": []},
        },
    )
    session = None
    while True:
        msg = _read_json_line(proc, 20)
        if msg is None:
            break
        _log(log_path, {"type": "rpc", "dir": "in", "payload": msg})
        if msg.get("id") == 2 and "result" in msg:
            session = msg["result"]
            break
        if msg.get("error") and msg.get("id") == 2:
            _log(log_path, {"type": "error", "message": msg["error"]})
            proc.terminate()
            return 2
    session_id = ""
    if isinstance(session, dict):
        session_id = str(session.get("sessionId") or session.get("session_id") or "")
    if not session_id:
        _log(log_path, {"type": "error", "message": "ACP session/new did not return sessionId"})
        proc.terminate()
        return 3
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "session/prompt",
            "params": {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": prompt}],
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
        if msg.get("id") == 3:
            break
    _log(log_path, {"type": "done", "returncode": proc.poll()})
    if proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass
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
