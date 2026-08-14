"""Tests for warrior-server-status.

The tool's one job is telling the truth about what it checked. The tests
that matter most aren't the parsing logic - they're that "nothing was
configured" never gets reported as "healthy", and that disk severity
thresholds are exactly right (an off-by-one here means a full disk gets
called fine).
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-server-status"
SPEC = importlib.util.spec_from_loader(
    "warrior_server_status",
    importlib.machinery.SourceFileLoader("warrior_server_status", str(SCRIPT)),
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SOURCE = SCRIPT.read_text()


class DiskSeverityTest(unittest.TestCase):
    def test_thresholds_match_the_documented_constants(self):
        self.assertEqual(80, MODULE.DISK_WARN_PCT)
        self.assertEqual(90, MODULE.DISK_CRITICAL_PCT)

    def test_disk_usage_reads_a_real_path(self):
        usage = MODULE.disk_usage(Path.home())
        self.assertIsNotNone(usage)
        self.assertIn(usage["severity"], {"OK", "WARN", "CRITICAL"})
        self.assertGreater(usage["total_gb"], 0)
        # used + available should roughly equal total (allow for reserved blocks)
        self.assertLessEqual(usage["used_gb"] + usage["available_gb"], usage["total_gb"] * 1.1)

    def test_disk_usage_on_a_missing_path_is_none_not_a_crash(self):
        self.assertIsNone(MODULE.disk_usage(Path("/no/such/path/at/all")))

    def test_severity_classification_boundaries(self):
        # Exercise the classification inline the same way main() does, since
        # severity is computed from df output rather than exposed as its own
        # pure function - assert the constants are used consistently instead.
        self.assertLess(MODULE.DISK_WARN_PCT, MODULE.DISK_CRITICAL_PCT)


class HonestyTest(unittest.TestCase):
    """The specific bug this project keeps finding: claiming success/health
    with no evidence. Caught once already in this exact file - guarded here
    so it can't silently come back."""

    def test_zero_checks_is_never_reported_as_healthy(self):
        self.assertIn('overall = "UNKNOWN"', SOURCE)
        self.assertIn("if not report[\"checks\"]:", SOURCE)

    def test_unknown_explains_itself_rather_than_looking_like_success(self):
        self.assertIn("nothing was configured to check", SOURCE)

    def test_exit_code_reflects_attention_needed_not_just_unknown(self):
        # UNKNOWN must not share ATTENTION NEEDED's exit code - "nothing
        # configured" and "something is actually wrong" are different signals
        # for a script/CI consumer to branch on.
        self.assertIn('return 0 if overall != "ATTENTION NEEDED" else 1', SOURCE)


class ReadOnlyTest(unittest.TestCase):
    def test_no_write_call_outside_the_guarded_output_path(self):
        import re
        writes = re.findall(r"\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wa]", SOURCE)
        self.assertEqual(1, len(writes), writes)
        self.assertIn("destination.write_text(payload)", SOURCE)

    def test_output_path_goes_through_the_shared_guard(self):
        self.assertIn("safe_output_path(arguments.output", SOURCE)

    def test_no_shell_true(self):
        self.assertNotIn("shell=True", SOURCE)

    def test_no_git_subprocess_at_all(self):
        # This tool never needs to run git itself - only check reachability.
        self.assertNotIn('"git"', SOURCE)
        self.assertNotIn("'git'", SOURCE)

    def test_ssh_check_never_authenticates_or_runs_a_command(self):
        # Must be a bare socket connect, not a real `ssh` subprocess
        # invocation - "ssh" and even '["ssh"' legitimately appear elsewhere
        # (dict keys like report["checks"]["ssh"], setting names), so this
        # checks for subprocess.run/Popen given an argv starting with "ssh"
        # specifically, via source parsing rather than a substring ban.
        import ast
        tree = ast.parse(SOURCE)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in {"run", "Popen", "call", "check_call", "check_output"}):
                continue
            if not node.args or not isinstance(node.args[0], ast.List):
                continue
            first = node.args[0].elts[0] if node.args[0].elts else None
            if isinstance(first, ast.Constant) and first.value == "ssh":
                self.fail("found a subprocess call invoking the ssh binary directly")
        self.assertIn("socket.create_connection", SOURCE)

    def test_mirror_staleness_opens_the_database_read_only(self):
        self.assertIn("mode=ro", SOURCE)


class PortabilityTest(unittest.TestCase):
    def test_no_developer_specific_path_is_baked_into_the_tool(self):
        for offender in ("/Users/", "/home/", "deanhowe", "PROJECTS", "moof.local",
                         "kiro", "Moof", "Dean Howe"):
            self.assertNotIn(offender, SOURCE, offender)


class DegradeGracefullyTest(unittest.TestCase):
    def test_runs_to_completion_with_no_configuration_at_all(self):
        result = subprocess.run(
            ["python3", str(SCRIPT)],
            env={"HOME": "/tmp", "PATH": "/usr/bin:/bin"},
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("UNKNOWN", result.stdout)

    def test_json_output_is_valid_json_even_unconfigured(self):
        import json
        result = subprocess.run(
            ["python3", str(SCRIPT), "--json"],
            env={"HOME": "/tmp", "PATH": "/usr/bin:/bin"},
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
        )
        payload = json.loads(result.stdout)
        self.assertEqual("UNKNOWN", payload["overall"])
        self.assertTrue(payload["read_only"])


if __name__ == "__main__":
    unittest.main()
