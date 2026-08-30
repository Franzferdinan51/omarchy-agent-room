#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import subprocess
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent_room as ar  # noqa: E402


class HouseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.house = ar.House(self.dir / "house.json")
        self.house.ensure()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_room_and_mail(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Superprompt", "Dissect SuperPrompt", str(self.dir), ["coordinator", "reviewer"], "grok")
        )
        self.assertEqual(room["name"], "Superprompt")
        self.assertEqual(len(room["roles"]), 2)
        msg = self.house.mutate(
            lambda d: ar.send_mail(d, room["id"], "Reviewer", ["*"], "Claimed", "I claimed reviewer.")
        )
        snap = self.house.snapshot()
        self.assertEqual(len(snap["mail"]), 1)
        inbox = ar.inbox_for(snap, "Coordinator", room["id"])
        self.assertEqual(len(inbox), 1)
        self.assertIn("claimed", inbox[0]["body"].lower())
        self.assertEqual(msg["from"], "Reviewer")

    def test_room_names_must_be_unique_and_slug_safe(self):
        first = self.house.mutate(
            lambda d: ar.create_room(d, "Build Team", "Ship it", str(self.dir), ["builder"], "codex")
        )
        self.assertEqual(first["slug"], "build-team")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.house.mutate(
                lambda d: ar.create_room(d, " build-team ", "Another goal", str(self.dir), ["builder"], "codex")
            )
        second = self.house.mutate(
            lambda d: ar.create_room(d, "Review Team", "Review it", str(self.dir), ["reviewer"], "codex")
        )
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.house.mutate(lambda d: ar.update_room(d, first["id"], name=second["name"].replace(" ", "-")))

    def test_room_update_rejects_empty_fields(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Draft", "Old goal", str(self.dir), ["builder"], "codex")
        )
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.house.mutate(lambda d: ar.update_room(d, room["id"], goal="   "))
        self.assertEqual(self.house.snapshot()["rooms"][0]["goal"], "Old goal")

    def test_room_workspace_is_persisted_and_editable(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Workspace Team", "Use workspace four", str(self.dir), ["builder"], "codex", workspace="4")
        )
        self.assertEqual(room["workspace"], "4")
        updated = self.house.mutate(lambda d: ar.update_room(d, room["id"], workspace="name:dev"))
        self.assertEqual(updated["workspace"], "name:dev")

    def test_stop_room_terminates_process_group_and_closes_terminal_window(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Stop Team", "Stop every seat", str(self.dir), ["builder"], "codex")
        )
        self.house.mutate(
            lambda d: ar.find_room(d, room["id"])["roles"][0].update(
                {"status": "running", "pid": 4321, "app_id": "org.omarchy.agent-room.rm-test.builder"}
            )
        )
        clients = json.dumps([{"address": "0x123", "class": "org.omarchy.agent-room.rm-test.builder"}])
        with mock.patch.object(ar.os, "getpgid", return_value=4321) as getpgid, \
             mock.patch.object(ar.os, "killpg") as killpg, \
             mock.patch.object(ar.subprocess, "check_output", return_value=clients), \
             mock.patch.object(ar.subprocess, "run") as run, \
             mock.patch.object(ar, "omarchy_version", return_value="test"), \
             mock.patch.object(ar, "process_alive", return_value=True):
            ar.stop_room(self.house, room["id"])
        getpgid.assert_called_once_with(4321)
        killpg.assert_called_once()
        self.assertIn(
            mock.call(["hyprctl", "dispatch", 'hl.dsp.window.close({ window = "address:0x123" })'], check=False, stdout=mock.ANY, stderr=mock.ANY),
            run.call_args_list,
        )

    def test_health_reports_stale_or_failed_seats(self):
        room = {"id": "rm-health", "name": "Health", "roles": [
            {"id": "builder", "name": "Builder", "status": "running", "pid": 999999},
            {"id": "reviewer", "name": "Reviewer", "status": "error", "pid": 0, "error": "adapter missing"},
        ]}
        health = ar.derive_health({"rooms": [room], "mail": [], "work": [], "claims": [], "board": []})
        titles = {item["title"] for item in health}
        self.assertIn("Seat is stale", titles)
        self.assertIn("Seat failed", titles)

    def test_board_and_work_and_claims(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Build", "Ship it", str(self.dir), ["builder", "judge"], "codex")
        )
        post = self.house.mutate(
            lambda d: ar.board_post(d, room["id"], "Builder", "Need help", "How should tests look?")
        )
        self.house.mutate(lambda d: ar.board_reply(d, post["id"], "Judge", "Keep them small."))
        work = self.house.mutate(
            lambda d: ar.create_work(d, room["id"], "Write tests", "Add unit tests", "Builder")
        )
        self.house.mutate(lambda d: ar.claim_paths(d, room["id"], "Builder", ["tests/test_house.py"]))
        snap = self.house.snapshot()
        self.assertEqual(snap["board"][0]["replies"][0]["author"], "Judge")
        self.assertEqual(snap["work"][0]["title"], work["title"])
        self.assertEqual(snap["claims"][0]["path"], "tests/test_house.py")
        self.assertTrue(any(h["title"] == "Help requested" for h in snap["health"]))

    def test_mcp_tools_call(self):
        room = ar.call_tool(
            "room_create",
            {"name": "Mailroom", "goal": "Talk", "cwd": str(self.dir), "roles": ["coordinator"]},
            self.house,
        )
        os.environ["AGENT_ROOM_ID"] = room["id"]
        os.environ["AGENT_ROOM_NAME"] = "Coordinator"
        mail = ar.call_tool("send_mail", {"body": "hello team", "to": ["*"], "subject": "hi"}, self.house)
        inbox = ar.call_tool("fetch_inbox", {}, self.house)
        self.assertEqual(mail["body"], "hello team")
        self.assertEqual(len(inbox), 1)
        help_post = ar.call_tool("ask_help", {"title": "stuck", "body": "need a second pair"}, self.house)
        posts = ar.call_tool("board_list", {}, self.house)
        self.assertEqual(posts[0]["id"], help_post["id"])

    def test_unknown_room(self):
        with self.assertRaises(KeyError):
            self.house.mutate(lambda d: ar.find_room(d, "nope"))

    def test_model_setting_and_message_reset(self):
        ar.apply_settings(self.house, {"default_harness": "codex", "default_model": "gpt-5.2-codex"})
        room = self.house.mutate(lambda d: ar.create_room(d, "Models", "Test model selection", str(self.dir), ["builder"], None))
        self.assertEqual(room["roles"][0]["model"], "gpt-5.2-codex")
        self.house.mutate(lambda d: ar.send_mail(d, room["id"], "Builder", ["*"], "hi", "hello"))
        self.assertEqual(ar.clear_messages(self.house)["cleared"], 1)
        self.assertEqual(self.house.snapshot()["mail"], [])
        ar.reset_house(self.house)
        self.assertEqual(self.house.snapshot()["rooms"], [])
        self.assertEqual(self.house.snapshot()["settings"]["default_model"], "gpt-5.2-codex")

    def test_mcp_protocol_negotiates_and_calls_tool(self):
        proc = subprocess.Popen(
            [str(ROOT / "bin/agent-room"), "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        self.addCleanup(proc.kill)

        def call(request):
            body = json.dumps(request).encode()
            proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
            proc.stdin.flush()
            headers = {}
            while True:
                line = proc.stdout.readline()
                if line in (b"\n", b"\r\n"):
                    break
                key, value = line.decode().split(":", 1)
                headers[key.lower()] = value.strip()
            return json.loads(proc.stdout.read(int(headers["content-length"])))

        initialized = call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")
        listed = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertTrue(any(tool["name"] == "send_mail" for tool in listed["result"]["tools"]))
        tool_names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertTrue({"room_update", "room_delete"}.issubset(tool_names))

    def test_edit_team_goal_and_delete_team(self):
        room = self.house.mutate(lambda d: ar.create_room(d, "Draft", "Old goal", str(self.dir), ["builder"], "codex"))
        updated = self.house.mutate(lambda d: ar.update_room(d, room["id"], "Renamed", "New goal"))
        self.assertEqual((updated["name"], updated["goal"]), ("Renamed", "New goal"))
        self.house.mutate(lambda d: ar.send_mail(d, room["id"], "Builder", ["*"], "hi", "message"))
        deleted = ar.delete_room(self.house, room["id"])
        self.assertEqual(deleted["id"], room["id"])
        self.assertEqual(self.house.snapshot()["rooms"], [])
        self.assertEqual(self.house.snapshot()["mail"], [])

    def test_mixed_harness_and_acp_seats(self):
        room = self.house.mutate(
            lambda d: ar.create_room(
                d,
                "Mix",
                "Use several CLIs",
                str(self.dir),
                ["coordinator", "builder", "judge"],
                "grok",
                {
                    "coordinator": {"harness": "grok", "transport": "tui"},
                    "builder": {"harness": "codex", "transport": "tui"},
                    "judge": {"harness": "hermes", "transport": "acp"},
                },
            )
        )
        by_id = {r["id"]: r for r in room["roles"]}
        self.assertEqual(by_id["coordinator"]["harness"], "grok")
        self.assertEqual(by_id["builder"]["harness"], "codex")
        self.assertEqual(by_id["judge"]["harness"], "hermes")
        self.assertEqual(by_id["judge"]["transport"], "acp")
        settings = ar.apply_settings(self.house, {"default_harness": "codex", "acp_enabled": True})
        self.assertEqual(settings["default_harness"], "codex")
        import harness as hx
        grok = hx.get("grok-build")
        self.assertEqual(grok["id"], "grok")
        self.assertTrue(grok["acp"])


if __name__ == "__main__":
    unittest.main()
