from __future__ import annotations

import copy
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "bin" / "warrior-laravel"
sys.path.insert(0, str(ROOT / "lib"))

from warrior_laravel_eval import (  # noqa: E402
    BENCHMARKS,
    DEFAULT_MODEL,
    _check_response,
    evaluate,
    validate_target,
)


class LaravelEvalUnitTests(unittest.TestCase):
    def test_checks_exact_scope_bindings_and_rejects_fabricated_static_api(self):
        case = next(item for item in BENCHMARKS if item["id"] == "nested-binding-scope")
        self.assertTrue(_check_response(case, "Use ->scopeBindings() on the route group.")["passed"])
        self.assertFalse(_check_response(case, "Call Route::scopedBindings() statically.")["passed"])

    def test_local_policy_rejects_cloud_models_and_remote_hosts(self):
        with self.assertRaises(ValueError):
            validate_target("http://127.0.0.1:11434", "gpt-oss:20b-cloud")
        with self.assertRaises(ValueError):
            validate_target("http://10.0.0.94:11434", DEFAULT_MODEL)
        validate_target("http://10.0.0.94:11434", DEFAULT_MODEL, allow_network=True)

    def test_evaluation_records_identity_and_never_mutates_a_project(self):
        calls: list[tuple[str, dict[str, object]]] = []
        responses = {
            "/api/show": {"details": {"family": "qwen2"}},
            "/api/tags": {"models": [{"name": DEFAULT_MODEL, "digest": "sha256:test"}]},
            "/api/generate": {
                "response": "Use ->scopeBindings() on the route group.",
                "eval_count": 7,
                "prompt_eval_count": 12,
            },
        }

        def fake_request(host: str, path: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
            calls.append((path, copy.deepcopy(payload)))
            return responses[path]

        with patch("warrior_laravel_eval._request_json", side_effect=fake_request):
            benchmark = [item for item in BENCHMARKS if item["id"] == "nested-binding-scope"]
            report = evaluate(max_tasks=1, benchmarks=benchmark)

        self.assertEqual(report["model"]["digest"], "sha256:test")
        self.assertEqual(report["summary"]["passed"], 1)
        self.assertTrue(report["read_only"])
        self.assertEqual([path for path, _payload in calls], ["/api/show", "/api/tags", "/api/generate"])
        self.assertFalse(calls[2][1]["stream"])
        self.assertEqual(calls[2][1]["keep_alive"], 0)
        self.assertEqual(calls[2][1]["options"]["num_predict"], 64)
        self.assertEqual(calls[2][1]["options"]["num_ctx"], 4096)

    def test_qwen3_disables_hidden_thinking_for_answer_measurement(self):
        responses = {
            "/api/show": {"details": {"family": "qwen3"}},
            "/api/tags": {"models": [{"name": "qwen3.5:latest", "digest": "sha256:qwen3"}]},
            "/api/generate": {"response": "scopeBindings()"},
        }

        def fake_request(host: str, path: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
            return responses[path]

        with patch("warrior_laravel_eval._request_json", side_effect=fake_request) as request:
            benchmark = [item for item in BENCHMARKS if item["id"] == "nested-binding-scope"]
            evaluate(model="qwen3.5:latest", max_tasks=1, benchmarks=benchmark)

        self.assertFalse(request.call_args_list[-1].args[2]["think"])

    def test_cli_rejects_zero_tasks_without_contacting_ollama(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "eval", "--max-tasks", "0", "--json"],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("at least 1", result.stderr)


if __name__ == "__main__":
    unittest.main()
