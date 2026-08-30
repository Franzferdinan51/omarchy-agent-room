# Telegram Connector for Agent Room

## Status

Approved direction; pending implementation-spec review.

## Goal

Add Telegram as a first-class Agent Room connector. A Telegram chat is paired with an Agent Room team, incoming messages are delivered to that team, and the team can send replies through the connector. The feature must be controllable from Settings and must not commit credentials or machine-specific data.

## Design

### Connector service

Implement the Telegram Bot API integration in `connectors.py` using Python's standard library HTTP client. Keep it independent of the QML process so polling survives UI refreshes and can be stopped reliably. The service will:

- validate credentials with `getMe`;
- clear an existing webhook before long polling;
- persist the Telegram update offset in Agent Room state;
- use bounded request timeouts and exponential reconnect backoff;
- expose masked status and diagnostics, never the token;
- stop cleanly and avoid duplicate pollers.

The connector process will be managed by Agent Room commands and use a lock/pid record under the existing local state directory. Stale records will be detected without killing unrelated processes.

### Secret storage

The token will not be stored in `house.json`, QML properties, logs, README files, test fixtures, or Git history. Prefer the desktop `secret-tool` keyring when available. If unavailable, use a user-only (`0600`) token file under Agent Room's state directory and show that the fallback is active in diagnostics. Settings and snapshots only expose `configured: true/false` and a masked suffix when appropriate.

### Pairing and commands

Unknown chats are denied by default and receive a short pairing instruction. The Settings tab will list pending requests and allow approve, deny, or revoke. Store only the minimum chat metadata required for routing.

Support safe connector commands:

- `/start` and `/help` for onboarding;
- `/whoami` for the chat identity used in pairing;
- `/status` for connector/team status;
- `/cancel` for cancelling the active request where supported.

Auto-approval is disabled by default and requires an explicit Settings toggle.

### Agent Room routing

Settings will select a default Telegram team/room. An approved chat can optionally be mapped to a different team. Incoming messages are recorded as connector events and delivered to the selected team. A new connector reply operation will send text and bounded progress updates back to the originating Telegram chat while preserving room identity and auditability.

### Settings UI

Add a Telegram section to the existing Settings tab with:

- masked bot-token input;
- Save/Test, Connect, Pause, Reconnect, and Forget buttons;
- connection state, bot username, last update, and error diagnostics;
- default team selector;
- pending/approved chat management;
- auto-approval and notification options.

Destructive actions require the same confirmation pattern already used by Settings maintenance actions.

### Reliability and safety

All Telegram text is treated as untrusted input. Replies are escaped/limited to Telegram-safe lengths, polling handles rate limits and transient network errors, and malformed updates are ignored with a diagnostic entry rather than crashing the connector. Stop operations terminate the connector process and its child process group, matching the existing team shutdown behavior.

### Testing

Add deterministic tests with a local fake Bot API server for:

- token validation and token redaction;
- webhook cleanup and polling offset persistence;
- pairing approval/deny/revoke;
- malformed updates, rate limits, reconnect backoff, and clean stop;
- routing to the selected team and reply delivery;
- Settings patches and connector lifecycle commands.

Run the full existing test suite, a source diff scan for credential-like data, and a clean build/live-plugin sync check before committing. Only source, documentation, and tests will be pushed; local state, `.grok/`, tokens, logs, and personal identifiers remain untracked.

## Alternatives considered

The original Electron implementation launches Telegram around a desktop-specific runtime and uses Electron `safeStorage`. Those pieces cannot be copied directly into the Python/Quickshell Agent Room architecture. A separate direct Grok Build CLI responder was also considered, but routing through Agent Room keeps Telegram aligned with rooms, teams, health, audit logs, and existing stop controls.

## Rollout

The feature will default to disconnected and deny unknown chats. Existing installations remain unchanged until a token is configured. README documentation will explain setup, keyring fallback, pairing, troubleshooting, and how to remove all Telegram state.
