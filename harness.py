"""Best-effort detection of locally available agent harnesses."""
from __future__ import annotations
import shutil
import sys
import os
from pathlib import Path


STANDALONE_ROOT = Path(
    os.environ.get(
        "MACH_CLI_ROOT",
        Path(__file__).resolve().parent.parent / "Franzferdinan51" / "MultiAgentCli",
    )
).expanduser().resolve()

CATALOG = [
    ("multi-agent-cli", "MultiAgentCli (LM Studio)", [sys.executable, "-m", "multi_agent_cli.cli"]),
    ("codex", "Codex", ["npx", "-y", "@agentclientprotocol/codex-acp"]),
    ("claude", "Claude Code", ["npx", "-y", "@agentclientprotocol/claude-agent-acp"]),
    ("hermes", "Hermes Agent", ["hermes", "acp", "--accept-hooks"]),
    ("grok", "Grok Build", ["grok", "agent", "stdio"]),
    ("gemini", "Gemini", ["gemini", "--acp"]),
    ("copilot", "Copilot", ["copilot", "--acp"]),
    ("opencode", "OpenCode", ["opencode", "acp"]),
]


def local_cli_command() -> tuple[list[str], dict[str, str]]:
    """Return the standalone mach entrypoint and environment for local use."""
    env = {}
    if STANDALONE_ROOT.is_dir():
        env["PYTHONPATH"] = str(STANDALONE_ROOT)
    return [sys.executable, "-m", "multi_agent_cli.cli"], env

def detect() -> list[dict[str, object]]:
    rows = []
    for ident, label, command in CATALOG:
        installed = STANDALONE_ROOT.is_dir() if ident == "multi-agent-cli" else bool(shutil.which(command[0]))
        rows.append({"id": ident, "label": label, "installed": installed, "acp_ready": installed, "command": command})
    return rows
