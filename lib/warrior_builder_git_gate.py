"""A Kiro CLI preToolUse hook that structurally enforces Builder's git
authority - the second half of the gap `agents/roles/builder.md` names:
file-scope is adapter-enforced (`warrior_builder_lease_gate`), but "never
delete, clean, reset, force, discard, broaden scope, or push to an external
remote" was still prompt-only until this hook.

Reuses the exact schema already verified live for the lease gate: `tool_name`
is `"shell"` for command execution (confirmed real, 2026-09-08/09-10 across
this project's own sessions), `tool_input.command` is the shell string, and
`cwd` is the leased worktree root.

Mechanism: destructive git subcommands are blocked unconditionally - no
lease field can ever grant them, matching builder.md's flat "never" (this is
a categorical prohibition, not a situational grant). `git commit`/`git add`
are blocked unless `.warrior/lease.json` sets `"git": {"allow_commit": true}`.
`git push` is blocked unless the lease names an exact permitted remote via
`"git": {"remote": "<name>"}` AND the command targets that same remote AND
carries no force flag - a force flag is caught by the categorical block
above regardless of what the lease permits.

No lease file at all (same stance as the file-scope gate) means no git
authority whatsoever: every git write action is blocked.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

LEASE_RELATIVE_PATH = Path(".warrior") / "lease.json"

# Categorically forbidden regardless of any lease grant - matches builder.md's
# "never delete, clean, reset, force, discard" verbatim.
DESTRUCTIVE_PATTERN = re.compile(
    r"\bgit\s+("
    r"reset"
    r"|clean"
    r"|checkout\s+(--\s|\.\s*$|\.\s|--\s*$)"
    r"|restore(?!\s+--staged\b)"
    r"|branch\s+.*-D\b"
    r"|stash\s+(drop|clear)"
    r"|push\s+.*(--force\b|-f\b|--force-with-lease\b)"
    r"|update-ref\s+-d"
    r")",
    re.IGNORECASE,
)

COMMIT_PATTERN = re.compile(r"\bgit\s+(commit|add)\b", re.IGNORECASE)
PUSH_PATTERN = re.compile(r"\bgit\s+push\b(.*)$", re.IGNORECASE)


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
    if not isinstance(data, dict):
        return None
    return data


def _push_target_remote(command: str) -> str | None:
    """Best-effort extraction of the remote name from a `git push` command.

    `git push` with no remote argument pushes to the configured upstream,
    which this hook cannot resolve without inspecting the repo - treated as
    an unnamed remote (never matches a lease's permitted remote, fails
    closed) rather than guessed.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None

    try:
        push_idx = next(i for i, t in enumerate(tokens) if t == "push")
    except StopIteration:
        return None

    for token in tokens[push_idx + 1:]:
        if token.startswith("-"):
            continue
        return token
    return None


def evaluate(payload: dict[str, Any]) -> tuple[int, str]:
    """Return (exit_code, message). exit_code 0 allows the tool call through."""
    if payload.get("tool_name") != "shell":
        return 0, ""

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return 0, ""

    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0, ""

    if DESTRUCTIVE_PATTERN.search(command):
        return (
            2,
            "[builder-git-gate] Blocked: this looks like a destructive git "
            "action (reset/clean/checkout-discard/restore/force-delete-branch/"
            "stash-drop/force-push). Builder's contract forbids these "
            "unconditionally - no lease can grant them. Stop and report the "
            "conflict instead.",
        )

    lease = _read_lease(cwd)
    git_authority = lease.get("git") if isinstance(lease, dict) else None
    if not isinstance(git_authority, dict):
        git_authority = {}

    if COMMIT_PATTERN.search(command) and not git_authority.get("allow_commit", False):
        return (
            2,
            "[builder-git-gate] Blocked: staging/committing is not granted by "
            "this work item's lease (.warrior/lease.json has no "
            "git.allow_commit: true). Builder must not commit unless the "
            "work item explicitly grants it.",
        )

    if PUSH_PATTERN.search(command):
        permitted_remote = git_authority.get("remote")
        target_remote = _push_target_remote(command)
        if not isinstance(permitted_remote, str) or not permitted_remote or target_remote != permitted_remote:
            return (
                2,
                f"[builder-git-gate] Blocked: push to "
                f"'{target_remote or '(unnamed/upstream)'}' is not this work "
                f"item's permitted destination "
                f"({permitted_remote or 'none granted'}). Never push to an "
                "external remote without explicit authority.",
            )

    return 0, ""
