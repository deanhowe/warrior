from __future__ import annotations

import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_loader(
    "warrior_credits",
    SourceFileLoader("warrior_credits", str(ROOT / "bin" / "warrior-credits")),
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class WarriorCreditsTest(unittest.TestCase):
    @patch.object(MODULE.subprocess, "run")
    def test_visible_tmux_capture_does_not_include_stale_scrollback(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "visible"
        self.assertEqual("visible", MODULE.tmux_capture("tmux", "session", lines_back=0))
        self.assertNotIn("-S", run.call_args.args[0])

    def test_codex_parser_preserves_five_hour_and_weekly_windows(self):
        data = MODULE.parse_codex("""
│  5h limit:      [██████████████████░░] 91% left (resets 12:58)          │
│  Weekly limit:  [████████████████░░░░] 82% left (resets 18:44 on 1 Sep) │
""")
        self.assertEqual(91, data["session_pct_remaining"])
        self.assertEqual(9, data["session_pct_used"])
        self.assertEqual("12:58", data["session_resets_on"])
        self.assertEqual(82, data["weekly_pct_remaining"])
        self.assertEqual(18, data["weekly_pct_used"])
        self.assertEqual("1 Sep at 18:44", data["weekly_resets_on"])

    def test_codex_parser_keeps_legacy_weekly_only_output_compatible(self):
        data = MODULE.parse_codex(
            "Weekly limit: 82% left (resets 18:44 on 1 Sep)"
        )
        self.assertNotIn("session_pct_remaining", data)
        self.assertEqual(82, data["weekly_pct_remaining"])


if __name__ == "__main__":
    unittest.main()
