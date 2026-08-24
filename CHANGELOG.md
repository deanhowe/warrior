# Changelog

All notable Warrior releases are recorded here.

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
