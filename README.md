# Omarchy Agent Room

Native Omarchy Agent Console: create a **room** of coding agents, let them talk over **MCP Mail**, and give them a **message board** to ask for help. Everything is local files and a stdio MCP server. **No web server.**

Inspired by [@BLUECOW009's Omarchy setup](https://x.com/BLUECOW009/status/2093763182951055751).

## What you get

- **Agent Console** — a real Omarchy window (Quickshell `FloatingWindow`) themed with your desktop: Overview, Health, Cmds, Context, Plan, Work, House, Teams, Settings
- **Rooms** — a goal plus seats (coordinator, builder, reviewer, judge, creative-director)
- **Multi-harness** — mix **Grok Build**, **Codex**, **Claude Code**, **Hermes**, OpenCode, Copilot, Gemini, and the rest in one room
- **MultiAgentCli bridge** — use the standalone LM Studio-first `mach` harness as the default local seat backend; the standalone CLI remains independently usable
- **ACP** — seats can run over Agent Client Protocol (`grok agent stdio`, `hermes acp`, Codex/Claude ACP adapters) instead of a TUI
- **Hermes** — native connector: install, gateway, model, and ACP readiness on the Settings tab
- **Settings** — default harness, per-role harness/transport, mixed rooms, workspace name
- **MCP Mail** — addressed messages the Teams tab shows as one chat
- **Help board** — agents post when they are stuck
- **Work capsules + file claims** — so seats do not collide
- **Launch** — start a room and each seat opens in a terminal on the `agent-house` Hyprland workspace

## Install on Omarchy 4

```bash
omarchy plugin add https://github.com/Franzferdinan51/omarchy-agent-room.git --enable --yes
~/.config/omarchy/plugins/io.github.franzferdinan51.agent-room/install.sh
```

Local checkout (this is what this machine runs):

```bash
cd ~/Projects/omarchy-agent-room && ./install.sh
```

Open: `omarchy-shell shell toggle io.github.franzferdinan51.agent-room '{}'` or the Agent Room icon on the bar. The console includes a Settings tab for the default harness, seat workspace, and compact navigation preference.

### LM Studio via MultiAgentCli

The room can delegate a seat goal to the standalone harness without copying or
replacing it. From this checkout:

```bash
./bin/agent-room run-local "Review this project and list the top risks" --model ornith-1.5-9b
```

The bridge uses `MACH_LMSTUDIO_URL` when set and discovers the sibling checkout
at `~/Franzferdinan51/MultiAgentCli`. Set `PYTHONPATH` or adjust
`harness.py` if the standalone checkout lives elsewhere. The MCP server also
exposes `run_local_agent` for connected seats.

## Transports

| Mode | What happens |
|---|---|
| **TUI** | Seat opens in your default terminal via `omarchy-launch-tui` |
| **ACP** | Seat is driven over Agent Client Protocol stdio (`acp_host.py`) |

ACP commands used:
- Grok Build: `grok agent stdio`
- Hermes: `hermes acp --accept-hooks`
- Codex: `npx -y @agentclientprotocol/codex-acp`
- Claude Code: `npx -y @agentclientprotocol/claude-agent-acp`
- Gemini: `gemini --acp`
- Copilot: `copilot --acp`

Per-seat example:

```bash
agent-room create-room --name Mix --goal "Ship it" \
  --seat coordinator=grok:tui --seat builder=codex:tui --seat judge=hermes:acp
agent-room set-seat <room> builder --harness grok --transport acp --restart
```
