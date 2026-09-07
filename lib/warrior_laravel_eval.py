"""Cheap, read-only behavioural checks for a Laravel coding model.

This is an evaluation harness, not a training pipeline. It talks only to an
explicitly selected Ollama endpoint, defaults to loopback, never pulls a
model, and never writes to a project. The checks are deliberately small and
deterministic: they measure whether a model names verified Laravel idioms and
admits uncertainty instead of rewarding confident invention.
"""

from __future__ import annotations

import json
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SCHEMA = 1
DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "deanhowe/moof-laravel:latest"
MAX_RESPONSE_CHARS = 12_000
DEFAULT_MAX_TOKENS = 64
DEFAULT_CONTEXT_TOKENS = 4096


# Each ``required`` entry is an alternative group: one term from every group
# must occur. This keeps checks tolerant of harmless formatting differences
# while still making the acceptance rule explicit and reviewable.
BENCHMARKS: tuple[dict[str, Any], ...] = (
    {
        "id": "version-honesty",
        "prompt": (
            "Which Laravel major version are you assuming? Explain how you "
            "would verify it in this project before relying on a version-specific API."
        ),
        "required": (("composer.json", "composer show", "verify"),),
        "forbidden": (),
    },
    {
        "id": "nested-binding-scope",
        "prompt": (
            "How do I scope nested route model bindings to their parent in Laravel? "
            "Give the exact method name and a short usage example."
        ),
        "required": (("scopeBindings",),),
        "forbidden": ("Route::scopedBindings",),
    },
    {
        "id": "form-request",
        "prompt": (
            "What is a Laravel Form Request? Name the class method used for rules "
            "and show how a controller reads validated input."
        ),
        "required": (("FormRequest", "form request"), ("rules()", "rules"), ("validated()", "validated")),
        "forbidden": (),
    },
    {
        "id": "authorization-policy",
        "prompt": (
            "Show the idiomatic Laravel way to authorize updating a Post, using a "
            "policy and the controller."
        ),
        "required": (("policy", "Policy"), ("authorize", "Gate::allows")),
        "forbidden": (),
    },
    {
        "id": "queued-job",
        "prompt": (
            "How do I define and dispatch a queued Laravel job? Include the interface "
            "and the dispatch call."
        ),
        "required": (("ShouldQueue",), ("dispatch",)),
        "forbidden": (),
    },
    {
        "id": "pest-test",
        "prompt": (
            "Write a small Pest feature test for an authenticated user viewing a "
            "dashboard. Use the idiomatic test and authentication helpers."
        ),
        "required": (("it(", "test("), ("actingAs",), ("expect(", "assert")),
        "forbidden": (),
    },
)


def _loopback(host: str) -> bool:
    parsed = urlparse(host)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _cloud_model(model: str) -> bool:
    lowered = model.casefold()
    return lowered.endswith("-cloud") or ":cloud" in lowered or "-cloud:" in lowered


def validate_target(host: str, model: str, *, allow_network: bool = False) -> None:
    """Fail closed unless the evaluator is pointed at local Ollama."""
    if not _loopback(host) and not allow_network:
        raise ValueError("refusing non-loopback Ollama host; pass --allow-network explicitly")
    if _cloud_model(model):
        raise ValueError("refusing a cloud-backed model in the local evaluator")
    parsed = urlparse(host)
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Ollama host must be a base URL without a path or query")


def _request_json(
    host: str,
    path: str,
    payload: dict[str, Any] | None,
    timeout: float,
) -> dict[str, Any]:
    request = Request(
        host.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310: host is validated above
            body = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"Ollama request {path} failed: {error}") from error
    try:
        data = json.loads(body)
    except (UnicodeError, ValueError) as error:
        raise RuntimeError(f"Ollama request {path} returned invalid JSON") from error
    if not isinstance(data, dict):
        raise RuntimeError(f"Ollama request {path} returned a non-object")
    return data


def _check_response(case: dict[str, Any], response: str) -> dict[str, Any]:
    folded = response.casefold()
    required = []
    for alternatives in case["required"]:
        matched = next((term for term in alternatives if term.casefold() in folded), None)
        required.append({"terms": list(alternatives), "matched": matched})
    forbidden = [term for term in case["forbidden"] if term.casefold() in folded]
    passed = all(item["matched"] for item in required) and not forbidden
    return {
        "passed": passed,
        "required": required,
        "forbidden_matches": forbidden,
    }


