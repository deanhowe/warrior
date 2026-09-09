"""A Kiro CLI preToolUse hook that closes a real, live-proven gap.

Verified live against `laravel-warrior` (2026-09-08): the agent's own prompt
already says "run `diagnostics` after any php-lsp edit" - twice, in
increasingly explicit wording - and it still skipped that step both times
under live test, relying on the test suite alone to catch its mistakes. The
test suite happened to catch both bugs, but diagnostics is faster and would
catch classes of error (type mismatches, unreached branches) a single test
run won't exercise. Prompt wording alone hit a real ceiling on a cheap
model; this hook enforces the behavior structurally instead, using the same
block-and-suggest mechanism already proven to work twice tonight for the
`rtk` hook (the model reliably retries with the corrected command once a
tool call is rejected with a clear reason).

Mechanism, deliberately the simplest thing that could work:
  - A `@php-lsp/edit_file` or `@php-lsp/rename_symbol` call marks this
    session "diagnostics owed" and is never itself blocked.
  - A `@php-lsp/diagnostics` call clears it.
  - A `shell` call that looks like a test run, while diagnostics is owed,
    is rejected once with a message pointing at `@php-lsp/diagnostics` -
    exactly the `rtk` hook's own pattern, reusing a mechanism already
    proven to work rather than inventing an unproven one.

State is a small per-session JSON file, not a database - this hook needs
no more than a boolean, and Kiro CLI hooks are short-lived processes with
no shared memory across invocations.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

STATE_DIR = Path(tempfile.gettempdir()) / "warrior-diagnostics-gate"
STATE_MAX_AGE_SECONDS = 24 * 60 * 60
TEST_RUN_PATTERN = re.compile(r"\b(artisan\s+test|pest)\b", re.IGNORECASE)
EDIT_TOOL_SUFFIXES = ("/edit_file", "/rename_symbol")
DIAGNOSTICS_TOOL_SUFFIX = "/diagnostics"


def _state_path(session_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id) or "unknown"
    return STATE_DIR / f"{safe_id}.json"


def _prune_stale_state(now: float) -> None:
    if not STATE_DIR.is_dir():
        return
    for entry in STATE_DIR.iterdir():
        try:
            if now - entry.stat().st_mtime > STATE_MAX_AGE_SECONDS:
                entry.unlink()
        except OSError:
            continue


def _read_owed(session_id: str) -> bool:
    path = _state_path(session_id)
    if not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("owed", False)
    except (OSError, ValueError):
        return False


def _write_owed(session_id: str, owed: bool) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(session_id).write_text(json.dumps({"owed": owed}), encoding="utf-8")


def evaluate(payload: dict[str, Any], *, now: float | None = None) -> tuple[int, str]:
    """Return (exit_code, message). exit_code 0 allows the tool call through."""
    now = time.time() if now is None else now
    _prune_stale_state(now)

    session_id = payload.get("session_id")
    tool_name = payload.get("tool_name", "")
    if not isinstance(session_id, str) or not session_id:
        return 0, ""

    if any(tool_name.endswith(suffix) for suffix in EDIT_TOOL_SUFFIXES):
        _write_owed(session_id, True)
        return 0, ""

    if tool_name.endswith(DIAGNOSTICS_TOOL_SUFFIX):
        _write_owed(session_id, False)
        return 0, ""

    if tool_name == "shell":
        command = payload.get("tool_input", {}).get("command", "")
        if isinstance(command, str) and TEST_RUN_PATTERN.search(command) and _read_owed(session_id):
            # Clear state on the block itself, one-shot: if the model doesn't
            # act on the message and just retries the same test command, this
            # must not become an infinite block loop with no escape.
            _write_owed(session_id, False)
            return (
                2,
                "[diagnostics-gate] You edited a file via php-lsp and haven't run "
                "@php-lsp/diagnostics on it yet. Run diagnostics first - it's faster "
                "than a test run and catches errors a single test won't exercise - "
                "then retry this command.",
            )

    return 0, ""
