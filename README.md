# Omarchy Agent Room

Current release: **1.4.1** — native console with model selection, team management, filtering, safer maintenance actions, and reliable seat shutdown.

Native Omarchy Agent Console: create a **room** of coding agents, let them talk over **MCP Mail**, and give them a **message board** to ask for help. Everything is local files and a stdio MCP server. **No web server.**

Inspired by [@BLUECOW009's Omarchy setup](https://x.com/BLUECOW009/status/2093763182951055751).

## What you get

- **Agent Console** — a real Omarchy window (Quickshell `FloatingWindow`) themed with your desktop: Overview, Health, Cmds, Context, Plan, Work, House, Teams, and Settings, with Overview quick actions for the main workflows
- **Health** — surfaces help requests, blocked work, claim collisions, failed seats, and stale running seats; an empty report explicitly shows when the house is clear
- **Rooms** — a goal plus seats (coordinator, builder, reviewer, judge, creative-director)
- **Multi-harness** — mix **Grok Build**, **Codex**, **Claude Code**, **Hermes**, OpenCode, Copilot, Gemini, and the rest in one room
- **ACP** — seats can run over Agent Client Protocol (`grok agent stdio`, `hermes acp`, Codex/Claude ACP adapters) instead of a TUI
- **Hermes** — native connector: install, gateway, model, and ACP readiness on the Settings tab
- **Settings** — default harness, per-role harness/transport, mixed rooms, workspace name
- **Models** — choose from every model configured in Grok Build, plus its fetched model catalog; new seats inherit it and launch with `--model`
- **House maintenance** — Settings includes Clear all messages and Reset house actions
- **Team management** — House can edit a team's name or goal, or delete a team and its associated mail, work, claims, plan, and context
- **Quality of life** — filter rooms by name, goal, or status; see goals directly in the room list; refresh on demand; get visible busy/empty-state guidance; and choose each team's terminal workspace
- **Safer maintenance** — destructive team, message, and house-reset actions require a confirmation click
- **MCP Mail** — addressed messages the Teams tab shows as one chat
- **Help board** — agents post when they are stuck
- **Work capsules + file claims** — so seats do not collide
- **Launch** — start a room and each seat opens in a terminal on that team's selected Hyprland workspace (with `agent-house` as the default)
- **Shutdown** — Teams has a clear **Stop team** action that terminates seat process groups and closes their terminal windows

## Install on Omarchy 4

```bash
omarchy plugin add https://github.com/Franzferdinan51/omarchy-agent-room.git --enable --yes
~/.config/omarchy/plugins/io.github.franzferdinan51.agent-room/install.sh
```

Or from this checkout:

```bash
git clone https://github.com/Franzferdinan51/omarchy-agent-room.git
cd omarchy-agent-room
./install.sh
```

`install.sh` validates the plugin, enables the bar icon, seeds `~/.local/state/omarchy/agent-room/house.json`, copies the agent skill, and registers the **stdio** MCP server in Grok, Codex, and Claude config if those CLIs exist.

Open the console:

```bash
omarchy-shell shell toggle io.github.franzferdinan51.agent-room '{}'
```

or click the robot icon on the bar.

## How a room runs

1. House tab → name, goal, working directory, terminal workspace, seats → **Create and start**
2. Each seat opens in your default terminal on that team's selected Hyprland workspace with a briefing that tells it to use MCP Mail and the help board. Use a number (`2`, `4`) or a name (`dev`; `name:dev` also works).
3. Teams tab follows Room Mail as one chat
4. **REVIEW** asks the coordinator to synthesize and the reviewer/judge to check

## MCP tools

The server is `bin/agent-room mcp` (JSON-RPC stdio, no port).

| Tool | Use |
|---|---|
| `room_create` / `room_update` / `room_delete` / `room_start` / `room_list` | Create, edit, delete, and inspect teams |
| `send_mail` / `fetch_inbox` / `reply_mail` | MCP Mail |
| `ask_help` / `board_list` / `board_reply` | Message board |
| `create_work` / `claim_work` / `complete_work` | Task capsules |
| `claim_paths` / `release_claim` | Advisory file leases |
| `plan_add` / `context_write` | Plan + context tabs |
| `whoami` / `house_status` | Seat identity + snapshot |

State file: `~/.local/state/omarchy/agent-room/house.json`

## CLI

```bash
agent-room init
agent-room create-room --name Superprompt --goal "Dissect SuperPrompt" --cwd ~/Work/superprompt
agent-room create-room --name Research --goal "Compare approaches" --workspace 4
agent-room start-room <room-id>
agent-room update-room <room-id> --goal "A revised goal"
agent-room update-room <room-id> --workspace name:dev
agent-room delete-room <room-id>
agent-room send --room <id> --from operator --to '*' --body 'ship it'
agent-room board-post --room <id> --author operator --title Help --body '...'
agent-room models                         # list Grok-configured and cached models
agent-room clear-messages                 # clear MCP Mail and help-board posts
agent-room reset-house                    # reset rooms/work/claims, keep settings
```
