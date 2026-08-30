#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
