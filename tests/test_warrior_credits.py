from __future__ import annotations

import ast
import importlib.util
import time
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


class ClaudeCreditsTest(unittest.TestCase):
    """fetch_claude/parse_claude read plan-usage-history.json directly.

    Rewritten 2026-09-02: the previous implementation tmux-scraped a real
    Claude Code TUI, like copilot/codex still do below, which meant every
    call spawned a durable Claude session. That defect was found live in the
    sibling Moof project (hundreds of sessions/day from a 60s poll timer)
    and fixed there first; this ports the same fix here. The load-bearing
    assertion is that the claude path cannot do that again.
    """

    def test_claude_functions_cannot_spawn_a_process(self):
        # Scoped to fetch_claude/parse_claude and their _claude_* helpers
        # only: copilot/kiro/codex legitimately still use subprocess/tmux
        # below in this same file, so a module-wide check would be false.
        source = Path(ROOT / "bin" / "warrior-credits").read_text()
        tree = ast.parse(source)
        claude_functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and (node.name == "fetch_claude" or node.name.startswith("_claude_")
                 or node.name == "parse_claude")
        }
        self.assertIn("fetch_claude", claude_functions)
        self.assertIn("parse_claude", claude_functions)
        for name, node in claude_functions.items():
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr in (
                    "run", "Popen", "system", "popen",
                ):
                    self.fail(f"{name} calls {child.attr} — reintroduces a process spawn")
                if isinstance(child, ast.Name) and child.id in ("tmux_session", "tmux_send",
                                                                "tmux_capture", "require_tmux"):
                    self.fail(f"{name} calls {child.id} — reintroduces a tmux scrape")

    def test_percent_treats_absent_window_as_zero(self):
        self.assertEqual(0, MODULE._claude_percent({"u": {}}, "fh"))
        self.assertEqual(37, MODULE._claude_percent({"u": {"fh": 37}}, "fh"))

    def test_percent_clamps_and_rejects_junk(self):
        self.assertEqual(100, MODULE._claude_percent({"u": {"fh": 140}}, "fh"))
        self.assertEqual(0, MODULE._claude_percent({"u": {"fh": -5}}, "fh"))
        self.assertEqual(0, MODULE._claude_percent({"u": {"fh": "nope"}}, "fh"))

    def test_window_start_detects_a_drop(self):
        samples = [
            {"t": 1_000, "u": {"fh": 40}},
            {"t": 2_000, "u": {"fh": 60}},
            {"t": 3_000, "u": {"fh": 5}},
        ]
        self.assertEqual(3_000, MODULE._claude_window_start_ms(samples, "fh"))

    def test_window_start_detects_a_rise_from_idle(self):
        samples = [
            {"t": 1_000, "u": {"fh": 0}},
            {"t": 2_000, "u": {"fh": 0}},
            {"t": 3_000, "u": {"fh": 8}},
        ]
        self.assertEqual(3_000, MODULE._claude_window_start_ms(samples, "fh"))

    def test_window_start_returns_none_without_a_boundary(self):
        samples = [{"t": 1_000, "u": {"fh": 5}}, {"t": 2_000, "u": {"fh": 9}}]
        self.assertIsNone(MODULE._claude_window_start_ms(samples, "fh"))

    def test_unknown_start_reports_unknown_rather_than_inventing_a_time(self):
        self.assertEqual(
            "unknown",
            MODULE._claude_format_reset(None, MODULE.CLAUDE_SESSION_WINDOW_SECONDS, time.time()),
        )

    def test_reset_day_of_week_is_not_assumed_fixed(self):
        # The real-world case that motivated this test: a reset detected on
        # a Tuesday, one day off a prior Wednesday-looking pattern. The
        # window length must still hold even though the weekday does not.
        now = time.time()
        tuesday_start_ms = (now - 6.9 * 24 * 3600) * 1000
        rendered = MODULE._claude_format_reset(
            tuesday_start_ms, MODULE.CLAUDE_WEEKLY_WINDOW_SECONDS, now
        )
        self.assertNotEqual("unknown", rendered)

    def test_reset_is_always_rolled_into_the_future(self):
        now = time.time()
        stale_start_ms = (now - 11 * 24 * 3600) * 1000
        rendered = MODULE._claude_format_reset(
            stale_start_ms, MODULE.CLAUDE_WEEKLY_WINDOW_SECONDS, now
        )
        self.assertNotEqual("unknown", rendered)
        self.assertIsNotNone(time.strptime(rendered, "%a %d %b, %I:%M%p"))

    def test_parse_emits_the_dashboard_contract(self):
        now_ms = time.time() * 1000
        samples = [
            {"t": now_ms - 2 * 3600 * 1000, "u": {"fh": 0, "sd": 10}},
            {"t": now_ms - 1 * 3600 * 1000, "u": {"fh": 20, "sd": 10}},
            {"t": now_ms, "u": {"fh": 20, "sd": 10}},
        ]
        data = MODULE.parse_claude(samples)
        self.assertEqual(
            {"session_pct_used", "session_pct_remaining", "session_resets_on",
             "weekly_pct_used", "weekly_pct_remaining", "weekly_resets_on"},
            set(data),
        )
        self.assertEqual(20, data["session_pct_used"])
        self.assertEqual(80, data["session_pct_remaining"])

    def test_stale_history_raises_quota_fetch_error_not_a_crash(self):
        old_ms = (time.time() - 100 * 3600) * 1000
        with self.assertRaises(MODULE.QuotaFetchError):
            MODULE.parse_claude([{"t": old_ms, "u": {"fh": 5, "sd": 5}}])


if __name__ == "__main__":
    unittest.main()
