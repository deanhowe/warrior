# Safety contract

Every tool in this repository follows the same contract. This document states
it plainly enough to audit yourself against the source — not as reassurance,
as a checklist.

## 1. A read-only Git allowlist, checked on every token

`lib/warrior_forge.py` defines `GUARD_REQUIRE_VERB`, `GUARD_NO_VERB`, and
`GUARD_REQUIRE_OPTION` — a per-subcommand guard that inspects every argument,
not just the first one. That distinction is load-bearing: a guard that only
checks the first token after `remote` lets `git remote -v remove <name>`
through, because `-v` is a modifier, not the verb. Verified against real git
to actually delete a remote before this guard existed. The guard now rejects
any verb it hasn't explicitly allowlisted, and rejects bare/ambiguous forms
outright (`git stash` alone performs a stash, not a listing).

## 2. `git status` cannot silently mutate `.git/index`

Every status call passes `--no-optional-locks -c core.fsmonitor=`. Without
these, `git status` refreshes and writes back the on-disk stat cache — a real
mutation, not a no-op — and can execute a repository-supplied `fsmonitor`
program. A tool that claims to be read-only and isn't is worse than one that
admits it mutates.

## 3. `--output` cannot destroy anything

- **No overwrite without `--force`.** An existing file at the destination path
  is left alone unless you explicitly ask to replace it.
- **No writing inside a `.git` directory**, at any depth.
- **Restricted to data extensions** (`.json`, `.txt`, `.md`, `.log`) — a report
  is data; refusing other extensions closes a path to planting executable
  content via a mistyped flag.
- **No writing to a path whose filename starts with a dot** — a report should
  never masquerade as a dotfile.
- **No creating missing parent directories.** If the target directory doesn't
  exist, the tool refuses rather than `mkdir -p`ing an arbitrary tree.

## Why this list exists

An adversarial audit of the original version of this scanner found four real
bugs, including one where a mistyped `--output` overwrote a repository's
`.git/HEAD` and broke it. Every guard above traces to a finding like that one.
This is not a hypothetical threat model — it is a list of things that already
happened once, to this exact code, before the guard existed.

## What this contract does not cover

It covers these tools. It does not make any Git operation you perform
elsewhere safe, and it does not replace verifying an action's effect — an
exit code of `0` is not proof anything happened correctly; several findings
in this project's own history came from things that returned success while
doing the wrong thing, or nothing at all.

## Candidate history rewrites

`warrior-history build-candidate` is the deliberate exception to the tools'
read-only default. Its write authority is confined to one destination path
that must not exist. It never invokes `git-filter-repo` in the source:

- the source working tree must be clean;
- the plan pins source HEAD and every ref;
- the candidate is a `--mirror --no-local` clone at a new path;
- `git-filter-repo --force` runs only with the candidate as its working directory;
- the candidate retains no remote;
- requested paths must be absent across all candidate refs;
- candidate `git fsck --full` must pass;
- source HEAD and refs are rechecked after rewriting;
- failed or partial candidates are preserved, never automatically deleted.

The command does not replace a canonical repository, change a source ref,
delete a source object, push rewritten history, or force-push anything.

### Public projections

`warrior-history public-audit` reads every reachable blob, commit message, and commit identity
on one explicitly selected local branch. It returns exit code `3` when it sees
high-confidence token/key patterns, non-placeholder absolute user paths,
unapproved email addresses, or unapproved commit metadata. Reports contain
categories, counts, object IDs, and non-sensitive paths—not matched values or
email addresses. This is a heuristic release gate, not a mathematical proof
that arbitrary prose contains no private facts.

`public-plan` pins the source HEAD, every source ref, the selected branch, the
public name/email identity, the explicit sole-author policy, and the SHA-256 of
any private replacement file.
`build-public-candidate` then:

- clones only the selected branch, without tags or local hardlinks;
- removes the candidate remote before rewriting;
- rewrites author and committer name/email metadata to the chosen public owner;
- when `--sole-author` is explicit, strips `Co-Authored-By` trailers and proves
  no second contributor identity remains;
- optionally removes exact files/directories and applies replacements to blobs
  and commit messages;
- runs `git fsck --full` and the same public audit;
- verifies the source and all its refs are unchanged.

Replacement values stay in the caller-owned file outside the source; the plan
stores only its path and digest. The builder never pushes. A partial candidate
is retained for inspection.

## Pre-push preservation hook

`hooks/pre-push-preservation` blocks deletion, tag replacement and
non-fast-forward branch updates from Git's four-field pre-push input. It does
not search `$*` for `-f`: hook arguments contain the remote name and URL, so
that common pattern falsely blocks ordinary repositories whose names include
strings such as `-folio` or `-firefox`. The hook has deterministic tests for a
new ref, fast-forward, rewrite and deletion. Installation is deliberately
separate from the hook file because replacing an existing local hook requires
preserving and reviewing what was already there.

## Adversarial review coverage, stated per tool

Only `warrior-scan` has had the full treatment this contract describes:
independent agents actively trying to break it, live against real
repositories, not just reading the code. That's where the four bugs above
came from. `warrior-protect`, `warrior-classify`, and
`warrior-project checkpoint-plan` share its guarded
`--output` path and were spot-tested live against the same destructive
attempts, but haven't had an independent adversarial pass of their own.
`warrior-facts` has no write path at all, which is a different kind of
safety argument than "audited and found clean." `warrior-credits` has had
one real bug found this way — a shell-command construction that broke
cross-Python-version, fixed — but not a dedicated adversarial pass either.

Don't read "these guards exist" as "every tool has been proven to enforce
them under attack." Only one has, so far.
