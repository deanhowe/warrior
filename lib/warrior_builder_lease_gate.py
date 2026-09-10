"""A Kiro CLI preToolUse hook that structurally enforces Builder's file-scope
lease.

`agents/roles/builder.md` says this in plain words: "Headless harness queues
must keep Builder disabled until those boundaries are enforced by the
adapter, not merely written into its prompt." Before this hook, that
enforcement did not exist anywhere - `warrior-builder`'s Kiro config relied
entirely on `fs_write: {"requireApproval": "always"}`, i.e. a human reading
every single write before approving it. That is a real control when Dean is
present, but it is not "the adapter enforces its lease" - it is a human
being the adapter, which is exactly what makes headless/queued Builder
dispatch unsafe today.

Two things below are verified live (2026-09-10), not assumed from docs:

1. The hook *matcher* name configured in the agent's `tools` list
   ("fs_write") is NOT the string the hook payload reports as `tool_name`.
   A real write call was captured via a dump-to-file preToolUse hook and its
   payload's `tool_name` is `"write"`. This module matches on that real
   value, not the matcher alias.
2. The real `tool_input` for a write call is
   `{"command": "create"|..., "path": "<absolute path>", "content": "..."}`.
   `path` is the field this hook checks against the lease.

Mechanism, deliberately the simplest thing that enforces the actual
contract: a lease is a JSON file at `<cwd>/.warrior/lease.json` containing
`{"allowed_files": [...]}`, paths relative to the worktree root (`cwd`) or
absolute. Whoever grants Builder a lease - a human, or dispatch tooling -
writes this file before Builder ever gets a live turn. No lease file at all
means Builder has no authorised scope, matching builder.md's "must refuse to
start without ... an exact file allow-list": every write is blocked. A
lease with an allow-list blocks any write whose resolved path falls outside
it and allows everything else through.

This covers file-scope enforcement only. Git-authority enforcement (never
force, reset, clean, discard, or push externally) is a real, separate,
not-yet-built piece of the same contract - nothing here covers that.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LEASE_RELATIVE_PATH = Path(".warrior") / "lease.json"
WRITE_TOOL_NAME = "write"


def _lease_path(cwd: str) -> Path:
    return Path(cwd) / LEASE_RELATIVE_PATH


def _read_lease(cwd: str) -> dict[str, Any] | None:
    path = _lease_path(cwd)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("allowed_files"), list):
        return None
    return data


def _resolve(cwd: str, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = Path(cwd) / candidate
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def evaluate(payload: dict[str, Any]) -> tuple[int, str]:
    """Return (exit_code, message). exit_code 0 allows the tool call through."""
    if payload.get("tool_name") != WRITE_TOOL_NAME:
        return 0, ""

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return 0, ""

    tool_input = payload.get("tool_input")
    raw_path = tool_input.get("path") if isinstance(tool_input, dict) else None
    if not isinstance(raw_path, str) or not raw_path:
        return 0, ""

    lease = _read_lease(cwd)
    if lease is None:
        return (
            2,
            "[builder-lease-gate] No lease found at .warrior/lease.json in this "
            "worktree. Builder must refuse to start without an exact file "
            "allow-list - stop and ask for one; do not write anything.",
        )

    allowed_files = [f for f in lease["allowed_files"] if isinstance(f, str)]
    allowed = {_resolve(cwd, f) for f in allowed_files}
    target = _resolve(cwd, raw_path)

    if target not in allowed:
        allowed_display = ", ".join(sorted(allowed_files)) or "(none)"
        return (
            2,
            f"[builder-lease-gate] '{raw_path}' is outside this lease's file "
            f"allow-list ({allowed_display}). Never broaden scope - stop and "
            "report the conflict instead of writing here.",
        )

    return 0, ""
