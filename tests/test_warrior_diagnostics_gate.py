"""Tests for warrior_diagnostics_gate — the php-lsp diagnostics enforcement hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import warrior_diagnostics_gate as gate  # noqa: E402


def _session_id() -> str:
    return f"test-{uuid.uuid4()}"


def _shell(session_id: str, command: str) -> dict:
    return {
        "hook_event_name": "preToolUse",
        "session_id": session_id,
        "tool_name": "shell",
        "tool_input": {"command": command},
    }


def _php_lsp(session_id: str, sub_tool: str) -> dict:
    return {
        "hook_event_name": "preToolUse",
        "session_id": session_id,
        "tool_name": f"@php-lsp/{sub_tool}",
        "tool_input": {},
    }


def test_allows_shell_test_run_when_nothing_is_owed(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()

    code, message = gate.evaluate(_shell(session, "php artisan test"))

    assert code == 0
    assert message == ""


def test_blocks_the_first_test_run_after_an_edit(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()

    edit_code, _ = gate.evaluate(_php_lsp(session, "edit_file"))
    test_code, message = gate.evaluate(_shell(session, "cd /repo && rtk php artisan test tests/Feature/X.php"))

    assert edit_code == 0
    assert test_code == 2
    assert "diagnostics" in message


def test_allows_the_second_test_attempt_after_being_blocked_once(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()

    gate.evaluate(_php_lsp(session, "edit_file"))
    first_code, _ = gate.evaluate(_shell(session, "php artisan test"))
    second_code, second_message = gate.evaluate(_shell(session, "php artisan test"))

    assert first_code == 2
    assert second_code == 0
    assert second_message == ""


def test_running_diagnostics_clears_the_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()

    gate.evaluate(_php_lsp(session, "edit_file"))
    gate.evaluate(_php_lsp(session, "diagnostics"))
    code, message = gate.evaluate(_shell(session, "php artisan test"))

    assert code == 0
    assert message == ""


def test_rename_symbol_also_marks_diagnostics_owed(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()

    gate.evaluate(_php_lsp(session, "rename_symbol"))
    code, message = gate.evaluate(_shell(session, "php artisan test"))

    assert code == 2
    assert "diagnostics" in message


def test_read_only_php_lsp_calls_do_not_mark_anything_owed(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()

    for sub_tool in ("hover", "definition", "references"):
        gate.evaluate(_php_lsp(session, sub_tool))

    code, message = gate.evaluate(_shell(session, "php artisan test"))

    assert code == 0
    assert message == ""


def test_pest_command_is_also_recognized_as_a_test_run(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()

    gate.evaluate(_php_lsp(session, "edit_file"))
    code, message = gate.evaluate(_shell(session, "./vendor/bin/pest --filter=Foo"))

    assert code == 2
    assert "diagnostics" in message


def test_non_test_shell_commands_are_never_blocked_even_when_owed(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()

    gate.evaluate(_php_lsp(session, "edit_file"))
    code, message = gate.evaluate(_shell(session, "git status"))

    assert code == 0
    assert message == ""


def test_sessions_are_isolated_from_each_other(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session_a = _session_id()
    session_b = _session_id()

    gate.evaluate(_php_lsp(session_a, "edit_file"))
    code, message = gate.evaluate(_shell(session_b, "php artisan test"))

    assert code == 0
    assert message == ""


def test_missing_session_id_never_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)

    payload = {"hook_event_name": "preToolUse", "tool_name": "shell", "tool_input": {"command": "php artisan test"}}
    code, message = gate.evaluate(payload)

    assert code == 0
    assert message == ""


def test_stale_state_files_get_pruned(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    session = _session_id()
    gate.evaluate(_php_lsp(session, "edit_file"))
    state_file = gate._state_path(session)
    assert state_file.is_file()

    far_future = time.time() + gate.STATE_MAX_AGE_SECONDS + 3600
    code, message = gate.evaluate(_shell(session, "git status"), now=far_future)

    assert code == 0
    assert message == ""
    assert not state_file.is_file()


def test_cli_end_to_end_via_stdin(tmp_path):
    session = _session_id()
    script = ROOT / "bin" / "warrior-diagnostics-gate"
    env = {**os.environ, "TMPDIR": str(tmp_path)}

    edit_payload = json.dumps({
        "hook_event_name": "preToolUse",
        "session_id": session,
        "tool_name": "@php-lsp/edit_file",
        "tool_input": {},
    })
    edit_result = subprocess.run(
        [sys.executable, str(script)], input=edit_payload, text=True, capture_output=True, env=env,
    )
    assert edit_result.returncode == 0

    test_payload = json.dumps({
        "hook_event_name": "preToolUse",
        "session_id": session,
        "tool_name": "shell",
        "tool_input": {"command": "php artisan test"},
    })
    test_result = subprocess.run(
        [sys.executable, str(script)], input=test_payload, text=True, capture_output=True, env=env,
    )
    assert test_result.returncode == 2
    assert "diagnostics" in test_result.stderr
