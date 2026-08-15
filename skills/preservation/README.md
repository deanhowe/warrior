# Preservation

Skills for not losing work, and for knowing what's actually on your machine.
The layer everything else in this plugin sits on top of.

## Model-invoked

- **[warrior](./warrior/SKILL.md)** — find work git is hiding (shelves, stashes, index-only content, unreachable commits, unmirrored repos) and give it a safe, verified home. Use before any bulk git operation, or when asked "where is X on my machine".
- **[warrior-authority](./warrior-authority/SKILL.md)** — the authority model for agents that touch git. What an agent may decide for itself versus what needs a named human approval, and why the difference matters before staging, committing, or pushing anything.
- **[warrior-bootstrap](./warrior-bootstrap/SKILL.md)** — guide a developer from a decade of scattered repositories to their own working local control plane: a private forge, a small brain, and an authority-bounded work queue for AI agents.
- **[warrior-worktree](./warrior-worktree/SKILL.md)** — lease a bounded slice of a repository to an agent instead of handing over the repository: baseline, file scope, validation contract, and why an expired lease is never auto-recovered.
- **[warrior-exchange](./warrior-exchange/SKILL.md)** — coordinate several AI harnesses against one estate using a private forge as the exchange. Branch-as-message, verifying which model actually answered, and why a task marked done is not work completed.

None of these five are user-invoked-only today; each has a description
written to trigger contextually. See `docs/preservation/` for the full
guided path (`docs/JOURNEY.md`) rather than a skill-by-skill docs page —
preservation is taught as one journey, not as isolated reference pages.
