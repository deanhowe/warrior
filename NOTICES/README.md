# Third-party notices

Warrior's own code (`bin/`, `lib/`, `skills/preservation/`, and everything
not listed below) is original work under this repo's own `LICENSE`.

## `skills/engineering/`, `skills/productivity/`, `skills/misc/git-guardrails-claude-code/`

Sourced from [mattpocock/skills](https://github.com/mattpocock/skills),
copyright (c) 2026 Matt Pocock, MIT License. The full original license text
is preserved verbatim in `mattpocock-skills-LICENSE` in this directory, as
required by its terms.

These are Matt Pocock's real engineering and productivity practices — TDD,
code review, spec/ticket flows, domain modelling, and more. Most imported
files remain byte-identical. Warrior deliberately renames two skills, adjusts
their internal references, adds Gitea support, and strengthens one Git safety
hook. Those transformations are declared in
`upstreams/mattpocock-skills.json`; they must not be described as upstream
content or allowed to drift silently.

Warrior's own `skills/preservation/` sits alongside these as a different
kind of skill — machine-preservation and git safety rather than day-to-day
engineering practice — and the two are meant to be used together, not to
compete.

## Provenance

Imported from the public mattpocock/skills repository at commit
`8b78b531ab965735c5dc74f6f7a219e1e37326df` (2026-08-13). Warrior carries a
pinned subset, not a Git submodule and not a live upstream checkout, so a
Warrior clone installs and works independently.

The machine-readable manifest records the exact source identity, selected
trees, renames, declared divergences, and Warrior-only files. Given any local
checkout of that source commit, this relationship can be verified without
network access or mutation:

```bash
python3 bin/warrior-upstream audit \
  --manifest upstreams/mattpocock-skills.json \
  --source /path/to/mattpocock-skills
```

The audit currently proves 70 byte-identical files, 9 declared divergences,
and 1 declared Warrior-only file. It does not fetch or update upstream.
