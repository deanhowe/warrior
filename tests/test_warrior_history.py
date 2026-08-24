from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-history"
LOADER = importlib.machinery.SourceFileLoader("warrior_history", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        },
    )


def run_history(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class HistoryAssessmentCliTest(unittest.TestCase):
    def test_help_uses_a_human_scale_large_blob_option(self):
        result = run_history("assess", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--large-mb", result.stdout)
        self.assertNotIn("--large-bytes", result.stdout)

    def test_distinguishes_current_and_history_only_database_and_archive_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "project"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            (repo / "application.py").write_text("print('safe')\n")
            (repo / "old-export.zip").write_bytes(b"PK\x03\x04historical")
            run_git(repo, "add", "application.py", "old-export.zip")
            run_git(repo, "commit", "-m", "initial import")
            (repo / "old-export.zip").unlink()
            (repo / "runtime.sqlite3").write_bytes(b"SQLite format 3\x00")
            run_git(repo, "add", "old-export.zip", "runtime.sqlite3")
            run_git(repo, "commit", "-m", "replace archive with runtime database")

            result = run_history("assess", str(repo), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            artifacts = {item["path"]: item for item in report["artifacts"]}
            self.assertEqual(artifacts["old-export.zip"]["presence"], "history-only")
            self.assertEqual(artifacts["old-export.zip"]["kind"], "archive")
            self.assertEqual(artifacts["runtime.sqlite3"]["presence"], "current")
            self.assertEqual(artifacts["runtime.sqlite3"]["kind"], "database")
            self.assertNotIn("historical", result.stdout)
            self.assertNotIn("SQLite format", result.stdout)

    def test_reports_large_blobs_even_when_the_extension_is_not_special(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "project"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            (repo / "weights.bin").write_bytes(b"x" * 2048)
            run_git(repo, "add", "weights.bin")
            run_git(repo, "commit", "-m", "add generated weights")

            result = run_history("assess", str(repo), "--json", "--large-bytes", "1024")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(len(report["large_blobs"]), 1)
            self.assertEqual(report["large_blobs"][0]["path"], "weights.bin")
            self.assertEqual(report["large_blobs"][0]["size_bytes"], 2048)
            self.assertEqual(report["large_blobs"][0]["presence"], "current")

    def test_reports_unreachable_commits_as_expiring_work_not_deletion_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "project"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            (repo / "kept.txt").write_text("kept\n")
            run_git(repo, "add", "kept.txt")
            run_git(repo, "commit", "-m", "kept history")
            run_git(repo, "switch", "-c", "temporary-line")
            (repo / "lost.txt").write_text("important\n")
            run_git(repo, "add", "lost.txt")
            run_git(repo, "commit", "-m", "valuable experiment")
            unreachable = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            run_git(repo, "switch", "main")
            run_git(repo, "branch", "-D", "temporary-line")

            result = run_history("assess", str(repo), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            commits = {item["commit"]: item for item in report["unreachable_commits"]}
            self.assertEqual(commits[unreachable]["subject"], "valuable experiment")
            self.assertEqual(commits[unreachable]["disposition"], "preserve-and-review")
            self.assertNotIn("delete", commits[unreachable]["next_step"].casefold())

    def test_counts_sensitive_artifacts_without_printing_their_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "project"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            private = repo / "credentials"
            private.mkdir()
            (private / "customer-passwords.zip").write_bytes(b"private marker")
            run_git(repo, "add", "credentials/customer-passwords.zip")
            run_git(repo, "commit", "-m", "accidental private archive")

            result = run_history("assess", str(repo), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("customer-passwords", result.stdout)
            self.assertNotIn("private marker", result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["sensitive_paths_withheld"], 1)
            self.assertTrue(report["artifacts"][0]["path_withheld"])
            self.assertNotIn("path", report["artifacts"][0])

    def test_warns_when_reachable_refs_contain_unrelated_root_histories(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "project"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            (repo / "first.txt").write_text("first\n")
            run_git(repo, "add", "first.txt")
            run_git(repo, "commit", "-m", "first lineage")
            run_git(repo, "switch", "--orphan", "imported-history")
            (repo / "second.txt").write_text("second\n")
            run_git(repo, "add", "second.txt")
            run_git(repo, "commit", "-m", "unrelated imported lineage")

            result = run_history("assess", str(repo), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(len(report["root_commits"]), 2)
            self.assertIn("multiple unrelated root histories", report["warnings"])

    def test_assesses_bare_repositories_without_calling_worktree_only_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            bare = root / "project.git"
            source.mkdir()
            run_git(source, "init", "-b", "main")
            (source / "release.zip").write_bytes(b"PK\x03\x04release")
            run_git(source, "add", "release.zip")
            run_git(source, "commit", "-m", "release archive")
            subprocess.run(
                ["git", "clone", "--bare", str(source), str(bare)],
                check=True, capture_output=True, text=True,
            )

            result = run_history("assess", str(bare), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["repository_kind"], "bare")
            self.assertEqual(report["artifacts"][0]["presence"], "current")


class ReadOnlyGuardTest(unittest.TestCase):
    def test_rejects_history_rewrite_and_fsck_recovery_writes(self):
        dangerous = [
            ("filter-branch", "--", "--all"),
            ("fsck", "--lost-found"),
            ("rev-list", "--objects", "--all", "--output=.git/HEAD"),
            ("cat-file", "--batch-check", "--filters"),
        ]
        for command in dangerous:
            with self.subTest(command=command):
                with self.assertRaises(RuntimeError):
                    MODULE.assert_read_only(command)

    def test_classifies_common_history_bloat_formats(self):
        expected = {
            "backup.sql": "database-dump",
            "repository.bundle": "git-bundle",
            "release.jar": "package-archive",
            "application.exe": "compiled-binary",
            "recording.mov": "media",
        }
        for path, kind in expected.items():
            with self.subTest(path=path):
                self.assertEqual(MODULE.artifact_kind(path), kind)

    def test_withholds_sensitive_commit_subjects(self):
        self.assertEqual(
            MODULE.public_subject("temporary password hunter2"),
            "[sensitive commit subject withheld]",
        )
        self.assertEqual(MODULE.public_subject("document history policy"), "document history policy")

    def test_assessment_does_not_refresh_or_rewrite_the_git_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "project"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            (repo / "tracked.txt").write_text("tracked\n")
            run_git(repo, "add", "tracked.txt")
            run_git(repo, "commit", "-m", "tracked state")
            index = repo / ".git" / "index"
            before = hashlib.sha256(index.read_bytes()).hexdigest()

            result = run_history("assess", str(repo), "--json")

            after = hashlib.sha256(index.read_bytes()).hexdigest()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
