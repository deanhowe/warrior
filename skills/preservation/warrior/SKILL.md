---
name: warrior
description: Find work that git is hiding from the user and plan a safe home for it. Use when auditing a machine for lost or at-risk work, before a bulk Git operation or project/package import, when asked where work lives, or when a developer is uncertain about Git state.
---

# Warrior

Read-only or additive tools live in `bin/`. Read `docs/SAFETY.md` before
proposing any command from this skill, and `docs/JOURNEY.md` for the full
guided path — this file is the terse operating summary.

## Order of operations

1. **`warrior-scan <roots...>`** first, always, before any other git
   operation on those roots. It is read-only; running it costs nothing and
   changes nothing.
2. Read the findings ranked CRITICAL → HIGH → MEDIUM → INFO. Do not propose
   fixing anything below CRITICAL/HIGH until those are handled.
3. For each finding, propose the exact recovery command from
   `docs/JOURNEY.md` Chapter 2. **Copy the content out before touching the
   original** — never apply a shelf, pop a stash, or reset toward a found
   commit as the first action.
4. Before importing an estate, run `warrior-project dossier <roots...>`, then
   `warrior-project checkpoint-plan <roots...>`. The plan pins current state
   and gives every repository a closure verdict; it does not create a
   checkpoint or grant authority to apply one.
5. Before publishing a repository, run `warrior-history public-audit` on the
   exact branch. If history needs changing, use `public-plan` and
   `build-public-candidate`; publish the verified candidate, never rewrite the
   private source in place.
6. Only after nothing is at risk: `warrior-facts` to orient on the estate,
   `warrior-protect` to give unprotected repos a home, `warrior-classify` to
   record what each repository is for.

## Non-negotiable rules

- Never run `git reset --hard`, `git clean`, `git stash drop`, `git gc`, or
  any force-push as part of this skill's own operation. If a recovery
  genuinely requires one of these, state that plainly and get explicit human
  confirmation naming the exact command — never infer permission for it.
- Never trust an exit code as proof something happened. `warrior-protect`
  verifies by checking the server's own refs; hold every tool in this
  project to that same standard when reporting results.
- If a repository or path looks like it might hold credentials, tax records,
  or other sensitive material, do not print sample filenames from it even if
  a tool would normally show them — the finding still matters, the sample
  doesn't need to be visible.
- Read-only by default, everywhere. Any command that isn't in a tool's
  documented read-only allowlist is out of scope for this skill.
