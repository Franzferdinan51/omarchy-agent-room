# Telegram Connector Implementation Plan

## Goal

Deliver a secure, testable Telegram connector integrated with Agent Room teams and Settings, then verify and push sanitized changes to `main`.

## Work items

1. Extend connector/state boundaries
   - Add token storage helpers using `secret-tool` with a strict-permission fallback.
   - Add Telegram configuration defaults and masked status to snapshots.
   - Add Bot API client, webhook cleanup, long polling, offset persistence, backoff, locking, and clean shutdown.
   - Add pairing state and team/chat routing without exposing credentials.

2. Add Agent Room operations
   - Add connector lifecycle commands and MCP operations.
   - Add inbound routing and Telegram reply operations.
   - Ensure reset/clear operations do not accidentally leak or delete credentials unless explicitly requested.

3. Add Settings UI
   - Add masked token entry and lifecycle controls.
   - Add team selection, pairing controls, diagnostics, and safe forget behavior.
   - Keep the QML snapshot token-free and refresh status after each operation.

4. Test first and verify
   - Add fake Bot API tests for validation, polling, offset, retry, malformed input, pairing, routing, and stop.
   - Add settings and CLI tests.
   - Run the full suite and scan tracked files for token-like values, personal paths, chat IDs, and generated state.

5. Document and release
   - Update README with setup, keyring fallback, pairing, routing, troubleshooting, and removal steps.
   - Sync only source files to the registered live plugin.
   - Verify version, Settings visibility, connector lifecycle, and no credential leakage.
   - Commit and push to `origin/main`.

## Privacy gate

Before commit, inspect `git diff --cached` and `git status --short`. Never stage `.grok/`, local state, logs, token files, test secrets, personal paths, or identifiers. Use placeholders in fixtures and documentation.
