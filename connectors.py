"""Live connectors: Hermes Agent status and ACP adapter readiness."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import harness as hx


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
    rows = []
    for spec in hx.detect():
        acp = spec.get("command")
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
