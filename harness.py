"""Coding-agent harness catalog for Omarchy Agent Room.

Each seat can run a different harness (Grok Build, Codex, Claude Code,
Hermes, …) either as a TUI in a terminal or over ACP stdio.
"""

from __future__ import annotations

import shutil
import json
import os
import re
import sys
import tomllib
from urllib import request as urlrequest
from pathlib import Path
from typing import Any

HARNESSES: list[dict[str, Any]] = [
    {
        "id": "multi-agent-cli",
        "label": "MultiAgentCli (LM Studio)",
        "bin": sys.executable,
        "family": "Local",
        "blurb": "Standalone local-first MultiAgentCli powered by LM Studio and SearXNG",
        "argv": [sys.executable, "-m", "multi_agent_cli.cli"],
        "prompt_style": "multi-agent-cli",
        "acp": None,
    },
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


def standalone_root() -> Path:
    return Path(
        os.environ.get(
            "MACH_CLI_ROOT",
            Path(__file__).resolve().parent.parent / "Franzferdinan51" / "MultiAgentCli",
        )
    ).expanduser().resolve()


def lmstudio_default_model() -> str:
    """Return the first usable text model exposed by the local LM Studio API."""
    configured = os.environ.get("MACH_LMSTUDIO_MODEL", "").strip()
    if configured:
        return configured
    base = os.environ.get("MACH_LMSTUDIO_URL", "http://localhost:1234/v1").rstrip("/")
    try:
        with urlrequest.urlopen(f"{base}/models", timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        candidates = []
        for item in data.get("data", []):
            model_id = str(item.get("id", "")).strip()
            lowered = model_id.lower()
            if model_id and "embed" not in lowered and "rerank" not in lowered:
                match = re.search(r"(\d+(?:\.\d+)?)b\b", lowered)
                size = float(match.group(1)) if match else 9999.0
                candidates.append((size, model_id))
        if candidates:
            return min(candidates)[1]
    except (OSError, ValueError, TypeError):
        pass
    return "local-model"


def lmstudio_model_options() -> list[dict[str, str]]:
    """Return selectable LM Studio generation models for the native console."""
    options = [{"value": "", "label": "Auto (LM Studio)"}]
    base = os.environ.get("MACH_LMSTUDIO_URL", "http://localhost:1234/v1").rstrip("/")
    try:
        with urlrequest.urlopen(f"{base}/models", timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        for item in data.get("data", []):
            model_id = str(item.get("id", "")).strip()
            lowered = model_id.lower()
            if model_id and "embed" not in lowered and "rerank" not in lowered:
                options.append({"value": model_id, "label": f"LM Studio · {model_id}"})
    except (OSError, ValueError, TypeError):
        pass
    return options


def model_options() -> list[dict[str, str]]:
    """Combine local LM Studio models with the legacy configured catalog."""
    options = lmstudio_model_options()
    seen = {item["value"] for item in options}
    for item in grok_model_options():
        if item["value"] not in seen:
            options.append(item)
            seen.add(item["value"])
    return options

MODEL_OPTIONS: dict[str, list[dict[str, str]]] = {
    "grok": [{"value": "", "label": "Auto (account default)"}, {"value": "grok-4.1", "label": "Grok 4.1"}, {"value": "grok-4.1-mini", "label": "Grok 4.1 Mini"}],
    "codex": [{"value": "", "label": "Auto (account default)"}, {"value": "gpt-5.2-codex", "label": "GPT-5.2 Codex"}, {"value": "gpt-5.1-codex-mini", "label": "GPT-5.1 Codex Mini"}],
    "claude": [{"value": "", "label": "Auto (account default)"}, {"value": "claude-sonnet-4-5", "label": "Claude Sonnet 4.5"}, {"value": "claude-opus-4-1", "label": "Claude Opus 4.1"}],
    "hermes": [{"value": "", "label": "Config default"}, {"value": "qwen3-coder", "label": "Qwen3 Coder"}, {"value": "deepseek-v3", "label": "DeepSeek V3"}],
    "gemini": [{"value": "", "label": "Auto (account default)"}, {"value": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"}, {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"}],
    "opencode": [{"value": "", "label": "Auto (provider default)"}, {"value": "anthropic/claude-sonnet-4-5", "label": "Claude Sonnet 4.5"}, {"value": "openai/gpt-5", "label": "GPT-5"}],
}

def grok_model_options() -> list[dict[str, str]]:
    """Read Grok's configured and cached models, including custom providers."""
    found: dict[str, str] = {}
    config = Path(os.environ.get("GROK_HOME", Path.home() / ".grok")) / "config.toml"
    try:
        parsed = tomllib.loads(config.read_text(encoding="utf-8"))
        for key, spec in (parsed.get("model") or {}).items():
            if isinstance(spec, dict):
                found[str(spec.get("model") or key)] = str(spec.get("name") or key)
    except (OSError, tomllib.TOMLDecodeError):
        pass
    cache = config.parent / "models_cache.json"
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
        for key, entry in (data.get("models") or {}).items():
            info = entry.get("info") if isinstance(entry, dict) else {}
            model_id = str(info.get("model") or key)
            if model_id and not info.get("hidden", False):
                found[model_id] = str(info.get("name") or model_id)
    except (OSError, json.JSONDecodeError):
        pass
    options = [{"value": "", "label": "Auto (Grok default)"}]
    options.extend({"value": model_id, "label": label} for model_id, label in sorted(found.items(), key=lambda item: item[1].lower()))
    return options

DEFAULT_ROLE_HARNESS = {
    "coordinator": "multi-agent-cli",
    "builder": "multi-agent-cli",
    "reviewer": "multi-agent-cli",
    "judge": "multi-agent-cli",
    "creative-director": "multi-agent-cli",
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
    path = str(Path(spec["bin"]).resolve()) if hid == "multi-agent-cli" and standalone_root().is_dir() else shutil.which(spec["bin"])
    item["installed"] = bool(path)
    item["path"] = path or ""
    acp = spec.get("acp")
    if hid == "multi-agent-cli":
        item["installed"] = standalone_root().is_dir()
        item["path"] = str(standalone_root()) if item["installed"] else ""
        item["acp_ready"] = False
    elif acp and shutil.which(acp[0]):
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
    if normalize_id(harness_id) == "multi-agent-cli":
        # The standalone harness is a one-shot local agent, so a room seat
        # runs its goal through LM Studio and exits cleanly.
        argv += ["run", "--agents", "lmstudio", "--no-progress", "--json"]
        argv += ["--model", model or lmstudio_default_model()]
        return argv + ["--goal", prompt]
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
        "workspace": "current",
        "default_harness": "multi-agent-cli",
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
        "telegram_enabled": False,
        "telegram_team": "",
        "telegram_auto_approve": False,
        "telegram_notify_progress": True,
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
    return get(str(settings.get("default_harness") or "multi-agent-cli"))["id"]


def resolve_transport(settings: dict[str, Any], role_id: str, explicit: str | None = None) -> str:
    if explicit in ("tui", "acp"):
        return explicit
    roles = settings.get("role_transport") or {}
    if role_id in roles and roles[role_id] in ("tui", "acp"):
        return str(roles[role_id])
    dt = settings.get("default_transport") or "tui"
    return dt if dt in ("tui", "acp") else "tui"