def evaluate(
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    *,
    max_tasks: int | None = None,
    timeout: float = 120.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    context_tokens: int = DEFAULT_CONTEXT_TOKENS,
    allow_network: bool = False,
    benchmarks: Iterable[dict[str, Any]] = BENCHMARKS,
) -> dict[str, Any]:
    """Run a bounded benchmark and return a JSON-safe evidence report."""
    validate_target(host, model, allow_network=allow_network)
    selected = list(benchmarks)
    if max_tasks is not None:
        if max_tasks < 1:
            raise ValueError("max_tasks must be at least 1")
        selected = selected[:max_tasks]
    if not selected:
        raise ValueError("no benchmark tasks selected")
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")
    if context_tokens < 1024:
        raise ValueError("context_tokens must be at least 1024")

    shown = _request_json(host, "/api/show", {"name": model}, timeout)
    digest = shown.get("digest")
    if not isinstance(digest, str) or not digest:
        tags = _request_json(host, "/api/tags", None, timeout)
        models = tags.get("models") if isinstance(tags.get("models"), list) else []
        matching = next(
            (item for item in models if isinstance(item, dict) and item.get("name") == model),
            None,
        )
        digest = matching.get("digest") if isinstance(matching, dict) else None
    details = shown.get("details") if isinstance(shown.get("details"), dict) else {}
    results: list[dict[str, Any]] = []
    started = time.monotonic()
    for case in selected:
        case_started = time.monotonic()
        generated = _request_json(
            host,
            "/api/generate",
            {
                "model": model,
                "prompt": case["prompt"],
                "stream": False,
                "keep_alive": 0,
                "options": {
                    "temperature": 0,
                    "num_predict": max_tokens,
                    "num_ctx": context_tokens,
                },
            },
            timeout,
        )
        response = generated.get("response")
        if not isinstance(response, str):
            raise RuntimeError(f"Ollama benchmark {case['id']} returned no text")
        response_excerpt = response[:MAX_RESPONSE_CHARS]
        checks = _check_response(case, response_excerpt)
        results.append(
            {
                "id": case["id"],
                "passed": checks["passed"],
                "checks": checks,
                "response": response_excerpt,
                "truncated": len(response) > MAX_RESPONSE_CHARS,
                "elapsed_ms": round((time.monotonic() - case_started) * 1000),
                "prompt_eval_count": generated.get("prompt_eval_count"),
                "eval_count": generated.get("eval_count"),
            }
        )

    passed = sum(1 for result in results if result["passed"])
    return {
        "schema": SCHEMA,
        "tool": "warrior-laravel eval",
        "read_only": True,
        "network_scope": "loopback" if _loopback(host) else "explicitly-authorised-remote",
        "model": {
            "requested": model,
            "digest": digest,
            "family": details.get("family"),
            "parameter_size": details.get("parameter_size"),
            "quantization_level": details.get("quantization_level"),
        },
        "tasks": results,
        "summary": {
            "passed": passed,
            "total": len(results),
            "score": round(passed / len(results), 3),
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "max_tokens": max_tokens,
            "context_tokens": context_tokens,
        },
        "safety": [
            "No model pull, project file write, Git operation, or framework command is invoked.",
            "A passing check is evidence for these prompts, not proof of general Laravel competence.",
            "This configures prompts and measures behaviour; it does not fine-tune model weights.",
        ],
    }


def human(report: dict[str, Any]) -> str:
    model = report["model"]
    summary = report["summary"]
    lines = [
        "WARRIOR LARAVEL MODEL EVAL — read-only",
        f"Model: {model['requested']}",
        f"Digest: {model.get('digest') or '(not reported by Ollama)'}",
        f"Score: {summary['passed']}/{summary['total']} ({summary['score']:.0%})",
    ]
    for task in report["tasks"]:
        lines.append(f"  {'PASS' if task['passed'] else 'FAIL'} {task['id']} ({task['elapsed_ms']} ms)")
    lines.append("No model pull, project write, Git operation, or framework command was invoked.")
    return "\n".join(lines)
