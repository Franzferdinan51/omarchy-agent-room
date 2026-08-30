"""Best-effort detection of locally available agent harnesses."""
from __future__ import annotations
import shutil

CATALOG = [
    ("codex", "Codex", ["npx", "-y", "@agentclientprotocol/codex-acp"]),
    ("claude", "Claude Code", ["npx", "-y", "@agentclientprotocol/claude-agent-acp"]),
    ("hermes", "Hermes Agent", ["hermes", "acp", "--accept-hooks"]),
    ("grok", "Grok Build", ["grok", "agent", "stdio"]),
    ("gemini", "Gemini", ["gemini", "--acp"]),
    ("copilot", "Copilot", ["copilot", "--acp"]),
    ("opencode", "OpenCode", ["opencode", "acp"]),
]

def detect() -> list[dict[str, object]]:
    rows = []
    for ident, label, command in CATALOG:
        binary = shutil.which(command[0])
        rows.append({"id": ident, "label": label, "installed": bool(binary), "acp_ready": bool(binary), "command": command})
    return rows
