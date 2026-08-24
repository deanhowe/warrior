from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lib.warrior_forge import UnsafeGitCommand, assert_safe_git


SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-project"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Warrior Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Warrior Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}


def git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    ).stdout.strip()


def initialise(repo: Path, name: str = "dean/example", version: str | None = "1.2.3") -> None:
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    composer = {"name": name, "type": "library"}
    if version is not None:
        composer["version"] = version
    (repo / "composer.json").write_text(json.dumps(composer) + "\n")
    (repo / "src.php").write_text("<?php\n")
    git(repo, "add", "composer.json", "src.php")
    git(repo, "commit", "-q", "-m", "fixture")


def snapshot(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for current, _directories, files in os.walk(path):
        for filename in files:
            item = Path(current) / filename
            result[str(item.relative_to(path))] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def dossier(*roots: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "dossier", *map(str, roots), "--json"],
        check=False,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )


def checkpoint_plan(*roots: Path, output: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "checkpoint-plan", *map(str, roots), "--json"]
    if output is not None:
        command.extend(["--output", str(output)])
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )


class ProjectDossierCliTest(unittest.TestCase):
    def test_git_guard_allows_only_plain_blob_reads_for_cat_file(self) -> None:
        assert_safe_git(("cat-file", "blob", "refs/tags/v1.0.0:composer.json"))
        with self.assertRaises(UnsafeGitCommand):
            assert_safe_git(("cat-file", "--filters", "refs/tags/v1.0.0:composer.json"))

    def test_discovers_source_and_agent_state_but_prunes_dependency_repositories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package"
            initialise(root)
            git(root, "remote", "add", "origin", "https://dean:secret@example.test/dean/example.git")

            agent_state = root / ".kiro"
            initialise(agent_state, "dean/example-agent-state", "0.1.0")

            vendored = root / "vendor" / "third-party" / "dependency"
            initialise(vendored, "third-party/dependency", "9.9.9")

            before = snapshot(root / ".git")
            result = dossier(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["read_only"])
            self.assertEqual(report["repositories_discovered"], 2)
            repositories = {item["path"]: item for item in report["repositories"]}
            source = repositories[str(root.resolve())]
            self.assertEqual(source["role_hint"], "source")
            self.assertEqual(source["composer"]["name"], "dean/example")
            self.assertEqual(source["composer"]["version_candidates"], ["1.2.3"])
            self.assertTrue(source["composer"]["publishable"])
            self.assertIn("[REDACTED]@example.test", source["remotes"][0]["url"])
            self.assertNotIn("secret", result.stdout)
            self.assertEqual(
                repositories[str(agent_state.resolve())]["role_hint"],
                "auxiliary-agent-state",
            )
            self.assertNotIn(str(vendored.resolve()), repositories)
            self.assertEqual(before, snapshot(root / ".git"))

    def test_placeholder_or_unversioned_manifests_are_blocked_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "template"
            initialise(root, ":vendor_slug/:package_slug", None)

            result = dossier(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            package = json.loads(result.stdout)["repositories"][0]["composer"]
            self.assertFalse(package["publishable"])
            self.assertEqual(package["version_candidates"], [])
            self.assertIn("invalid-or-placeholder-package-name", package["blockers"])
            self.assertIn("no-evidence-backed-version", package["blockers"])

    def test_historical_semver_tags_are_publishable_version_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "tagged-package"
            initialise(root, "dean/tagged-package", None)
            git(root, "tag", "v1.4.0")
            (root / "src.php").write_text("<?php // later\n")
            git(root, "add", "src.php")
            git(root, "commit", "-q", "-m", "later work")

            result = dossier(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            package = json.loads(result.stdout)["repositories"][0]["composer"]
            self.assertTrue(package["publishable"])
            self.assertEqual(package["version_candidates"], ["v1.4.0"])
            self.assertEqual(
                package["tagged_releases"],
                [{"version": "v1.4.0", "ref": "refs/tags/v1.4.0"}],
            )

    def test_tag_for_pre_fork_package_identity_does_not_release_current_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "renamed-fork"
            initialise(root, "upstream/original", None)
            git(root, "tag", "v1.4.0")
            (root / "composer.json").write_text(json.dumps({
                "name": "dean/renamed-fork",
                "type": "library",
            }) + "\n")
            git(root, "add", "composer.json")
            git(root, "commit", "-q", "-m", "rename package")

            result = dossier(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            package = json.loads(result.stdout)["repositories"][0]["composer"]
            self.assertFalse(package["publishable"])
            self.assertEqual(package["version_candidates"], [])
            self.assertEqual(package["tagged_releases"], [])
            self.assertEqual(package["historical_package_identities"], [{
                "name": "upstream/original",
                "version": "v1.4.0",
                "ref": "refs/tags/v1.4.0",
            }])

    def test_dirty_manifest_version_is_reported_but_not_treated_as_a_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "dirty-manifest"
            initialise(root, "dean/example", "1.0.0")
            (root / "composer.json").write_text(json.dumps({
                "name": "dean/example",
                "type": "library",
                "version": "9.9.9",
            }) + "\n")

            result = dossier(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            package = json.loads(result.stdout)["repositories"][0]["composer"]
            self.assertEqual(package["declared_version"], "1.0.0")
            self.assertEqual(package["version_candidates"], ["1.0.0"])
            self.assertTrue(package["working_tree_differs_from_head"])
            self.assertEqual(package["working_tree"]["declared_version"], "9.9.9")

    def test_duplicate_composer_identities_are_reported_at_estate_level(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialise(root / "old", "dean/collision", "1.0.0")
            initialise(root / "new", "dean/collision", "2.0.0")

            result = dossier(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(
                report["package_identity_conflicts"],
                [{
                    "name": "dean/collision",
                    "paths": sorted([
                        str((root / "old").resolve()),
                        str((root / "new").resolve()),
                    ]),
                }],
            )

    def test_checkpoint_plan_pins_dirty_state_without_mutating_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "dirty-package"
            initialise(root)
            (root / "src.php").write_text("<?php // changed\n")
            (root / "notes.md").write_text("authored note\n")
            before = snapshot(root / ".git")

            result = checkpoint_plan(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["read_only"])
            self.assertEqual(report["schema"], 1)
            repository = report["repositories"][0]
            self.assertEqual(repository["head"], git(root, "rev-parse", "HEAD"))
            self.assertEqual(repository["checkpoint_status"], "needed")
            self.assertEqual(repository["verdict"], "checkpoint-needed")
            self.assertEqual(repository["change_counts"], {
                "staged": 0,
                "modified": 1,
                "deleted": 0,
                "untracked": 1,
                "sensitive_withheld": 0,
            })
            self.assertEqual(repository["required_artifacts"], [
                "tracked-worktree-patch",
                "untracked-content-manifest",
            ])
            self.assertEqual(len(repository["status_digest"]), 64)
            self.assertEqual(before, snapshot(root / ".git"))

    def test_checkpoint_plan_withholds_sensitive_names_and_blocks_automation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sensitive-package"
            initialise(root)
            (root / ".env.local").write_text("VALUE=withheld\n")

            result = checkpoint_plan(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(".env.local", result.stdout)
            repository = json.loads(result.stdout)["repositories"][0]
            self.assertEqual(repository["checkpoint_status"], "blocked")
            self.assertEqual(repository["verdict"], "human-review-required")
            self.assertEqual(repository["change_counts"]["sensitive_withheld"], 1)
            self.assertEqual(repository["visible_changes"], [])
            self.assertIn("sensitive-paths-withheld", repository["issues"])

    def test_checkpoint_plan_puts_duplicate_identity_on_each_repository_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialise(root / "old", "dean/collision", "1.0.0")
            initialise(root / "new", "dean/collision", "2.0.0")

            result = checkpoint_plan(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(len(report["repositories"]), 2)
            for repository in report["repositories"]:
                self.assertEqual(repository["package_status"], "blocked")
                self.assertEqual(repository["verdict"], "human-review-required")
                self.assertIn("duplicate-package-identity", repository["issues"])

    def test_checkpoint_plan_writes_once_and_refuses_to_overwrite_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package"
            initialise(root)
            report_path = Path(temporary) / "checkpoint-plan.json"

            first = checkpoint_plan(root, output=report_path)
            original = report_path.read_bytes()
            second = checkpoint_plan(root, output=report_path)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(original)["schema"], 1)
            self.assertEqual(second.returncode, 2)
            self.assertIn("already exists", second.stderr)
            self.assertEqual(report_path.read_bytes(), original)

    def test_checkpoint_plan_fails_closed_when_repository_status_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "broken-worktree"
            root.mkdir()
            (root / ".git").write_text("gitdir: /path/that/does/not/exist\n")

            result = checkpoint_plan(root)

            self.assertEqual(result.returncode, 2)
            self.assertIn("could not read Git status", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
