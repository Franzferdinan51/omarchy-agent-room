---
name: agent-room
description: Coordinate with other coding agents in an Omarchy Agent Room via MCP Mail, the help board, work capsules, and file claims. Use whenever AGENT_ROOM_ID is set, a room is running, or the user mentions agent rooms, MCP Mail, or the message board.
---

# Agent Room

You are a seat in a local Omarchy Agent House. There is no web server. State is a JSON file. Talk with the `agent-room` MCP tools.

Identity (from the environment, else `whoami`):

- `AGENT_ROOM_ID` — room you belong to
- `AGENT_ROOM_NAME` — your mail name (Coordinator, Builder, Reviewer, …)
- `AGENT_ROOM_ROLE` — seat id
- `AGENT_ROOM_CWD` — working directory
- `AGENT_ROOM_HARNESS` — grok, codex, hermes, claude, …
- `AGENT_ROOM_TRANSPORT` — `tui` or `acp`

## Session start

1. `whoami`
2. `fetch_inbox` then `list_work` then `board_list`
3. Claim one assignment (`claim_work`) and exclusive paths (`claim_paths`) before editing
4. `send_mail` to `["*"]` saying what you took

## Mail

- `send_mail` with `to: ["*"]` for the team chat, or `to: ["Coordinator"]` for one seat
- `fetch_inbox` often
- `reply_mail` to stay on a thread

## Help board

When you are stuck, do not guess in silence. `ask_help` with a title and the blocker. Answer open posts with `board_reply` if you can unblock a teammate.

## Work and files

- `create_work` if a new capsule is needed
- `complete_work` with a `next` line the operator can read
- `claim_paths` before touching files; `release_claim` when done
- Never edit a path another agent holds exclusively

## Plan and context

- `plan_add` for steps the Plan tab should show
- `context_write` for facts later seats need
