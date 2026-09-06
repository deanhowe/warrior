from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "bin" / "warrior-laravel"


def snapshot(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for current, _directories, files in os.walk(path):
        for filename in files:
            item = Path(current) / filename
            result[str(item.relative_to(path))] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def dossier(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "dossier", str(root), "--json"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


class LaravelDossierCliTest(unittest.TestCase):
    def test_reports_laravel_signals_without_reading_or_leaking_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "local"
            (root / "config").mkdir(parents=True)
            (root / "routes").mkdir()
            (root / "tests" / "Feature").mkdir(parents=True)
            (root / "resources" / "js").mkdir(parents=True)
            (root / "vendor" / "secret-package").mkdir(parents=True)
            (root / ".tax").mkdir()
            (root / ".env").write_text("STRIPE_SECRET=sk_test_never-print-this\n")
            (root / "composer.json").write_text(json.dumps({
                "name": "deanhowe/moof-one",
                "type": "private",
                "require": {
                    "php": ">=8.3",
                    "laravel/framework": "^12.0",
                    "livewire/livewire": "^4.0",
                },
                "require-dev": {"pestphp/pest": "^4.0"},
                "repositories": {"private": {"type": "vcs", "url": "ssh://secret@example.invalid/private.git"}},
            }) + "\n")
            (root / "artisan").write_text("#!/usr/bin/env php\n")
            (root / "config" / "multitenancy.php").write_text("DomainTenantFinder::class\n")
            (root / "routes" / "web.php").write_text("Route::middleware('tenant')->get('/');\n")
            (root / "routes" / "channels.php").write_text("Broadcast::channel('chat');\n")
            (root / "tests" / "Feature" / "HealthTest.php").write_text("<?php\n")
            (root / "vendor" / "secret-package" / "token.txt").write_text("do-not-read\n")

            before = snapshot(root)
            result = dossier(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["read_only"])
            project = report["projects"][0]
            self.assertEqual(project["kind"], "laravel")
            self.assertEqual(project["composer"]["name"], "deanhowe/moof-one")
            self.assertEqual(project["composer"]["php_constraint"], ">=8.3")
            self.assertEqual(project["composer"]["laravel_constraint"], "^12.0")
            self.assertTrue(project["signals"]["multitenancy"])
            self.assertTrue(project["signals"]["broadcasting"])
            self.assertTrue(project["signals"]["livewire"])
            self.assertTrue(project["signals"]["tests"])
            self.assertTrue(project["boundaries"]["environment_file_present"])
            self.assertTrue(project["boundaries"]["tax_directory_present"])
            self.assertEqual(project["composer"]["repository_count"], 1)
            self.assertTrue(project["composer"]["repositories_declared"])
            self.assertNotIn("sk_test_never-print-this", result.stdout)
            self.assertNotIn("secret@example.invalid", result.stdout)
            self.assertNotIn("do-not-read", result.stdout)
            self.assertEqual(before, snapshot(root))

    def test_classifies_a_plain_php_library_without_guessing_laravel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package"
            root.mkdir()
            (root / "composer.json").write_text(json.dumps({
                "name": "deanhowe/example",
                "type": "library",
                "require": {"php": ">=8.2"},
            }) + "\n")

            result = dossier(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            project = json.loads(result.stdout)["projects"][0]
            self.assertEqual(project["kind"], "php")
            self.assertFalse(project["signals"]["laravel"])
            self.assertEqual(project["composer"]["php_constraint"], ">=8.2")


if __name__ == "__main__":
    unittest.main()
