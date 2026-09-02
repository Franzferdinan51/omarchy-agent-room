from pathlib import Path
import unittest


class ConsoleLayoutTests(unittest.TestCase):
    def test_console_root_fills_the_floating_window(self):
        source = (Path(__file__).resolve().parents[1] / "Console.qml").read_text(encoding="utf-8")
        root_block = source.split("property bool closingFromHost", 1)[0]
        self.assertIn("anchors.fill: parent", root_block)

    def test_compact_layout_keeps_wrapped_tabs_and_editor_input_usable(self):
        source = (Path(__file__).resolve().parents[1] / "Console.qml").read_text(encoding="utf-8")
        self.assertIn("height: implicitHeight", source)
        self.assertIn("contentMaxWidth: 1280", source)
        self.assertIn("x: Math.max(0, (scrollArea.availableWidth - width) / 2)", source)
        for field in ("contextField", "planField", "workTitleField", "workBriefField"):
            self.assertIn(f"{field}.activeFocus", source)

    def test_message_and_capsule_text_wraps_without_fixed_title_columns(self):
        source = (Path(__file__).resolve().parents[1] / "Console.qml").read_text(encoding="utf-8")
        self.assertIn('component Capsule: Rectangle', source)
        self.assertIn('wrapMode: Text.Wrap', source)
        self.assertIn('Flow {\n                        width: parent.width', source)

    def test_console_uses_dynamic_status_snapshot_and_unique_editor_ids(self):
        source = (Path(__file__).resolve().parents[1] / "Console.qml").read_text(encoding="utf-8")
        self.assertIn('command: [root.pluginDir + "/bin/agent-room", "status"]', source)
        ids = [line.split("id:", 1)[1].strip() for line in source.splitlines() if "id:" in line]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("id: telegramTokenField", source)
        self.assertIn("id: settingsWorkspaceField", source)

    def test_console_exposes_grok_local_and_only_offers_available_acp(self):
        source = (Path(__file__).resolve().parents[1] / "Console.qml").read_text(encoding="utf-8")
        self.assertIn('text: "Grok Local"', source)
        self.assertIn("function harnessSupportsAcp", source)
        self.assertIn("root.harnessSupportsAcp(modelData.harness || modelData.program)", source)


if __name__ == "__main__":
    unittest.main()
