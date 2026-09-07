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

## Improving the model without pretending to train it

Use failed checks as evidence. Update the system prompt or add a verified
idiom to the Modelfile only when the underlying Laravel source and project
conventions support it. Rebuild the model, run the same benchmark, and keep
the digest and report with the change. A future LoRA/fine-tuning effort would
need a curated dataset, a held-out test set, and a real training/evaluation
pipeline; this tool is the release gate that makes that distinction visible.
