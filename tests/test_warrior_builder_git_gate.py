"""Tests for warrior_builder_git_gate — Builder's git-authority enforcement hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import warrior_builder_git_gate as gate  # noqa: E402


def _shell(cwd: str, command: str) -> dict:
    return {
        "hook_event_name": "preToolUse",
        "cwd": cwd,
        "session_id": "test-session",
        "tool_name": "shell",
        "tool_input": {"command": command},
    }


def _write_lease(worktree: Path, git: dict | None = None) -> None:
    lease_dir = worktree / ".warrior"
    lease_dir.mkdir(parents=True, exist_ok=True)
    data = {"allowed_files": []}
    if git is not None:
        data["git"] = git
    (lease_dir / "lease.json").write_text(json.dumps(data), encoding="utf-8")


def test_git_reset_is_always_blocked_even_with_a_permissive_lease(tmp_path):
    _write_lease(tmp_path, {"allow_commit": True, "remote": "moof"})

    code, message = gate.evaluate(_shell(str(tmp_path), "git reset --hard HEAD~1"))

    assert code == 2
    assert "destructive" in message


def test_git_clean_is_always_blocked(tmp_path):
    code, message = gate.evaluate(_shell(str(tmp_path), "git clean -fd"))

    assert code == 2
    assert "destructive" in message


def test_git_checkout_discard_is_blocked(tmp_path):
    code, _ = gate.evaluate(_shell(str(tmp_path), "git checkout -- ."))

    assert code == 2


def test_git_restore_working_tree_is_blocked(tmp_path):
    code, _ = gate.evaluate(_shell(str(tmp_path), "git restore app/Foo.php"))

    assert code == 2


def test_git_restore_staged_only_is_not_treated_as_discard(tmp_path):
    _write_lease(tmp_path, {"allow_commit": True})

    code, message = gate.evaluate(_shell(str(tmp_path), "git restore --staged app/Foo.php"))

    assert code == 0
    assert message == ""


def test_force_delete_branch_is_blocked(tmp_path):
    code, _ = gate.evaluate(_shell(str(tmp_path), "git branch -D feature/old"))

    assert code == 2


def test_stash_drop_is_blocked(tmp_path):
    code, _ = gate.evaluate(_shell(str(tmp_path), "git stash drop"))

    assert code == 2


def test_force_push_is_blocked_even_to_the_permitted_remote(tmp_path):
    _write_lease(tmp_path, {"remote": "moof"})

    code, message = gate.evaluate(_shell(str(tmp_path), "git push --force moof main"))

    assert code == 2
    assert "destructive" in message


def test_commit_blocked_without_lease(tmp_path):
    code, message = gate.evaluate(_shell(str(tmp_path), "git commit -m 'test'"))

    assert code == 2
    assert "not granted" in message


def test_commit_allowed_when_lease_grants_it(tmp_path):
    _write_lease(tmp_path, {"allow_commit": True})

    code, message = gate.evaluate(_shell(str(tmp_path), "git commit -m 'test'"))

    assert code == 0
    assert message == ""


def test_add_is_treated_the_same_as_commit(tmp_path):
    code, _ = gate.evaluate(_shell(str(tmp_path), "git add file.txt"))

    assert code == 2


def test_push_blocked_with_no_lease_at_all(tmp_path):
    code, message = gate.evaluate(_shell(str(tmp_path), "git push origin main"))

    assert code == 2
    assert "permitted destination" in message


def test_push_blocked_to_a_remote_other_than_the_permitted_one(tmp_path):
    _write_lease(tmp_path, {"remote": "moof"})

    code, message = gate.evaluate(_shell(str(tmp_path), "git push origin main"))

    assert code == 2
    assert "origin" in message


def test_push_allowed_to_the_exact_permitted_remote(tmp_path):
    _write_lease(tmp_path, {"remote": "moof"})

    code, message = gate.evaluate(_shell(str(tmp_path), "git push moof main"))

    assert code == 0
    assert message == ""


def test_push_with_no_remote_argument_fails_closed(tmp_path):
    _write_lease(tmp_path, {"remote": "moof"})

    code, _ = gate.evaluate(_shell(str(tmp_path), "git push"))

    assert code == 2


def test_non_git_shell_commands_are_never_blocked(tmp_path):
    code, message = gate.evaluate(_shell(str(tmp_path), "php artisan test"))

    assert code == 0
    assert message == ""


def test_non_shell_tool_calls_are_never_blocked(tmp_path):
    payload = {
        "hook_event_name": "preToolUse",
        "cwd": str(tmp_path),
        "session_id": "test-session",
        "tool_name": "write",
        "tool_input": {"path": "app/Foo.php"},
    }

    code, message = gate.evaluate(payload)

    assert code == 0
    assert message == ""


def test_missing_cwd_never_blocks(tmp_path):
    payload = {
        "hook_event_name": "preToolUse",
        "session_id": "test-session",
        "tool_name": "shell",
        "tool_input": {"command": "git reset --hard"},
    }

    code, message = gate.evaluate(payload)

    assert code == 0
    assert message == ""


def test_cli_end_to_end_via_stdin(tmp_path):
    _write_lease(tmp_path, {"remote": "moof"})
    script = ROOT / "bin" / "warrior-builder-git-gate"

    allowed_payload = json.dumps(_shell(str(tmp_path), "git push moof main"))
    allowed_result = subprocess.run(
        [sys.executable, str(script)], input=allowed_payload, text=True, capture_output=True,
    )
    assert allowed_result.returncode == 0

    blocked_payload = json.dumps(_shell(str(tmp_path), "git reset --hard"))
    blocked_result = subprocess.run(
        [sys.executable, str(script)], input=blocked_payload, text=True, capture_output=True,
    )
    assert blocked_result.returncode == 2
    assert "destructive" in blocked_result.stderr
