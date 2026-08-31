"""Live connectors: Telegram, Hermes Agent, and ACP adapter readiness."""

from __future__ import annotations

import shutil
import subprocess
import json
import os
import time
from urllib import error as urlerror
from urllib import parse, request
from pathlib import Path
from typing import Any

import harness as hx

TELEGRAM_SERVICE = "omarchy-agent-room-telegram"
TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_TIMEOUT = 35
TELEGRAM_MAX_TEXT = 3900


def _state_dir(state_path: Path | None = None) -> Path:
    return (state_path or (Path.home() / ".local/state/omarchy/agent-room/house.json")).parent


def _token_path(state_path: Path | None = None) -> Path:
    return _state_dir(state_path) / "telegram.token"


def _secret_tool() -> str | None:
    return shutil.which("secret-tool")


def telegram_token_configured(state_path: Path | None = None) -> bool:
    token = telegram_get_token(state_path)
    return bool(token)


def telegram_get_token(state_path: Path | None = None) -> str:
    tool = _secret_tool()
    if tool:
        try:
            result = subprocess.run(
                [tool, "lookup", "service", TELEGRAM_SERVICE, "account", os.environ.get("USER", "agent")],
                capture_output=True, text=True, timeout=4,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    path = _token_path(state_path)
    try:
        if path.stat().st_mode & 0o077:
            path.chmod(0o600)
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def telegram_set_token(token: str, state_path: Path | None = None) -> dict[str, Any]:
    token = token.strip()
    if not token or len(token) > 512 or any(ch.isspace() for ch in token):
        raise ValueError("Enter a valid Telegram bot token")
    tool = _secret_tool()
    account = os.environ.get("USER", "agent")
    if tool:
        try:
            result = subprocess.run(
                [tool, "store", "--label", "Agent Room Telegram bot", "service", TELEGRAM_SERVICE, "account", account],
                input=token, capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return {"configured": True, "storage": "keyring"}
        except (OSError, subprocess.SubprocessError):
            pass
    path = _token_path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    path.chmod(0o600)
    return {"configured": True, "storage": "protected-file"}


def telegram_forget_token(state_path: Path | None = None) -> dict[str, Any]:
    tool = _secret_tool()
    account = os.environ.get("USER", "agent")
    if tool:
        try:
            subprocess.run([tool, "clear", "service", TELEGRAM_SERVICE, "account", account], capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
    path = _token_path(state_path)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise RuntimeError(f"Could not remove Telegram token: {exc}") from exc
    return {"configured": False}


def _telegram_request(token: str, method: str, params: dict[str, Any] | None = None, timeout: int = TELEGRAM_TIMEOUT) -> dict[str, Any]:
    body = parse.urlencode({k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in (params or {}).items()}).encode()
    req = request.Request(f"{TELEGRAM_API}/bot{token}/{method}", data=body, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urlerror.URLError) as exc:
        raise RuntimeError(f"Telegram {method} request failed: {exc}") from exc
    if not data.get("ok"):
        raise RuntimeError(str(data.get("description") or f"Telegram {method} failed"))
    return data


def telegram_test(state_path: Path | None = None) -> dict[str, Any]:
    token = telegram_get_token(state_path)
    if not token:
        return {"configured": False, "status": "disconnected", "error": "No bot token configured"}
    try:
        bot = _telegram_request(token, "getMe", timeout=10).get("result") or {}
        return {"configured": True, "status": "ready", "bot": {"id": bot.get("id"), "username": bot.get("username", ""), "name": bot.get("first_name", "")}, "storage": "keyring" if _secret_tool() else "protected-file"}
    except RuntimeError as exc:
        return {"configured": True, "status": "error", "error": str(exc)}


def telegram_send(text: str, chat_id: str | int, state_path: Path | None = None) -> dict[str, Any]:
    token = telegram_get_token(state_path)
    if not token:
        raise RuntimeError("No Telegram bot token configured")
    text = str(text).strip()
    if not text:
        raise ValueError("Telegram message cannot be empty")
    result = _telegram_request(token, "sendMessage", {"chat_id": chat_id, "text": text[:TELEGRAM_MAX_TEXT]})
    return result.get("result") or {}


def telegram_delete_webhook(state_path: Path | None = None) -> dict[str, Any]:
    token = telegram_get_token(state_path)
    if not token:
        raise RuntimeError("No Telegram bot token configured")
    return _telegram_request(token, "deleteWebhook", {"drop_pending_updates": False})


def telegram_status(state_path: Path | None = None) -> dict[str, Any]:
    configured = telegram_token_configured(state_path)
    status: dict[str, Any] = {
        "configured": configured,
        "status": "configured" if configured else "disconnected",
        "storage": "keyring" if _secret_tool() else "protected-file",
    }
    pid_path = _state_dir(state_path) / "telegram.pid"
    pid = 0
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        status["polling"] = True
        status["pid"] = pid
    except (OSError, ValueError):
        status["polling"] = False
        status["pid"] = 0
    status["token_hint"] = "configured" if configured else "not configured"
    return status


def telegram_poll(token: str, offset: int = 0) -> list[dict[str, Any]]:
    result = _telegram_request(token, "getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": json.dumps(["message"])}, timeout=35)
    return result.get("result") or []


def _read_yaml_model(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model:") or line.strip().startswith("model:"):
                value = line.split(":", 1)[1].strip().strip("\"'")
                return value
    except OSError:
        return ""
    return ""


def hermes_status() -> dict[str, Any]:
    binary = shutil.which("hermes") or shutil.which("hermes-agent")
    installed = bool(binary)
    version = ""
    if binary:
        try:
            version = subprocess.check_output(
                [binary, "--version"], text=True, stderr=subprocess.DEVNULL, timeout=5
            ).strip().splitlines()[0]
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            version = ""
    gateway = "unknown"
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", "hermes-gateway.service"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0:
            gateway = "active"
        else:
            e = subprocess.run(
                ["systemctl", "--user", "is-enabled", "hermes-gateway.service"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            gateway = "stopped" if e.returncode == 0 else "not-installed"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        gateway = "unknown"

    home = Path.home() / ".hermes"
    model = _read_yaml_model(home / "config.yaml") or _read_yaml_model(home / "profile.yaml")
    acp_ok = bool(binary)

    return {
        "installed": installed,
        "path": binary or "",
        "version": version,
        "gateway": gateway,
        "model": model,
        "home": str(home) if home.is_dir() else "",
        "acp": acp_ok,
        "label": "Hermes Agent",
    }


def acp_catalog() -> list[dict[str, Any]]:
    """Return the detected ACP adapters with their actual launch commands."""
    rows = []
    for spec in hx.detect():
        acp = spec.get("acp")
        rows.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "installed": spec["installed"],
                "acp_ready": bool(spec.get("acp_ready")),
                "acp_command": " ".join(acp) if acp else "",
            }
        )
    return rows
