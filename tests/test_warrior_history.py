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


class PublicHistoryAuditCliTest(unittest.TestCase):
    def test_fails_closed_on_historical_personal_data_and_secrets_without_echoing_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "project"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            private_email = "person" + "@private-company.dev"
            private_path = "/Users/" + "privateperson/Projects/app"
            private_token = "ghp" + "_abcdefghijklmnopqrstuvwxyz1234567890"
            (repo / "notes.txt").write_text(
                f"contact={private_email}\nroot={private_path}\ntoken={private_token}\n"
            )
            run_git(repo, "add", "notes.txt")
            run_git(repo, "commit", "-m", "accidental private material")
            (repo / "notes.txt").write_text("public replacement\n")
            run_git(repo, "add", "notes.txt")
            run_git(repo, "commit", "-m", "remove private material from current tree")

            result = run_history("public-audit", str(repo), "--ref", "main", "--json")

            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertNotIn(private_email, result.stdout)
            self.assertNotIn(private_path, result.stdout)
            self.assertNotIn(private_token, result.stdout)
            report = json.loads(result.stdout)
            self.assertFalse(report["safe_for_publication"])
            self.assertEqual(report["selected_ref"], "refs/heads/main")
            self.assertEqual(report["findings_by_category"]["email-address"], 1)
            self.assertEqual(report["findings_by_category"]["absolute-user-path"], 1)
            self.assertEqual(report["findings_by_category"]["github-token"], 1)
            self.assertGreaterEqual(report["commit_metadata_email_count"], 1)

    def test_accepts_a_clean_selected_ref_and_ignores_an_unselected_private_branch(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "project"
            repo.mkdir()
            run_git(repo, "init", "-b", "main")
            (repo / "README.md").write_text("Portable public project.\n")
            run_git(repo, "add", "README.md")
            run_git(repo, "commit", "-m", "public root")
            run_git(repo, "switch", "-c", "private-notes")
            (repo / "private.txt").write_text("/Users/" + "privateperson/private\n")
            run_git(repo, "add", "private.txt")
            run_git(repo, "commit", "-m", "private branch")
            run_git(repo, "switch", "main")

            result = run_history(
                "public-audit", str(repo), "--ref", "main",
                "--allow-email", "fixture@example.invalid", "--json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["safe_for_publication"])
            self.assertEqual(report["scanned_ref_count"], 1)
            self.assertEqual(report["content_blob_count"], 1)


class HistoryRewriteCandidateCliTest(unittest.TestCase):
    def test_builds_a_single_branch_public_candidate_with_redacted_content_and_noreply_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            candidate = root / "public.git"
            plan = root / "public-plan.json"
            replacements = root / "private-replacements.txt"
            source.mkdir()
            run_git(source, "init", "-b", "main")
            private_path = "/Users/" + "privateperson/secret"
            private_token = "ghp" + "_abcdefghijklmnopqrstuvwxyz1234567890"
            (source / "README.md").write_text(f"path={private_path}\ntoken={private_token}\n")
            run_git(source, "add", "README.md")
            run_git(source, "commit", "-m", "initial source")
            run_git(source, "switch", "-c", "private-notes")
            (source / "never-public.txt").write_text("private branch only\n")
            run_git(source, "add", "never-public.txt")
            run_git(source, "commit", "-m", "private side branch")
            run_git(source, "switch", "main")
            replacements.write_text(
                f"{private_path}==>/Users/developer/project\n{private_token}==>[REDACTED]\n"
            )

            planned = run_history(
                "public-plan", str(source), "--ref", "main",
                "--public-email", "owner@users.noreply.github.com",
                "--replace-text", str(replacements), "--output", str(plan), "--json",
            )
            self.assertEqual(planned.returncode, 0, planned.stderr)
            built = run_history(
                "build-public-candidate", "--plan", str(plan),
                "--destination", str(candidate), "--json",
            )

            self.assertEqual(built.returncode, 0, built.stderr)
            report = json.loads(built.stdout)
            self.assertTrue(report["verification"]["source_unchanged"])
            self.assertTrue(report["verification"]["selected_branch_only"])
            self.assertTrue(report["verification"]["public_audit_passed"])
            refs = subprocess.run(
                ["git", "--git-dir", str(candidate), "for-each-ref", "--format=%(refname)"],
                check=True, capture_output=True, text=True,
            ).stdout.splitlines()
            self.assertEqual(refs, ["refs/heads/main"])
            contents = subprocess.run(
                ["git", "--git-dir", str(candidate), "show", "main:README.md"],
                check=True, capture_output=True, text=True,
            ).stdout
            self.assertNotIn(private_path, contents)
            self.assertNotIn(private_token, contents)
            self.assertIn("/Users/developer/project", contents)
            emails = subprocess.run(
                ["git", "--git-dir", str(candidate), "log", "--format=%ae%n%ce", "main"],
                check=True, capture_output=True, text=True,
            ).stdout.splitlines()
            self.assertEqual(set(emails), {"owner@users.noreply.github.com"})

    def test_removes_an_exact_path_only_in_a_new_verified_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            candidate = root / "candidate.git"
            plan = root / "rewrite-plan.json"
            source.mkdir()
            run_git(source, "init", "-b", "main")
            (source / "keep.txt").write_text("keep forever\n")
            (source / "accidental.zip").write_bytes(b"PK\x03\x04remove me")
            run_git(source, "add", "keep.txt", "accidental.zip")
            run_git(source, "commit", "-m", "add source and accidental archive")
            (source / "later.txt").write_text("later\n")
            run_git(source, "add", "later.txt")
            run_git(source, "commit", "-m", "keep later history")
            source_head = subprocess.run(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()

            planned = run_history(
                "plan", str(source), "--remove-path", "accidental.zip",
                "--output", str(plan), "--json",
            )
            self.assertEqual(planned.returncode, 0, planned.stderr)
            self.assertEqual(json.loads(plan.read_text())["source_head"], source_head)

            built = run_history(
                "build-candidate", "--plan", str(plan),
                "--destination", str(candidate), "--json",
            )

            self.assertEqual(built.returncode, 0, built.stderr)
            report = json.loads(built.stdout)
            self.assertTrue(report["verification"]["source_unchanged"])
            self.assertTrue(report["verification"]["removed_paths_absent"])
            self.assertTrue(report["verification"]["candidate_fsck_passed"])
            self.assertTrue(report["verification"]["candidate_has_no_remotes"])
            source_objects = subprocess.run(
                ["git", "-C", str(source), "rev-list", "--objects", "--all"],
                check=True, capture_output=True, text=True,
            ).stdout
            candidate_objects = subprocess.run(
                ["git", "-C", str(candidate), "rev-list", "--objects", "--all"],
                check=True, capture_output=True, text=True,
            ).stdout
            self.assertIn("accidental.zip", source_objects)
            self.assertNotIn("accidental.zip", candidate_objects)
            self.assertIn("keep.txt", candidate_objects)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(source), "rev-parse", "HEAD"],
                    check=True, capture_output=True, text=True,
                ).stdout.strip(),
                source_head,
            )
            self.assertTrue((source / "accidental.zip").is_file())

    def test_refuses_a_dirty_source_before_writing_a_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            plan = root / "plan.json"
            source.mkdir()
            run_git(source, "init", "-b", "main")
            (source / ".env").write_text("TOKEN=secret\n")
            run_git(source, "add", ".env")
            run_git(source, "commit", "-m", "accidental environment")
            (source / "uncommitted.txt").write_text("must not be omitted\n")

            result = run_history(
                "plan", str(source), "--remove-path", ".env",
                "--output", str(plan), "--json",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("not clean", result.stderr)
            self.assertFalse(plan.exists())
            self.assertTrue((source / "uncommitted.txt").is_file())

    def test_refuses_source_drift_and_an_existing_candidate_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            plan = root / "plan.json"
            destination = root / "candidate.git"
            source.mkdir()
            run_git(source, "init", "-b", "main")
            (source / "archive.zip").write_bytes(b"PK\x03\x04old")
            run_git(source, "add", "archive.zip")
            run_git(source, "commit", "-m", "old archive")
            planned = run_history(
                "plan", str(source), "--remove-path", "archive.zip",
                "--output", str(plan), "--json",
            )
            self.assertEqual(planned.returncode, 0, planned.stderr)
            (source / "later.txt").write_text("source advanced\n")
            run_git(source, "add", "later.txt")
            run_git(source, "commit", "-m", "advance after plan")

            drifted = run_history(
                "build-candidate", "--plan", str(plan),
                "--destination", str(destination), "--json",
            )
            self.assertEqual(drifted.returncode, 2)
            self.assertIn("HEAD changed", drifted.stderr)
            self.assertFalse(destination.exists())

            current_plan = root / "current-plan.json"
            replanned = run_history(
                "plan", str(source), "--remove-path", "archive.zip",
                "--output", str(current_plan), "--json",
            )
            self.assertEqual(replanned.returncode, 0, replanned.stderr)
            destination.mkdir()
            marker = destination / "preserve-me.txt"
            marker.write_text("existing work\n")
            existing = run_history(
                "build-candidate", "--plan", str(current_plan),
                "--destination", str(destination), "--json",
            )
            self.assertEqual(existing.returncode, 2)
            self.assertIn("already exists", existing.stderr)
            self.assertEqual(marker.read_text(), "existing work\n")


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

    def test_preserves_dotfile_identity_in_rewrite_rules(self):
        self.assertEqual(MODULE.validate_removal_path(".env"), ".env")

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
