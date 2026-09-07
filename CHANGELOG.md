# Changelog

All notable Warrior releases are recorded here.

## Unreleased

- Tighten the local `moof-laravel` system prompt with compact, executable
  Form Request and Pest answer shapes; evaluate candidate tags without
  replacing the stable model when the bounded score does not improve.
- Record a local-fleet comparison so an installed but unloadable or weaker
  DadsPC model is not promoted by name alone.
- Make the evaluator disable hidden Qwen 3-family thinking, matching Moof's
  MCP path and preventing false benchmark failures.
- Add explicit `compact` and `standard` evaluator profiles so response-budget
  results are comparable without making a long run the default.
- Record the first full six-check `standard` run (4/6 at the stable iMac
  digest) and keep it opt-in because each CPU prompt takes roughly a minute.
- Add `warrior-laravel eval`, a bounded loopback-only Ollama benchmark that
  records model digest, timing, token counters, and explicit Laravel idiom
  checks without pulling models or mutating projects; cap generated tokens so
  an open-ended prompt cannot turn a cheap probe into an unbounded run.
- Add portable Guardian, Wayfinder, and lease-bound Builder contracts with
  native Kiro, Claude, Copilot, and Codex profiles.
- Add `warrior-agents`, a zero-credit native validator and plan-first installer
  that refuses to overwrite a differing existing harness profile.
- Track Codex's five-hour and weekly allowance windows independently and avoid
  stale startup-gate matches when reading its TUI.
- Add `warrior-project checkpoint-plan`: a read-only closure ledger pinned to
  repository HEAD and exact status, with separate checkpoint/package states,
  per-repository verdicts, duplicate-identity blockers, sensitive-name
  withholding, and guarded JSON output.
- Preserve raw porcelain status so working-tree modifications cannot be
  misclassified as staged changes by stripped leading whitespace.
- Add exact-path history rewriting into a new disconnected candidate repository.
- Pin and re-verify source refs, reject dirty or drifted sources and existing
  destinations, remove candidate remotes, run full object verification, and
  prove requested paths are absent without changing the source.
- State macOS Tahoe 26 as Warrior's sole supported platform.
- Document direct CLI invocation through Warrior's `bin` directory on `PATH`.
- Add a fail-closed, value-withholding public history audit for one selected
  branch, including content and commit-identity checks.
- Add source-pinned public projection plans and disconnected candidate builds
  with single-branch export, metadata anonymisation, exact file/directory
  removal, private replacement-rule digests, full object verification, and a
  mandatory post-rewrite audit.
- Add an explicit sole-author projection policy that attributes every public
  commit to its declared owner and removes AI co-author trailers without
  changing private source history.

## 0.1.0 — 2026-08-24

Initial release of Warrior's preservation-first Git tooling and portable
engineering skill set.

### Shipped

- Ten command-line tools for discovering work at risk, inspecting an estate,
  protecting and classifying repositories, checking a forge, managing
  sidecars, measuring AI-harness credits, auditing knowledge sources,
  diagnosing repository history, and proving vendored upstream provenance.
- Seven preservation skills covering work recovery, authority, bootstrap,
  worktree leases, multi-harness exchange, package registries, and fork parity.
- Engineering and productivity skills derived from Matt Pocock's MIT-licensed
  skill set, with exact provenance, declared Warrior adaptations, and reviewed
  selective backports.
- Claude Code plugin and marketplace manifests, plus portable OpenAI agent
  metadata on the included skills.

### Deliberate boundaries

- `warrior-history` assesses rewrite candidates; it does not rewrite history.
- `warrior-upstream` proves and records source relationships; it does not fetch,
  merge, or overwrite vendored code.
- Forge protection and classification require explicit local configuration and
  never infer remote authority.
- The broader local control plane described in the roadmap is not part of this
  release.
