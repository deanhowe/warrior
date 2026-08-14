# Misc

Not part of the promoted plugin skill set — kept here because they're
directly useful, not because they're unfinished.

- **[git-guardrails-claude-code](./git-guardrails-claude-code/SKILL.md)** — sets up a Claude Code hook that blocks dangerous git commands (`push`, `reset --hard`, `clean`, `branch -D`) before they execute. Complements `skills/preservation/` directly: guardrails stop the destructive command from running at all; preservation finds and recovers what's already at risk. Sourced from [mattpocock/skills](https://github.com/mattpocock/skills) — see `NOTICES/`.

Only `git-guardrails-claude-code` was imported from upstream's `misc/`
bucket; the rest of that bucket (`migrate-to-shoehorn`, `scaffold-exercises`,
`setup-pre-commit`) is specific to Matt Pocock's own toolchain and wasn't
brought in.
