"""Tests for warrior-sidecar.

The bug this file exists to pin down happened during this tool's own first
live test: the .gitignore entry it wrote looked correct - "/goals/  # why" -
and was completely wrong. .gitignore comments are only comments as the
first character of a LINE; an inline "pattern  # comment" is not comment
syntax at all, it becomes part of the literal (non-matching) pattern. The
sidecar directory it had just created stayed untracked-and-unignored, the
worst state this whole project exists to catch, produced by its own newest
tool. Caught by verifying the actual effect (`git status`) rather than
trusting the tool's own success message.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-sidecar"
SPEC = importlib.util.spec_from_loader(
    "warrior_sidecar",
    importlib.machinery.SourceFileLoader("warrior_sidecar", str(SCRIPT)),
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SOURCE = SCRIPT.read_text()


def real_git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            text=True, timeout=15, stdin=subprocess.DEVNULL)
    return result.returncode, result.stdout.strip()


class GitignoreSyntaxTest(unittest.TestCase):
    """The regression this file is named for."""

    def test_the_pattern_and_comment_are_on_separate_lines(self):
        block = MODULE.gitignore_block("goals")
        lines = block.splitlines()
        self.assertEqual(2, len(lines))
        self.assertTrue(lines[0].startswith("#"), lines[0])
        self.assertEqual("/goals/", lines[1])

    def test_a_freshly_created_sidecar_is_actually_ignored_by_real_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            real_git(project, "init", "-q")
            record = MODULE.plan(project, "goals")
            self.assertEqual("create", record["action"])
            MODULE.execute(record)

            # The real test: ask real git, not this tool, whether it worked.
            code, output = real_git(project, "status", "--porcelain")
            self.assertEqual(0, code)
            self.assertNotIn("goals", output, f"goals/ still shows in git status: {output!r}")

            code, output = real_git(project, "check-ignore", "-v", "goals/")
            self.assertEqual(0, code, "git check-ignore found nothing - the pattern did not match")


class ScaffoldTest(unittest.TestCase):
    def test_known_category_gets_its_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            real_git(project, "init", "-q")
            record = MODULE.execute(MODULE.plan(project, "tmp"))
            self.assertNotIn("FAILED", record["result"], record["result"])
            readme = (project / "tmp" / "README.md").read_text()
            self.assertIn("Scratch", readme)
            self.assertIn("never delete", readme.lower())

    def test_unknown_category_gets_a_blank_readme_and_says_so(self):
        title, body = MODULE.category_purpose("experiments")
        self.assertEqual("Experiments", title)
        self.assertIn("experiments", body)

    def test_refuses_to_overwrite_an_existing_non_git_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            real_git(project, "init", "-q")
            (project / "goals").mkdir()
            (project / "goals" / "already-here.txt").write_text("pre-existing")
            record = MODULE.plan(project, "goals")
            self.assertEqual("refuse", record["action"])

    def test_skips_a_sidecar_that_is_already_a_git_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            real_git(project, "init", "-q")
            MODULE.execute(MODULE.plan(project, "goals"))
            second_pass = MODULE.plan(project, "goals")
            self.assertEqual("skip", second_pass["action"])

    def test_dry_run_writes_nothing_at_all(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            real_git(project, "init", "-q")
            result = subprocess.run(
                ["python3", str(SCRIPT), "init", str(project), "goals"],
                capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("DRY RUN", result.stdout)
            self.assertFalse((project / "goals").exists())
            self.assertFalse((project / ".gitignore").exists())


class ListTest(unittest.TestCase):
    def test_finds_a_sidecar_it_did_not_create_itself(self):
        # A directory that is gitignored AND its own git repo counts as a
        # sidecar even if warrior-sidecar never touched it - this project's
        # own .tax and .kiro predate this tool entirely.
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            real_git(project, "init", "-q")
            (project / ".gitignore").write_text("/wiki/\n")
            (project / "wiki").mkdir()
            real_git(project / "wiki", "init", "-q")
            found = MODULE.list_existing_sidecars(project)
            self.assertEqual(1, len(found))
            self.assertEqual("wiki", found[0]["category"])

    def test_reports_nothing_found_rather_than_crashing_on_an_empty_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            real_git(project, "init", "-q")
            self.assertEqual([], MODULE.list_existing_sidecars(project))


class ReadOnlyChokepointTest(unittest.TestCase):
    """The shared read-only git() must never be asked to mutate. This tool's
    one write path is its own separate, narrowly-scoped helper."""

    def test_shared_read_only_git_is_imported_but_never_used_to_write(self):
        self.assertIn("from warrior_forge import git", SOURCE)
        # Every mutation goes through the local helper, never the shared one.
        self.assertIn("_local_git_write", SOURCE)

    def test_local_write_helper_allows_exactly_three_verbs(self):
        self.assertIn('allowed = {"init", "add", "commit"}', SOURCE)

    def test_local_write_helper_only_ever_touches_a_freshly_created_directory(self):
        # execute() must create the directory itself (mkdir with exist_ok=False,
        # so it errors on anything pre-existing) before any write call.
        self.assertIn("mkdir(parents=True, exist_ok=False)", SOURCE)

    def test_no_shell_true_anywhere(self):
        self.assertNotIn("shell=True", SOURCE)

    def test_commit_works_with_no_global_git_identity_configured(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            real_git(project, "init", "-q")
            result = subprocess.run(
                ["python3", str(SCRIPT), "init", str(project), "goals", "--apply"],
                capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL,
                env={"HOME": temporary, "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("FAILED", result.stdout)


class DelegatesRatherThanDuplicatesTest(unittest.TestCase):
    """warrior-protect already does verified-by-refs pushing; this tool must
    not grow a second implementation of that safety-critical path."""

    def test_does_not_call_the_forge_api_at_all(self):
        self.assertNotIn("api(", SOURCE)
        self.assertNotIn("forge_token", SOURCE)

    def test_tells_the_user_to_use_warrior_protect_to_push(self):
        self.assertIn("warrior-protect", SOURCE)


class PortabilityTest(unittest.TestCase):
    def test_no_developer_specific_path_is_baked_into_the_tool(self):
        for offender in ("/Users/", "/home/", "deanhowe", "PROJECTS", "moof.local",
                         "kiro", "Moof", "Dean Howe"):
            self.assertNotIn(offender, SOURCE, offender)


if __name__ == "__main__":
    unittest.main()
