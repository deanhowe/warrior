# Matt Pocock skills upstream review — 2026-08-24

Warrior remains based on the pinned public source commit
`8b78b531ab965735c5dc74f6f7a219e1e37326df`. This review compared that base
with two newer, linear descendants:

- `5b15a47f2d7150f545fbcacbfe381787fc0230dc`: 29 commits newer overall;
  11 commits and 49 files changed inside Warrior's selected import surface.
- `6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`: three commits newer than
  `5b15a47`; only an in-progress `retro` skill changed, outside Warrior's
  selected import surface.

## Decision

Selectively backport portable correctness improvements. Do not bulk-sync the
vendored tree merely because a newer source commit exists.

### Backported

- Respect user-invoked skill boundaries. A skill may tell the user to run
  `setup-engineering-skills` or `improve-codebase-architecture`; it must not
  silently invoke either one. Warrior retains the useful debugging
  post-mortem that upstream removed, but turns its handoff into a recommendation.
- Let `wait-what` follow `CONTEXT-MAP.md` to the correct domain context.
- Put a visible separator between multiple questions in one grilling round.

Exact source commits and affected paths are recorded in
`upstreams/mattpocock-skills.json` under `backports`.

### Not adopted

- The repository-wide replacement of em dashes is a source style decision,
  not a correctness change.
- The literal phrase `call the Skill tool` assumes a particular harness
  interface. Warrior must remain portable across harnesses whose skill
  invocation mechanisms differ.
- YAML description quoting changes followed upstream's punctuation rewrite;
  Warrior's retained descriptions do not contain the colon-space forms that
  required those changes.
- The `retro` skill remains in upstream's `in-progress` area and is outside
  Warrior's declared import surface. It should be assessed on its own merits,
  not absorbed incidentally during a provenance refresh.

## Result

This is a reviewed selective backport, not an upstream version bump. The
pinned base remains reproducible, and every resulting difference remains
declared and machine-auditable.
