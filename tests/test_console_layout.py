from pathlib import Path
import unittest


class ConsoleLayoutTests(unittest.TestCase):
    def test_console_root_fills_the_floating_window(self):
        source = (Path(__file__).resolve().parents[1] / "Console.qml").read_text(encoding="utf-8")
        root_block = source.split("property bool closingFromHost", 1)[0]
        self.assertIn("anchors.fill: parent", root_block)


if __name__ == "__main__":
    unittest.main()
