from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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


class ProjectDossierCliTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
