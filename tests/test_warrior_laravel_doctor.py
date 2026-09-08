"""Tests for warrior_laravel_doctor - the fresh-clone test-environment checks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from warrior_laravel_doctor import diagnose  # noqa: E402

DATABASE_PHP_DRIFT = """<?php

return [
    'default' => env('DB_CONNECTION', 'mysql'),

    'connections' => [

        'tenant' => [
            'driver' => 'mysql',
            'database' => env('DB_TESTING_DATABASE', null),
            'host' => env('DB_HOST', '127.0.0.1'),
            'port' => env('DB_PORT', '3325'),
            'username' => env('DB_USERNAME', 'tenant_db_user'),
        ],

        'landlord' => [
            'driver' => 'mysql',
            'database' => env('DB_LANDLORD_DATABASE', 'landlord_testing'),
            'host' => env('DB_LANDLORD_HOST', env('DB_HOST', '127.0.0.1')),
            'port' => env('DB_LANDLORD_PORT', '3325'),
            'username' => env('DB_LANDLORD_USERNAME', 'landlord_db_user'),
        ],

        'testing' => [
            'driver' => 'mysql',
            'host' => env('DB_HOST', '127.0.0.1'),
            'port' => env('DB_TESTING_PORT', '3325'),
            'database' => env('DB_TESTING_DATABASE', 'testing'),
            'username' => env('DB_USERNAME', 'root'),
        ],

    ],
];
"""

DATABASE_PHP_CONSISTENT = """<?php

return [
    'connections' => [

        'landlord' => [
            'driver' => 'mysql',
            'host' => env('DB_HOST', '127.0.0.1'),
            'port' => env('DB_PORT', '3306'),
        ],

        'testing' => [
            'driver' => 'mysql',
            'host' => env('DB_HOST', '127.0.0.1'),
            'port' => env('DB_PORT', '3306'),
        ],

    ],
];
"""


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_flags_port_drift_when_one_connection_env_key_is_unset(tmp_path):
    _write(tmp_path, "config/database.php", DATABASE_PHP_DRIFT)
    _write(tmp_path, ".env", "DB_HOST=127.0.0.1\nDB_PORT=3306\nDB_LANDLORD_PORT=3306\n")

    report = diagnose(tmp_path)

    port_findings = [f for f in report["findings"] if f["check"] == "db-port-drift"]
    assert len(port_findings) == 1
    assert "testing" in port_findings[0]["message"]
    assert "tenant" in port_findings[0]["message"] or "landlord" in port_findings[0]["message"]


def test_no_drift_finding_when_all_connections_consistently_overridden(tmp_path):
    _write(tmp_path, "config/database.php", DATABASE_PHP_CONSISTENT)
    _write(tmp_path, ".env", "DB_HOST=127.0.0.1\nDB_PORT=3306\n")

    report = diagnose(tmp_path)

    assert [f for f in report["findings"] if f["check"] == "db-port-drift"] == []


def test_no_drift_finding_when_no_env_file_exists_at_all(tmp_path):
    _write(tmp_path, "config/database.php", DATABASE_PHP_CONSISTENT)

    report = diagnose(tmp_path)

    assert [f for f in report["findings"] if f["check"] == "db-port-drift"] == []


def test_never_reads_or_returns_an_env_value(tmp_path):
    _write(tmp_path, "config/database.php", DATABASE_PHP_DRIFT)
    _write(tmp_path, ".env", "DB_HOST=127.0.0.1\nDB_PORT=super-secret-value-12345\nDB_LANDLORD_PORT=3306\n")

    report = diagnose(tmp_path)

    assert "super-secret-value-12345" not in str(report)


def test_flags_missing_vite_manifest_when_blade_uses_vite(tmp_path):
    _write(tmp_path, "package.json", '{"scripts": {"build": "vite build"}}')
    _write(tmp_path, "resources/views/layouts/guest.blade.php", "<html>@vite('resources/js/app.js')</html>")

    report = diagnose(tmp_path)

    manifest_findings = [f for f in report["findings"] if f["check"] == "vite-manifest-missing"]
    assert len(manifest_findings) == 1


def test_no_vite_finding_once_manifest_exists(tmp_path):
    _write(tmp_path, "package.json", '{"scripts": {"build": "vite build"}}')
    _write(tmp_path, "resources/views/layouts/guest.blade.php", "<html>@vite('resources/js/app.js')</html>")
    _write(tmp_path, "public/build/manifest.json", "{}")

    report = diagnose(tmp_path)

    assert [f for f in report["findings"] if f["check"] == "vite-manifest-missing"] == []


def test_no_vite_finding_when_no_blade_file_calls_vite(tmp_path):
    _write(tmp_path, "package.json", '{"scripts": {"build": "vite build"}}')
    _write(tmp_path, "resources/views/layouts/guest.blade.php", "<html>no asset pipeline here</html>")

    report = diagnose(tmp_path)

    assert [f for f in report["findings"] if f["check"] == "vite-manifest-missing"] == []


def test_flags_multitenancy_dynamic_db_when_provisioning_code_present(tmp_path):
    _write(
        tmp_path,
        "composer.json",
        '{"require": {"spatie/laravel-multitenancy": "^3.0"}}',
    )
    _write(
        tmp_path,
        "database/factories/TenantFactory.php",
        "<?php\nclass TenantFactory {\n  function f() { $this->schema('landlord')->ensureDatabaseExists($x); }\n}\n",
    )

    report = diagnose(tmp_path)

    grant_findings = [f for f in report["findings"] if f["check"] == "multitenancy-dynamic-db"]
    assert len(grant_findings) == 1
    assert grant_findings[0]["severity"] == "info"


def test_no_multitenancy_finding_without_the_package(tmp_path):
    _write(tmp_path, "composer.json", '{"require": {"laravel/framework": "^12.0"}}')
    _write(
        tmp_path,
        "database/factories/TenantFactory.php",
        "<?php\n// ensureDatabaseExists mentioned but package absent\n",
    )

    report = diagnose(tmp_path)

    assert [f for f in report["findings"] if f["check"] == "multitenancy-dynamic-db"] == []


def test_report_shape_is_read_only_and_stable(tmp_path):
    report = diagnose(tmp_path)

    assert report["schema"] == 1
    assert report["tool"] == "warrior-laravel doctor"
    assert report["read_only"] is True
    assert report["findings"] == []
