#!/usr/bin/env python3
from __future__ import annotations

import json
import io
import os
import sys
import tempfile
import unittest
import subprocess
import time
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent_room as ar  # noqa: E402
import connectors  # noqa: E402
import acp_host  # noqa: E402
import harness  # noqa: E402


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

    def test_telegram_token_is_not_in_house_snapshot(self):
        with mock.patch.object(connectors, "_secret_tool", return_value=None):
            result = connectors.telegram_set_token("fixture-token-value", self.house.path)
            self.assertEqual(result["storage"], "protected-file")
            self.assertTrue((self.dir / "telegram.token").stat().st_mode & 0o077 == 0)
            snapshot = self.house.snapshot()
            self.assertNotIn("fixture-token-value", json.dumps(snapshot))
            self.assertTrue(snapshot["telegram_status"]["configured"])

    def test_telegram_approved_chat_routes_to_selected_team(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Telegram Team", "Handle remote requests", str(self.dir), ["coordinator"], "grok")
        )
        self.house.mutate(lambda d: d["settings"].update(telegram_team=room["id"]))
        self.house.mutate(lambda d: d["telegram"].update(approved=[{"chat_id": "42", "username": "tester"}]))
        with mock.patch.object(connectors, "telegram_send"):
            msg = ar.telegram_route_update(self.house, {"update_id": 7, "message": {"chat": {"id": 42}, "from": {"username": "tester"}, "text": "Please check status"}})
        self.assertEqual(msg["room_id"], room["id"])
        self.assertEqual(msg["from"], "telegram:tester")
        self.assertEqual(msg["thread_id"], "telegram:42")

    def test_telegram_unknown_chat_is_queued_and_not_delivered(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Pairing Team", "Handle paired requests", str(self.dir), ["coordinator"], "grok")
        )
        self.house.mutate(lambda d: d["settings"].update(telegram_team=room["id"]))
        with mock.patch.object(connectors, "telegram_send") as send:
            self.assertIsNone(ar.telegram_route_update(self.house, {"update_id": 8, "message": {"chat": {"id": 99}, "from": {"first_name": "New"}, "text": "Hello"}}))
        self.assertEqual(len(self.house.load()["mail"]), 0)
        self.assertEqual(self.house.load()["telegram"]["pending"][0]["chat_id"], "99")
        send.assert_called_once()

    def test_acp_host_completes_initialize_session_and_prompt(self):
        fake = self.dir / "fake_acp.py"
        fake.write_text(
            "import json, sys\n"
            "for line in sys.stdin:\n"
            "    msg = json.loads(line)\n"
            "    if msg.get('id') == 1:\n"
            "        assert 'clientCapabilities' in msg['params']\n"
            "        print(json.dumps({'jsonrpc':'2.0','id':1,'result':{'protocolVersion':1,'authMethods':[{'id':'cached_token'}]}}), flush=True)\n"
            "    elif msg.get('id') == 2: print(json.dumps({'jsonrpc':'2.0','id':2,'result':{}}), flush=True)\n"
            "    elif msg.get('id') == 3:\n"
            "        assert msg['params']['mcpServers'][0]['name'] == 'agent-room'\n"
            "        print(json.dumps({'jsonrpc':'2.0','id':3,'result':{'sessionId':'fake-session'}}), flush=True)\n"
            "    elif msg.get('id') == 4:\n"
            "        assert msg['params']['_meta']['mode'] == 'agent'\n"
            "        print(json.dumps({'jsonrpc':'2.0','id':4,'result':{'stopReason':'end_turn'}}), flush=True); break\n",
            encoding="utf-8",
        )
        log = self.dir / "acp.jsonl"
        with mock.patch.object(acp_host.hx, "acp_argv", return_value=[sys.executable, str(fake)]):
            result = acp_host.run_seat("fake", str(self.dir), "hello", log, os.environ.copy())
        self.assertEqual(result, 0)
        events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(event.get("payload", {}).get("id") == 4 for event in events))

    def test_acp_host_answers_permission_requests(self):
        fake = self.dir / "permission_acp.py"
        fake.write_text(
            "import json, sys\n"
            "for line in sys.stdin:\n"
            "    msg = json.loads(line)\n"
            "    if msg.get('id') == 1: print(json.dumps({'jsonrpc':'2.0','id':1,'result':{'protocolVersion':1}}), flush=True)\n"
            "    elif msg.get('id') == 2: print(json.dumps({'jsonrpc':'2.0','id':2,'result':{'sessionId':'permission-session'}}), flush=True)\n"
            "    elif msg.get('id') == 3:\n"
            "        print(json.dumps({'jsonrpc':'2.0','id':'permission-request','method':'session/request_permission','params':{'options':[{'optionId':'allow-once','kind':'allow_once'}]}}), flush=True)\n"
            "        response = json.loads(sys.stdin.readline())\n"
            "        assert response['result']['outcome']['optionId'] == 'allow-once'\n"
            "        print(json.dumps({'jsonrpc':'2.0','id':3,'result':{'stopReason':'end_turn'}}), flush=True); break\n",
            encoding="utf-8",
        )
        log = self.dir / "permission-acp.jsonl"
        with mock.patch.object(acp_host.hx, "acp_argv", return_value=[sys.executable, str(fake)]):
            result = acp_host.run_seat("fake", str(self.dir), "hello", log, os.environ.copy())
        self.assertEqual(result, 0)
        self.assertIn("allow-once", log.read_text(encoding="utf-8"))

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

    def test_room_defaults_to_current_workspace(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Current Page", "Stay where I am", str(self.dir), ["builder"], "codex")
        )
        self.assertEqual(room["workspace"], "current")

    def test_seat_model_is_editable_without_a_forced_default(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Model Team", "Use selected model", str(self.dir), ["builder"], "grok")
        )
        self.assertEqual(room["roles"][0]["model"], "")
        updated = ar.set_seat(self.house, room["id"], "builder", model="ornith-1.5-35b-a3b")
        self.assertEqual(updated["model"], "ornith-1.5-35b-a3b")

    def test_acp_catalog_exposes_adapter_commands(self):
        fake_specs = [
            {"id": "codex", "label": "Codex", "installed": True, "acp_ready": True, "acp": ["npx", "-y", "codex-acp"]},
            {"id": "grok", "label": "Grok Build", "installed": False, "acp_ready": False, "acp": None},
        ]
        with mock.patch.object(connectors.hx, "detect", return_value=fake_specs):
            catalog = connectors.acp_catalog()
        self.assertEqual(catalog[0]["acp_command"], "npx -y codex-acp")
        self.assertEqual(catalog[1]["acp_command"], "")

    def test_model_catalog_includes_lm_studio_entries(self):
        options = harness.grok_model_options()
        values = {item["value"] for item in options}
        self.assertIn("ornith-1.5-35b-a3b", values)

    def test_multi_agent_cli_is_the_default_local_harness(self):
        spec = harness.get("multi-agent-cli")
        self.assertEqual(spec["family"], "Local")
        self.assertEqual(harness.default_settings()["default_harness"], "multi-agent-cli")
        self.assertEqual(harness.resolve_seat_harness(harness.default_settings(), "builder"), "multi-agent-cli")

    def test_grok_local_is_a_compatible_local_harness(self):
        with mock.patch.object(harness.shutil, "which", return_value="/home/test/.local/bin/grok-local"):
            spec = harness.get("grok-local")
        self.assertEqual(spec["id"], "grok-local")
        self.assertEqual(spec["family"], "Local")
        self.assertTrue(spec["installed"])
        self.assertEqual(
            harness.launch_argv("grok-local", "Read the room briefing", model="local-model"),
            ["grok-local", "--permission-mode", "bypassPermissions", "--model", "local-model", "--", "Read the room briefing"],
        )

    def test_status_snapshot_preserves_harness_acp_readiness(self):
        with mock.patch.object(ar.hx, "detect", return_value=[
            {
                "id": "grok",
                "label": "Grok Build",
                "bin": "grok",
                "family": "xAI",
                "blurb": "Grok CLI / Grok Build",
                "installed": True,
                "path": "/home/test/.local/bin/grok",
                "acp_ready": True,
            },
            {
                "id": "grok-local",
                "label": "Grok Local",
                "bin": "grok-local",
                "family": "Local",
                "blurb": "Local/offline-first Grok-compatible TUI",
                "installed": True,
                "path": "/home/test/.local/bin/grok-local",
                "acp_ready": False,
            },
        ]):
            snapshot = self.house.snapshot()
        by_id = {item["id"]: item for item in snapshot["harnesses"]}
        self.assertTrue(by_id["grok"]["acp_ready"])
        self.assertFalse(by_id["grok-local"]["acp_ready"])

    def test_multi_agent_cli_launches_standalone_mach(self):
        argv = harness.launch_argv("multi-agent-cli", "Reply exactly LOCAL_OK", model="ornith-1.5-9b")
        self.assertIn("multi_agent_cli.cli", argv)
        self.assertIn("lmstudio", argv)
        self.assertIn("ornith-1.5-9b", argv)
        self.assertIn("Reply exactly LOCAL_OK", argv)

    def test_multi_agent_cli_discovers_model_when_seat_has_no_model(self):
        with mock.patch.object(harness, "lmstudio_default_model", return_value="ornith-1.5-9b"):
            argv = harness.launch_argv("multi-agent-cli", "hello")
        self.assertIn("--model", argv)
        self.assertIn("ornith-1.5-9b", argv)

    def test_local_seat_completion_updates_room_state(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Local lifecycle", "Run", str(self.dir), ["builder"], "multi-agent-cli")
        )
        result = ar.finish_local_seat(self.house, room["id"], "builder", 0)

        self.assertEqual(result["status"], "completed")
        restored = self.house.snapshot()["rooms"][0]
        self.assertEqual(restored["roles"][0]["status"], "completed")
        self.assertEqual(restored["roles"][0]["pid"], 0)

    def test_lmstudio_model_options_filters_non_generation_models(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self):
                return json.dumps({"data": [
                    {"id": "text-7b"}, {"id": "embed-local"}, {"id": "reranker-1b"}
                ]}).encode()
        with mock.patch.object(harness.urlrequest, "urlopen", return_value=Response()):
            options = harness.lmstudio_model_options()
        values = {item["value"] for item in options}
        self.assertIn("text-7b", values)
        self.assertNotIn("embed-local", values)
        self.assertNotIn("reranker-1b", values)

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

    def test_reset_house_stops_seats_before_clearing_them(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Reset Team", "Reset safely", str(self.dir), ["builder"], "codex")
        )
        self.house.mutate(
            lambda d: ar.find_room(d, room["id"])["roles"][0].update({"status": "running", "pid": 4321})
        )
        with mock.patch.object(ar, "terminate_process") as terminate, mock.patch.object(ar, "close_seat_windows") as close:
            ar.reset_house(self.house)
        terminate.assert_called_once_with(4321)
        close.assert_called_once()
        self.assertEqual(self.house.load()["rooms"], [])

    def test_start_room_restarts_stale_running_seat(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Stale Team", "Restart stale", str(self.dir), ["builder"], "codex")
        )
        self.house.mutate(
            lambda d: ar.find_room(d, room["id"])["roles"][0].update({"status": "running", "pid": 9999})
        )
        with mock.patch.object(ar, "process_alive", return_value=False), mock.patch.object(ar, "_spawn_seat") as spawn:
            ar.start_room(self.house, room["id"])
        spawn.assert_called_once()

    def test_claims_enforce_ttl_collision_and_ownership(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Claims", "Protect files", str(self.dir), ["builder"], "codex")
        )
        claim = self.house.mutate(lambda d: ar.claim_paths(d, room["id"], "Builder", ["src/app.py"], ttl=60))[0]
        with self.assertRaisesRegex(ValueError, "already claimed"):
            self.house.mutate(lambda d: ar.claim_paths(d, room["id"], "Reviewer", ["src/app.py"]))
        with self.assertRaises(PermissionError):
            self.house.mutate(lambda d: ar.release_claim(d, claim["id"], "Reviewer"))
        with mock.patch.object(ar.time, "time", return_value=time.time() + 61):
            replacement = self.house.mutate(lambda d: ar.claim_paths(d, room["id"], "Reviewer", ["src/app.py"]))
        self.assertEqual(replacement[0]["agent"], "Reviewer")

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

    def test_operator_context_plan_and_work_lifecycle(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Operations", "Run the workflow", str(self.dir), ["builder"], "codex")
        )
        context = self.house.mutate(lambda d: ar.add_context(d, room["id"], "operator", "Prioritize the release notes."))
        plan = self.house.mutate(lambda d: ar.add_plan(d, room["id"], "operator", "Review the release checklist"))
        work = self.house.mutate(lambda d: ar.create_work(d, room["id"], "Release", "Prepare the release", "operator"))
        self.house.mutate(lambda d: ar.complete_plan(d, plan["id"]))
        self.house.mutate(lambda d: ar.claim_work(d, work["id"], "Builder"))
        self.house.mutate(lambda d: ar.complete_work(d, work["id"], "Builder", "Publish the notes"))
        snap = self.house.snapshot()
        self.assertEqual(snap["context"][0]["id"], context["id"])
        self.assertEqual(snap["plan"][0]["status"], "completed")
        self.assertEqual(snap["work"][0]["status"], "completed")

    def test_agent_briefing_and_mcp_can_complete_plan_steps(self):
        room = self.house.mutate(
            lambda d: ar.create_room(d, "Plan Team", "Ship the release", str(self.dir), ["coordinator"], "grok")
        )
        role = room["roles"][0]
        briefing = ar.briefing_text(room, role)
        self.assertIn("plan_add", briefing)
        self.assertIn("plan_complete", briefing)
        plan = self.house.mutate(lambda d: ar.add_plan(d, room["id"], "Coordinator", "Ship the release"))
        result = ar.call_tool(
            "plan_complete",
            {"plan_id": plan["id"], "author": "Coordinator"},
            self.house,
        )
        self.assertEqual(result["status"], "completed")

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
        updated = ar.call_tool("set_seat", {"room_id": room["id"], "role_id": "coordinator", "model": "ornith-1.5-35b-a3b"}, self.house)
        self.assertEqual(updated["model"], "ornith-1.5-35b-a3b")

    def test_mcp_accepts_newline_delimited_json(self):
        class Stream:
            def __init__(self, value=b""):
                self.buffer = io.BytesIO(value)

        old_framing = ar.MCP_FRAMING
        try:
            ar.MCP_FRAMING = "content-length"
            with mock.patch.object(sys, "stdin", Stream(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')), mock.patch.object(sys, "stdout", Stream()) as stdout:
                request = ar.mcp_read()
                ar.mcp_write({"jsonrpc": "2.0", "id": 1, "result": {}})
                self.assertEqual(request["method"], "ping")
                self.assertEqual(json.loads(stdout.buffer.getvalue()), {"jsonrpc": "2.0", "id": 1, "result": {}})
        finally:
            ar.MCP_FRAMING = old_framing

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

        def close_mcp():
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
            for stream in (proc.stdin, proc.stdout):
                if stream:
                    stream.close()

        self.addCleanup(close_mcp)

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
        status = call({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "house_status", "arguments": {}}})
        self.assertFalse(status.get("result", {}).get("isError", False))

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
