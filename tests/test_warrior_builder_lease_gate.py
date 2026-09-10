"""Tests for warrior_builder_lease_gate — Builder's file-scope lease enforcement hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import warrior_builder_lease_gate as gate  # noqa: E402


def _write(cwd: str, path: str, command: str = "create") -> dict:
    return {
        "hook_event_name": "preToolUse",
        "cwd": cwd,
        "session_id": "test-session",
        "tool_name": "write",
        "tool_input": {"command": command, "path": path, "content": "x"},
    }


def _write_lease(worktree: Path, allowed_files: list[str]) -> None:
    lease_dir = worktree / ".warrior"
    lease_dir.mkdir(parents=True, exist_ok=True)
    (lease_dir / "lease.json").write_text(json.dumps({"allowed_files": allowed_files}), encoding="utf-8")


def test_blocks_every_write_when_no_lease_exists(tmp_path):
    code, message = gate.evaluate(_write(str(tmp_path), "app/Models/Foo.php"))

    assert code == 2
    assert "No lease found" in message


def test_allows_a_write_to_an_allow_listed_relative_path(tmp_path):
    _write_lease(tmp_path, ["app/Models/Foo.php"])

    code, message = gate.evaluate(_write(str(tmp_path), str(tmp_path / "app/Models/Foo.php")))

    assert code == 0
    assert message == ""


def test_blocks_a_write_outside_the_allow_list(tmp_path):
    _write_lease(tmp_path, ["app/Models/Foo.php"])

    code, message = gate.evaluate(_write(str(tmp_path), str(tmp_path / "app/Models/Bar.php")))

    assert code == 2
    assert "outside this lease" in message
    assert "Bar.php" in message


def test_allow_list_entries_are_resolved_relative_to_cwd(tmp_path):
    _write_lease(tmp_path, ["tests/Feature/FooTest.php"])

    code, _ = gate.evaluate(_write(str(tmp_path), "tests/Feature/FooTest.php"))

    assert code == 0


def test_path_traversal_outside_the_allow_list_is_still_blocked(tmp_path):
    _write_lease(tmp_path, ["app/Models/Foo.php"])

    escaped = str(tmp_path / "app" / "Models" / ".." / ".." / "Bar.php")
    code, message = gate.evaluate(_write(str(tmp_path), escaped))

    assert code == 2
    assert "outside this lease" in message


def test_non_write_tool_calls_are_never_blocked(tmp_path):
    payload = {
        "hook_event_name": "preToolUse",
        "cwd": str(tmp_path),
        "session_id": "test-session",
        "tool_name": "shell",
        "tool_input": {"command": "git status"},
    }

    code, message = gate.evaluate(payload)

    assert code == 0
    assert message == ""


def test_missing_cwd_never_blocks(tmp_path):
    payload = {
        "hook_event_name": "preToolUse",
        "session_id": "test-session",
        "tool_name": "write",
        "tool_input": {"command": "create", "path": "app/Models/Foo.php"},
    }

    code, message = gate.evaluate(payload)

    assert code == 0
    assert message == ""


def test_malformed_lease_json_is_treated_as_no_lease(tmp_path):
    lease_dir = tmp_path / ".warrior"
    lease_dir.mkdir()
    (lease_dir / "lease.json").write_text("not json", encoding="utf-8")

    code, message = gate.evaluate(_write(str(tmp_path), "app/Models/Foo.php"))

    assert code == 2
    assert "No lease found" in message


def test_lease_missing_allowed_files_key_is_treated_as_no_lease(tmp_path):
    lease_dir = tmp_path / ".warrior"
    lease_dir.mkdir()
    (lease_dir / "lease.json").write_text(json.dumps({"work_item": "WI-1"}), encoding="utf-8")

    code, message = gate.evaluate(_write(str(tmp_path), "app/Models/Foo.php"))

    assert code == 2
    assert "No lease found" in message


def test_empty_allow_list_blocks_every_write(tmp_path):
    _write_lease(tmp_path, [])

    code, message = gate.evaluate(_write(str(tmp_path), "app/Models/Foo.php"))

    assert code == 2
    assert "(none)" in message


def test_str_replace_command_is_checked_the_same_as_create(tmp_path):
    _write_lease(tmp_path, ["app/Models/Foo.php"])

    code, _ = gate.evaluate(_write(str(tmp_path), str(tmp_path / "app/Models/Foo.php"), command="str_replace"))

    assert code == 0


def test_cli_end_to_end_via_stdin(tmp_path):
    _write_lease(tmp_path, ["app/Models/Foo.php"])
    script = ROOT / "bin" / "warrior-builder-lease-gate"

    allowed_payload = json.dumps(_write(str(tmp_path), str(tmp_path / "app/Models/Foo.php")))
    allowed_result = subprocess.run(
        [sys.executable, str(script)], input=allowed_payload, text=True, capture_output=True,
    )
    assert allowed_result.returncode == 0

    blocked_payload = json.dumps(_write(str(tmp_path), str(tmp_path / "app/Models/Bar.php")))
    blocked_result = subprocess.run(
        [sys.executable, str(script)], input=blocked_payload, text=True, capture_output=True,
    )
    assert blocked_result.returncode == 2
    assert "outside this lease" in blocked_result.stderr
