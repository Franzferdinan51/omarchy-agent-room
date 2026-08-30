#!/usr/bin/env bash
# Wire Agent Room into Omarchy, Grok, Codex, and Claude. No web server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN="$ROOT/bin/agent-room"
PLUGIN_ID="io.github.franzferdinan51.agent-room"
PLUGIN_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$PLUGIN_ID"

chmod +x "$ROOT/bin/agent-room" "$ROOT/bin/launch-seat"
mkdir -p "$HOME/.local/state/omarchy/agent-room"
python3 "$ROOT/agent_room.py" init >/dev/null

if [[ "$(realpath "$ROOT")" != "$(realpath "$PLUGIN_DIR" 2>/dev/null || true)" ]]; then
  mkdir -p "$(dirname "$PLUGIN_DIR")"
  rm -rf "$PLUGIN_DIR"
  mkdir -p "$PLUGIN_DIR"
  # Copy without .git internals leaking as the plugin tree; git is allowed, but
  # a live checkout is what `omarchy plugin add` produces.
  tar -C "$ROOT" -cf - --exclude .git --exclude __pycache__ --exclude .pytest_cache . \
    | tar -C "$PLUGIN_DIR" -xf -
  chmod +x "$PLUGIN_DIR/bin/agent-room" "$PLUGIN_DIR/bin/launch-seat"
  BIN="$PLUGIN_DIR/bin/agent-room"
  ROOT="$PLUGIN_DIR"
fi

omarchy plugin validate "$ROOT"
omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
omarchy plugin enable "$PLUGIN_ID" right 2>/dev/null \
  || omarchy plugin enable "$PLUGIN_ID" --section right 2>/dev/null \
  || true

mkdir -p "$HOME/.agents/skills"
rm -rf "$HOME/.agents/skills/agent-room"
cp -a "$ROOT/skills/agent-room" "$HOME/.agents/skills/agent-room"
if [[ -d $HOME/.codex ]]; then
  mkdir -p "$HOME/.codex/skills"
  rm -rf "$HOME/.codex/skills/agent-room"
  cp -a "$ROOT/skills/agent-room" "$HOME/.codex/skills/agent-room"
fi

append_mcp_toml() {
  local file="$1"
  local heading="$2"
  mkdir -p "$(dirname "$file")"
  touch "$file"
  if grep -Fq "$heading" "$file" 2>/dev/null; then
    return 0
  fi
  cat >> "$file" <<EOF

$heading
command = "$BIN"
args = ["mcp"]
enabled = true
EOF
}

append_mcp_toml "$HOME/.grok/config.toml" "[mcp_servers.agent-room]"
append_mcp_toml "$HOME/.codex/config.toml" "[mcp_servers.agent-room]"

CLAUDE_JSON="${HOME}/.claude.json"
if [[ -f $CLAUDE_JSON ]] || command -v claude >/dev/null 2>&1; then
  python3 - "$CLAUDE_JSON" "$BIN" <<'PY'
import json, os, sys
path, binary = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try:
        data = json.loads(open(path).read() or "{}")
    except json.JSONDecodeError:
        data = {}
if not isinstance(data, dict):
    data = {}
servers = data.setdefault("mcpServers", {})
if "agent-room" not in servers:
    servers["agent-room"] = {"command": binary, "args": ["mcp"]}
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
PY
fi

echo "Agent Room installed."
echo "  plugin: $PLUGIN_ID"
echo "  mcp:    $BIN mcp"
echo "Open the console: omarchy-shell shell toggle $PLUGIN_ID '{}'"
echo "Or click the Agent Room icon on the bar."
