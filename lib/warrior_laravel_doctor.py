"""Read-only fresh-clone diagnostics for a Laravel project's test environment.

Unlike `warrior_laravel.build_dossier` (which deliberately never touches
environment files), this module DOES open `.env` - but only to check whether
a given key is *present*, one boolean per key. It never reads, stores, or
returns a value from `.env`, so it carries no risk of leaking a secret even
though it looks at the file.

The checks here exist because a real, multi-hour debugging session
(local-starter, 2026-09-08) found that "tests fail on a fresh clone" is
almost always one of three things, none of which is an application bug:

  1. A multi-connection app (e.g. spatie/laravel-multitenancy's tenant/
     landlord split) gives each connection its OWN env var for host/port,
     with its own separate default. Overriding one connection in `.env` and
     assuming the others inherited the fix is silent and easy to miss - one
     connection quietly stays on its coded default (frequently a stale port
     from a previous local setup) while its siblings point somewhere else.
  2. A multitenancy app that provisions one physical database per tenant
     needs its DB user to hold *global* CREATE/DROP, not a grant scoped to
     a handful of named databases - the first test that creates a new
     tenant will fail with "Access denied ... to database <random-slug>"
     against a user that looks, at a glance, fully provisioned.
  3. Feature tests that render a Blade view calling `@vite(...)` fail with
     "Vite manifest not found" simply because nobody ran `npm install &&
     npm run build` yet. This is an environment gap, not a code defect.

See docs/engineering/... (none yet) - for now, the origin story lives in
Moof's own knowledge base at
.knowledge/harnesses/kiro/KIRO-AGENT-CONFIG-REALITY.md's sibling notes and
in agents/kiro/laravel-warrior.knowledge-seed.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA = 1

_CONNECTION_BLOCK = re.compile(
    r"^ {8}'(\w+)' => \[\n(.*?)\n {8}\],", re.MULTILINE | re.DOTALL
)
_ENV_CALL = re.compile(r"env\(\s*'([A-Z0-9_]+)'")


def _env_keys_set(env_path: Path, keys: set[str]) -> dict[str, bool]:
    """Return {key: is_present} for `keys`, without ever reading a value."""
    if not keys:
        return {}
    if not env_path.is_file():
        return {key: False for key in keys}
    try:
        text = env_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {key: False for key in keys}
    return {key: bool(re.search(rf"(?m)^{re.escape(key)}=", text)) for key in keys}


def _extract_env_key(block: str, field: str) -> str | None:
    line_match = re.search(rf"'{field}'\s*=>\s*(.+)", block)
    if not line_match:
        return None
    call_match = _ENV_CALL.search(line_match.group(1))
    return call_match.group(1) if call_match else None


def _parse_mysql_connections(database_config: Path) -> list[dict[str, Any]]:
    if not database_config.is_file():
        return []
    try:
        content = database_config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    connections = []
    for match in _CONNECTION_BLOCK.finditer(content):
        name, block = match.group(1), match.group(2)
        if "'driver' => 'mysql'" not in block:
            continue
        connections.append({
            "name": name,
            "host_env_key": _extract_env_key(block, "host"),
            "port_env_key": _extract_env_key(block, "port"),
        })
    return connections


def _check_connection_drift(root: Path) -> list[dict[str, str]]:
    connections = _parse_mysql_connections(root / "config" / "database.php")
    if len(connections) < 2:
        return []

    keys: set[str] = set()
    for conn in connections:
        for field in ("host_env_key", "port_env_key"):
            if conn[field]:
                keys.add(conn[field])
    presence = _env_keys_set(root / ".env", keys)

    findings = []
    for field, label in (("host_env_key", "host"), ("port_env_key", "port")):
        rows = [(c["name"], c[field]) for c in connections if c[field]]
        if len(rows) < 2:
            continue
        overridden = {name: presence.get(key, False) for name, key in rows}
        if len(set(overridden.values())) <= 1:
            continue
        set_names = sorted(n for n, v in overridden.items() if v)
        unset_names = sorted(n for n, v in overridden.items() if not v)
        findings.append({
            "check": f"db-{label}-drift",
            "severity": "warning",
            "message": (
                f"Mixed {label} configuration across mysql connections: "
                f"{', '.join(set_names)} override their {label} in .env, but "
                f"{', '.join(unset_names)} do not and will silently fall back "
                f"to their own coded default in config/database.php. If these "
                f"connections are meant to reach the same local server, set "
                f"the missing connection's {label} env var too."
            ),
        })
    return findings


def _check_vite_manifest(root: Path) -> list[dict[str, str]]:
    package_json = root / "package.json"
    if not package_json.is_file():
        return []
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
    if not isinstance(scripts, dict) or "build" not in scripts:
        return []

    uses_vite = False
    views_dir = root / "resources" / "views"
    if views_dir.is_dir():
        for blade in views_dir.rglob("*.blade.php"):
            try:
                if "@vite(" in blade.read_text(encoding="utf-8", errors="replace"):
                    uses_vite = True
                    break
            except OSError:
                continue
    if not uses_vite:
        return []

    manifest = root / "public" / "build" / "manifest.json"
    if manifest.is_file():
        return []
    return [{
        "check": "vite-manifest-missing",
        "severity": "warning",
        "message": (
            "Blade views call @vite(...) but public/build/manifest.json is "
            "missing - the frontend has never been built on this clone. Run "
            "`npm install && npm run build` before trusting any test that "
            "renders a page through this layout."
        ),
    }]


def _check_multitenancy_dynamic_db(root: Path) -> list[dict[str, str]]:
    composer_json = root / "composer.json"
    if not composer_json.is_file():
        return []
    try:
        data = json.loads(composer_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    require = data.get("require", {}) if isinstance(data, dict) else {}
    if not isinstance(require, dict) or "spatie/laravel-multitenancy" not in require:
        return []

    needle = re.compile(r"ensureDatabaseExists|CREATE DATABASE", re.IGNORECASE)
    for sub in ("database/factories", "database/migrations"):
        directory = root / sub
        if not directory.is_dir():
            continue
        for php_file in directory.rglob("*.php"):
            try:
                if needle.search(php_file.read_text(encoding="utf-8", errors="replace")):
                    return [{
                        "check": "multitenancy-dynamic-db",
                        "severity": "info",
                        "message": (
                            "spatie/laravel-multitenancy is present and "
                            f"{php_file.relative_to(root)} provisions a "
                            "database at runtime. The DB user needs GLOBAL "
                            "CREATE/DROP (e.g. GRANT ALL PRIVILEGES ON *.* TO "
                            "'<user>'@'%'), not a grant scoped to a handful "
                            "of named databases - the first test that "
                            "creates a new tenant will otherwise fail with "
                            "'Access denied ... to database <random-slug>'."
                        ),
                    }]
            except OSError:
                continue
    return []


def diagnose(root: Path) -> dict[str, Any]:
    root = Path(root)
    findings = [
        *_check_connection_drift(root),
        *_check_vite_manifest(root),
        *_check_multitenancy_dynamic_db(root),
    ]
    return {
        "schema": SCHEMA,
        "tool": "warrior-laravel doctor",
        "read_only": True,
        "root": str(root),
        "findings": findings,
    }
