# Agent Room

This directory is an Omarchy 4 shell plugin (`io.github.franzferdinan51.agent-room`) plus a stdio MCP server.

- Do not add an HTTP server. State is `~/.local/state/omarchy/agent-room/house.json`.
- `agent_room.py` is CLI + MCP. `bin/agent-room` is the wrapper.
- `Console.qml` is the native window. `BarWidget.qml` is the bar icon.
- After QML or Python changes, run `omarchy plugin validate .` and `omarchy-shell shell rescanPlugins`.
- Tests: `python3 tests/test_house.py`
