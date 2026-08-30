"""Coding-agent harness catalog for Omarchy Agent Room.

Each seat can run a different harness (Grok Build, Codex, Claude Code,
Hermes, …) either as a TUI in a terminal or over ACP stdio.
"""

from __future__ import annotations

import shutil
from typing import Any

HARNESSES: list[dict[str, Any]] = [
    {
        "id": "grok",
        "label": "Grok Build",
        "bin": "grok",
        "family": "xAI",
        "blurb": "Grok CLI / Grok Build",
        "argv": ["grok", "--permission-mode", "bypassPermissions"],
        "prompt_style": "dashdash",
        "acp": ["grok", "agent", "stdio"],
    },
    {
        "id": "codex",
        "label": "Codex",
        "bin": "codex",
        "family": "OpenAI",
        "blurb": "OpenAI Codex CLI",
        "argv": ["codex", "--approve-for-me"],
        "prompt_style": "dashdash",
        "acp": ["npx", "-y", "@agentclientprotocol/codex-acp"],
    },
    {
        "id": "claude",
        "label": "Claude Code",
        "bin": "claude",
        "family": "Anthropic",
        "blurb": "Anthropic Claude Code",
        "argv": ["claude", "--permission-mode", "auto"],
        "prompt_style": "dashdash",
        "acp": ["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
    },
    {
        "id": "hermes",
        "label": "Hermes",
        "bin": "hermes",
        "family": "Nous",
        "blurb": "Nous Hermes Agent — TUI, gateway, and native ACP",
        "argv": ["hermes", "--yolo"],
        "prompt_style": "hermes",
        "acp": ["hermes", "acp", "--accept-hooks"],
    },
    {
        "id": "opencode",
        "label": "OpenCode",
        "bin": "opencode",
        "family": "OpenCode",
        "blurb": "SST OpenCode",
        "argv": ["opencode", "--auto"],
        "prompt_style": "opencode",
        "acp": ["npx", "-y", "opencode-ai", "acp"],
    },
    {
        "id": "copilot",
        "label": "GitHub Copilot",
        "bin": "copilot",
        "family": "GitHub",
        "blurb": "GitHub Copilot CLI",
        "argv": ["copilot", "--allow-all"],
        "prompt_style": "copilot",
        "acp": ["copilot", "--acp"],
    },
    {
        "id": "gemini",
        "label": "Gemini CLI",
        "bin": "gemini",
        "family": "Google",
        "blurb": "Google Gemini CLI",
        "argv": ["gemini", "--yolo"],
        "prompt_style": "gemini",
        "acp": ["gemini", "--acp"],
    },
    {
        "id": "agy",
        "label": "Antigravity",
        "bin": "agy",
        "family": "Google",
        "blurb": "Google Antigravity CLI",
        "argv": ["agy"],
        "prompt_style": "dashdash",
        "acp": None,
    },
    {
        "id": "crush",
        "label": "Crush",
        "bin": "crush",
        "family": "Charm",
        "blurb": "Crush agent",
        "argv": ["crush", "--yolo"],
        "prompt_style": "crush",
        "acp": None,
    },
    {
        "id": "omp",
        "label": "Oh My Pi",
        "bin": "omp",
        "family": "Pi",
        "blurb": "Oh My Pi",
        "argv": ["omp", "--auto-approve"],
        "prompt_style": "dashdash",
        "acp": None,
    },
    {
        "id": "pi",
        "label": "Pi",
        "bin": "pi",
        "family": "Pi",
        "blurb": "Mario Zechner Pi",
        "argv": ["pi"],
        "prompt_style": "pi",
        "acp": ["npx", "-y", "pi-acp"],
    },
]

BY_ID = {h["id"]: h for h in HARNESSES}

MODEL_OPTIONS: dict[str, list[dict[str, str]]] = {
    "grok": [{"value": "", "label": "Auto (account default)"}, {"value": "grok-4.1", "label": "Grok 4.1"}, {"value": "grok-4.1-mini", "label": "Grok 4.1 Mini"}],
    "codex": [{"value": "", "label": "Auto (account default)"}, {"value": "gpt-5.2-codex", "label": "GPT-5.2 Codex"}, {"value": "gpt-5.1-codex-mini", "label": "GPT-5.1 Codex Mini"}],
    "claude": [{"value": "", "label": "Auto (account default)"}, {"value": "claude-sonnet-4-5", "label": "Claude Sonnet 4.5"}, {"value": "claude-opus-4-1", "label": "Claude Opus 4.1"}],
    "hermes": [{"value": "", "label": "Config default"}, {"value": "qwen3-coder", "label": "Qwen3 Coder"}, {"value": "deepseek-v3", "label": "DeepSeek V3"}],
    "gemini": [{"value": "", "label": "Auto (account default)"}, {"value": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"}, {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"}],
    "opencode": [{"value": "", "label": "Auto (provider default)"}, {"value": "anthropic/claude-sonnet-4-5", "label": "Claude Sonnet 4.5"}, {"value": "openai/gpt-5", "label": "GPT-5"}],
}

DEFAULT_ROLE_HARNESS = {
    "coordinator": "grok",
    "builder": "codex",
    "reviewer": "claude",
    "judge": "hermes",
    "creative-director": "grok",
}

DEFAULT_ROLE_TRANSPORT = {
    "coordinator": "tui",
    "builder": "tui",
    "reviewer": "tui",
    "judge": "acp",
    "creative-director": "tui",
}

ALIASES = {
    "grok-build": "grok",
    "grokbuild": "grok",
    "build": "grok",
    "hermes-agent": "hermes",
    "hermes-acp": "hermes",
    "antigravity": "agy",
    "gpt": "codex",
}


def normalize_id(harness_id: str) -> str:
    hid = (harness_id or "").strip().lower()
    return ALIASES.get(hid, hid or "grok")


def get(harness_id: str) -> dict[str, Any]:
    hid = normalize_id(harness_id)
    spec = BY_ID.get(hid)
    if not spec:
        path = shutil.which(hid)
        return {
            "id": hid,
            "label": hid,
            "bin": hid,
            "family": "custom",
            "blurb": "Custom harness",
            "argv": [hid],
            "prompt_style": "dashdash",
            "acp": None,
            "installed": bool(path),
            "path": path or "",
            "acp_ready": False,
        }
    item = dict(spec)
    path = shutil.which(spec["bin"])
    item["installed"] = bool(path)
    item["path"] = path or ""
    acp = spec.get("acp")
    if acp and shutil.which(acp[0]):
        item["acp_ready"] = True
    elif acp and acp[0] == "npx" and shutil.which("npx"):
        item["acp_ready"] = True
    else:
        item["acp_ready"] = False
    return item


def detect() -> list[dict[str, Any]]:
    return [get(h["id"]) for h in HARNESSES]


def launch_argv(harness_id: str, prompt: str, unattended: bool = True, model: str = "") -> list[str]:
    spec = get(harness_id)
    style = spec.get("prompt_style") or "dashdash"
    argv = list(spec.get("argv") or [spec["bin"]])
    if not unattended:
        argv = [spec["bin"]]
    if model:
        argv += ["--model", model]
    if style == "pi":
        return argv + [prompt]
    if style == "crush":
        return ["crush", "run", prompt] if prompt else argv
    if style == "gemini":
        return argv + ["--prompt-interactive", prompt]
    if style == "copilot":
        return argv + ["--interactive", prompt]
    if style == "opencode":
        return argv + ["--prompt", prompt]
    if style == "hermes":
        cmd = ["hermes"]
        if unattended:
            cmd.append("--yolo")
        return cmd + ["-z", prompt]
    return argv + ["--", prompt]


def acp_argv(harness_id: str) -> list[str]:
    spec = get(harness_id)
    acp = spec.get("acp")
    if not acp:
        raise ValueError(f"{spec['label']} has no ACP adapter")
    return list(acp)


def default_settings() -> dict[str, Any]:
    return {
        "workspace": "agent-house",
        "default_harness": "grok",
        "default_model": "",
        "mixed_harness": True,
        "default_transport": "tui",
        "role_harness": dict(DEFAULT_ROLE_HARNESS),
        "role_transport": dict(DEFAULT_ROLE_TRANSPORT),
        "auto_brief": True,
        "poll_ms": 4000,
        "notify_board": True,
        "launch_unattended": True,
        "show_help_board": True,
        "show_seat_harness": True,
        "hermes_enabled": True,
        "hermes_gateway": False,
        "acp_enabled": True,
        "acp_auto_prompt": True,
    }


def merge_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_settings()
    if not isinstance(raw, dict):
        return base
    for key, value in raw.items():
        if key in ("role_harness", "role_transport") and isinstance(value, dict):
            merged = dict(base[key])
            for rk, rv in value.items():
                merged[str(rk)] = str(rv)
            base[key] = merged
        elif key in base:
            base[key] = value
    return base


def resolve_seat_harness(settings: dict[str, Any], role_id: str, explicit: str | None = None) -> str:
    if explicit:
        return get(explicit)["id"]
    roles = settings.get("role_harness") or {}
    if role_id in roles:
        return get(str(roles[role_id]))["id"]
    return get(str(settings.get("default_harness") or "grok"))["id"]


def resolve_transport(settings: dict[str, Any], role_id: str, explicit: str | None = None) -> str:
    if explicit in ("tui", "acp"):
        return explicit
    roles = settings.get("role_transport") or {}
    if role_id in roles and roles[role_id] in ("tui", "acp"):
        return str(roles[role_id])
    dt = settings.get("default_transport") or "tui"
    return dt if dt in ("tui", "acp") else "tui"
