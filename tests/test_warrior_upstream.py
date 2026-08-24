from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-upstream"


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
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
    return result.stdout.strip()


def run_audit(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "audit", *args],
        check=False,
        capture_output=True,
        text=True,
    )


class UpstreamAuditCliTest(unittest.TestCase):
    def test_proves_identical_files_renames_declared_divergence_and_local_extras(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            vendor = root / "vendor"
            source.mkdir()
            vendor.mkdir()
            run_git(source, "init", "-b", "main")
            (source / "skills" / "a").mkdir(parents=True)
            (source / "skills" / "a" / "same.md").write_text("same\n")
            (source / "skills" / "a" / "old-name.md").write_text("upstream\n")
            run_git(source, "add", "skills/a")
            run_git(source, "commit", "-m", "source fixture")
            source_commit = run_git(source, "rev-parse", "HEAD")

            (vendor / "skills" / "a").mkdir(parents=True)
            (vendor / "skills" / "a" / "same.md").write_text("same\n")
            (vendor / "skills" / "a" / "new-name.md").write_text("deliberate fork\n")
            (vendor / "skills" / "a" / "local.md").write_text("local extension\n")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": 1,
                "name": "fixture-skills",
                "source_url": "ssh://example.invalid/source.git",
                "source_commit": source_commit,
                "vendor_root": str(vendor),
                "mappings": [{"source": "skills/a", "destination": "skills/a"}],
                "renames": {"skills/a/old-name.md": "skills/a/new-name.md"},
                "expected_divergences": {
                    "skills/a/new-name.md": "product-neutral command name"
                },
                "expected_extras": {
                    "skills/a/local.md": "local integration"
                },
            }))

            result = run_audit("--manifest", str(manifest), "--source", str(source), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["healthy"])
            self.assertEqual(report["source_commit_actual"], source_commit)
            self.assertTrue(report["source_clean"])
            self.assertEqual(report["counts"], {
                "declared_divergence": 1,
                "expected_extra": 1,
                "identical": 1,
                "missing": 0,
                "stale_declaration": 0,
                "unexpected_difference": 0,
                "unexpected_extra": 0,
            })

            (source / "skills" / "a" / "same.md").write_text("dirty source\n")
            dirty_source = run_audit("--manifest", str(manifest), "--source", str(source), "--json")
            self.assertEqual(dirty_source.returncode, 1, dirty_source.stderr)
            self.assertFalse(json.loads(dirty_source.stdout)["source_clean"])
            (source / "skills" / "a" / "same.md").write_text("same\n")

            (vendor / "skills" / "a" / "same.md").write_text("silent drift\n")
            (vendor / "skills" / "a" / "surprise.md").write_text("undeclared\n")
            drifted = run_audit("--manifest", str(manifest), "--source", str(source), "--json")
            self.assertEqual(drifted.returncode, 1, drifted.stderr)
            drifted_report = json.loads(drifted.stdout)
            self.assertFalse(drifted_report["healthy"])
            self.assertEqual(drifted_report["counts"]["unexpected_difference"], 1)
            self.assertEqual(drifted_report["counts"]["unexpected_extra"], 1)

            (source / "later.md").write_text("later source state\n")
            run_git(source, "add", "later.md")
            run_git(source, "commit", "-m", "advance source")
            advanced = run_audit("--manifest", str(manifest), "--source", str(source), "--json")
            self.assertEqual(advanced.returncode, 1, advanced.stderr)
            self.assertFalse(json.loads(advanced.stdout)["source_commit_matches"])


if __name__ == "__main__":
    unittest.main()
