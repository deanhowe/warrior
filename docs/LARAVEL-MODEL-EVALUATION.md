# Laravel model evaluation

`warrior-laravel eval` is the cheap feedback loop for a local Laravel model.
It is deliberately an evaluation harness, not a claim that a prompt-configured
7B model has been fine-tuned or trained.

## Run it

The default is the local iMac Ollama server and the curated model:

```bash
warrior-laravel eval --max-tasks 3
warrior-laravel eval --json > ~/Desktop/warrior-laravel-eval.json
```

The command first asks Ollama for the model's own digest and details, then runs
a bounded set of six small prompts. Each response is checked for explicit,
reviewable evidence: version verification, the real `scopeBindings()` method,
Form Requests, policies, queued jobs, and Pest structure. The nested-binding
check also fails if the known fabricated `Route::scopedBindings()` spelling
appears.

`--max-tasks`, `--max-tokens`, and `--context-tokens` are the cost and time
controls. The evaluator caps each response at 64 generated tokens and each
request at a 4096-token context by default, so an open-ended model cannot run
away with the machine. Start with one or three tasks when
iterating on a Modelfile, then run all six before recording a release claim.
The evaluator uses `temperature: 0`, `stream: false`, and `keep_alive: 0` so a
run is reproducible and does not leave a model resident unnecessarily.

## Safety and interpretation

- Only loopback Ollama hosts are accepted by default. A non-loopback host
  requires the visible `--allow-network` switch.
- Cloud-backed model names are rejected. The evaluator will not silently
  spend a paid Ollama route.
- It never pulls a model, edits a project, runs Git, invokes Artisan, or
  writes a report file. Redirecting JSON to a path is the caller's choice.
- The report includes the requested model, Ollama digest, elapsed time, token
  counters when Ollama supplies them, each response (bounded), and the exact
  check results.
- A pass means only that the model satisfied these prompts. It is not proof
  of general Laravel competence, security, or suitability for autonomous code
  changes.

## First baseline

On 2026-09-07 the current iMac model `deanhowe/moof-laravel:latest` reported
digest `84b14d7d8c690d06d2f483c379abab1335534fce32996c7c8b10fb98e14ee552`.
Running all six checks with `--max-tokens 32 --context-tokens 2048` scored
**3/6 (50%)**: version honesty, nested binding scope, and policy authorization
passed; Form Requests, queued jobs, and Pest structure did not meet the
checks. This is a constrained baseline, not a release claim. Keep the command,
digest, and score together when comparing a future Modelfile or weight change.

## Compact-prompt refinement (2026-09-07)

The Modelfile now asks for the exact operational shape first: Form Request
answers should reach `$request->validated()`, Pest answers should begin with an
`it(..., function () { ... })` closure containing `actingAs()`, and short
answers should not spend their budget describing the model. A candidate was
built under the local-only tag `deanhowe/moof-laravel:candidate-20260907b`
while the previous release was preserved as
`deanhowe/moof-laravel:pre-compact-prompt-20260907`.

At the evaluator's 64-token cap, the stable model scored **4/6 (67%)**
(version honesty, nested binding scope, policy authorization, and queued jobs);
the candidate still scored **0/2** on the two short-answer cases because the
responses were truncated before all required terms. The candidate has not been
promoted to `:latest`. This is an honest response-budget limitation, not a
claim of training or general Laravel competence.

## Local fleet comparison (2026-09-07)

The same six checks were used to test other already-installed local models;
the evaluator was explicitly allowed to use DadsPC's LAN endpoint, but no
model was pulled or created there:

| Endpoint/model | Result | Evidence |
|---|---:|---|
| iMac `deanhowe/moof-laravel:latest` | 4/6 (67%) | version honesty, nested binding scope, policy, and queued job passed at 64 tokens |
| DadsPC `qwen3-coder:30b` | unavailable | Ollama HTTP 500: out-of-memory allocating a 12.7 GB CUDA-host buffer |
| DadsPC `deepcoder:14b` | 2/6 (33%) | form request and policy checks passed; the other four failed at 64 tokens |
| DadsPC `qwen3.5:latest` | 0/6 | all six checks failed at 64 tokens |

Moof therefore keeps the named `laravel` route on the iMac curated model. A
future DadsPC route needs a successful model-load health check and a fresh
benchmark result; an installed model name alone is not sufficient evidence.

## Improving the model without pretending to train it

Use failed checks as evidence. Update the system prompt or add a verified
idiom to the Modelfile only when the underlying Laravel source and project
conventions support it. Rebuild the model, run the same benchmark, and keep
the digest and report with the change. A future LoRA/fine-tuning effort would
need a curated dataset, a held-out test set, and a real training/evaluation
pipeline; this tool is the release gate that makes that distinction visible.
