"""Read-only Laravel/PHP evidence collection for Warrior.

The module deliberately reports structural evidence rather than pretending to
understand a project from its directory name.  It reads a small allow-list of
source manifests and marker files, never dependency trees or environment
files, and never invokes Git or a framework command.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


SCHEMA = 1
MAX_SOURCE_BYTES = 128_000
PACKAGE_NAME = re.compile(r"^[a-z0-9_.-]+/[a-z0-9_.-]+$")
SAFE_CONSTRAINT = re.compile(r"^[A-Za-z0-9*^~<>=|.,+_ -]{1,100}$")

KNOWN_FILES = (
    "composer.json",
    "artisan",
    "bootstrap/app.php",
    "config/multitenancy.php",
    "routes/web.php",
    "routes/api.php",
    "routes/channels.php",
    "tests",
    "resources/js",
    ".moof",
    ".knowledge",
    ".kiro",
    ".agents",
)


def _safe_constraint(value: Any) -> str | None:
    if not isinstance(value, str) or not SAFE_CONSTRAINT.fullmatch(value):
        return None
    return value


def _load_composer(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.is_file():
        return None, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None, ["invalid-composer-json"]
    if not isinstance(data, dict):
        return None, ["invalid-composer-json"]
    return data, []


def _markers(path: Path, needles: Iterable[str]) -> set[str]:
    """Return matching marker names without ever returning source text."""
    if not path.is_file():
        return set()
    try:
        source = path.read_bytes()[:MAX_SOURCE_BYTES].decode("utf-8", errors="replace")
    except OSError:
        return set()
    return {needle for needle in needles if needle in source}


def _present(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def _composer_evidence(data: dict[str, Any] | None, blockers: list[str]) -> dict[str, Any] | None:
    if data is None:
        return None
    name = data.get("name")
    package_name = name if isinstance(name, str) and PACKAGE_NAME.fullmatch(name) else None
    if package_name is None:
        blockers.append("invalid-or-missing-package-name")

    require = data.get("require") if isinstance(data.get("require"), dict) else {}
    require_dev = data.get("require-dev") if isinstance(data.get("require-dev"), dict) else {}
    require_names = sorted(
        key for key in require
        if isinstance(key, str) and (PACKAGE_NAME.fullmatch(key) or key.startswith("ext-"))
    )
    require_dev_names = sorted(
        key for key in require_dev
        if isinstance(key, str) and (PACKAGE_NAME.fullmatch(key) or key.startswith("ext-"))
    )
    repositories = data.get("repositories")
    repository_count = len(repositories) if isinstance(repositories, (list, dict)) else 0
    return {
        "name": package_name,
        "type": data.get("type") if isinstance(data.get("type"), str) else None,
        "php_constraint": _safe_constraint(require.get("php")),
        "laravel_constraint": _safe_constraint(require.get("laravel/framework")),
        "required_packages": require_names,
        "dev_packages": require_dev_names,
        "repository_count": repository_count,
        "repositories_declared": bool(repository_count),
    }


def inspect_project(root: Path) -> dict[str, Any]:
    """Build one deterministic, secret-safe dossier for ``root``."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"project root is not a directory: {root}")

    blockers: list[str] = []
    composer_data, composer_errors = _load_composer(root / "composer.json")
    blockers.extend(composer_errors)
    composer = _composer_evidence(composer_data, blockers)
    required = composer_data.get("require", {}) if isinstance(composer_data, dict) else {}
    required = required if isinstance(required, dict) else {}
    laravel_constraint = required.get("laravel/framework")

    artisan = _present(root, "artisan")
    laravel = bool(
        isinstance(laravel_constraint, str)
        or artisan
        or _present(root, "bootstrap/app.php")
    )
    package_names = set(composer["required_packages"] if composer else [])
    dev_package_names = set(composer["dev_packages"] if composer else [])
    all_packages = package_names | dev_package_names
    multitenancy_markers = _markers(
        root / "config/multitenancy.php",
        ("DomainTenantFinder", "TenantFinder", "tenancy"),
    )
    route_markers = _markers(
        root / "routes/web.php",
        ("Broadcast::", "middleware", "tenant"),
    )
    broadcasting = _present(root, "routes/channels.php") or "Broadcast::" in route_markers
    signals = {
        "laravel": laravel,
        "multitenancy": bool(multitenancy_markers),
        "broadcasting": broadcasting,
        "livewire": any(name.startswith("livewire/") for name in all_packages),
        "mingle": any("mingle" in name.lower() for name in all_packages),
        "tests": _present(root, "tests"),
        "frontend": _present(root, "resources/js"),
    }
    if not laravel and composer is not None:
        kind = "php"
    elif laravel:
        kind = "laravel"
    else:
        kind = "unknown"

    evidence_paths = [relative for relative in KNOWN_FILES if _present(root, relative)]
    boundaries = {
        "environment_file_present": any(root.glob(".env*")),
        "tax_directory_present": _present(root, ".tax"),
        "agent_state_present": any(
            _present(root, name) for name in (".kiro", ".agents", ".knowledge", ".moof")
        ),
        "dependency_trees_not_read": True,
        "environment_contents_not_read": True,
    }
    next_checks = [
        "Read the declared Composer package graph with credentials and repository URLs withheld.",
        "Inspect the listed route/config/test files directly before making semantic claims.",
    ]
    if composer and composer["repositories_declared"]:
        next_checks.append("Review Composer repository routing as a separate, authority-bounded check.")
    if not signals["tests"]:
        next_checks.append("Locate the project test runner before asking an agent to change code.")

    return {
        "schema": SCHEMA,
        "tool": "warrior-laravel",
        "read_only": True,
        "path": str(root),
        "kind": kind,
        "composer": composer,
        "signals": signals,
        "evidence_paths": evidence_paths,
        "boundaries": boundaries,
        "blockers": sorted(set(blockers)),
        "next_read_only_checks": next_checks,
        "safety": [
            "No environment, tax, dependency, build, or generated-file contents are returned.",
            "No Git, framework, network, model, or filesystem-mutating command is invoked.",
        ],
    }


def build_dossier(roots: Iterable[Path]) -> dict[str, Any]:
    projects = [inspect_project(Path(root)) for root in roots]
    return {
        "schema": SCHEMA,
        "tool": "warrior-laravel",
        "read_only": True,
        "roots": [project["path"] for project in projects],
        "projects": projects,
    }
