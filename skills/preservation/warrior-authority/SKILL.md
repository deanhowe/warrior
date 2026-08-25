---
name: warrior-authority
description: The authority model for agents that touch Git. Use before staging, committing, creating a branch or worktree, pushing, mirroring, migrating, deleting, or reviewing any proposed Git operation — and when deciding what an agent is allowed to do in someone else's repository.
---

# Warrior authority model

An agent that can edit files is not thereby allowed to commit them. An agent
that can commit is not thereby allowed to push. Nothing at all confers
permission to delete.

Most agent damage is not a wrong edit. It is a correct edit applied with
authority the agent assumed it had.

## The five authorities are independent

| Authority | Grants | Never implies |
|---|---|---|
| **read** | inspect files, history, refs | edit |
| **edit** | change the working tree | commit |
| **commit** | write objects to local history | push |
| **push** | publish to one named remote | any other remote |
| **delete** | remove branches, worktrees, files, stashes | anything, ever — always separately requested |

Read them as a ladder that does not climb itself. Holding rung three tells you
nothing about rung four. An agent that reasons "I was allowed to commit, so
presumably I may push" has invented authority.

Push authority is **per remote**, not global. Approval to push `origin` is not
approval to push `upstream`, a fork, or a private mirror.

## Authority is recorded, not inferred

Authority must live in a durable record the agent reads, not in the agent's
recollection of the conversation. Give every unit of work an explicit row:

```
work_item_id        what this change belongs to
repository_path     the canonical repository that owns the files
branch              the branch this work may touch
file_scope          the exact paths in scope, enumerated
commit_authority    none | local
push_authority      none | approved
push_remote         the one named remote, when push is approved
```

Two consequences follow, and both matter:

- Authority is scoped to **this repository and this work item**, not to the
  agent. The same agent may hold `commit=local push=approved` on one work item
  and `commit=none` on another, at the same time.
- An agent that cannot find a record grants itself nothing. Absence of a
  record is absence of authority, never a default of convenience.

## Never infer authority from

- being able to edit the file;
- the repository being private;
- the repository being the agent's "own" project;
- a plan having been shown to the human and not objected to — **showing a plan
  is not consent**;
- a previous approval for a similar operation;
- the operation being reversible in principle;
- the work being obviously correct;
- the human being busy, absent, or asleep.

## Evidence standards

**A zero exit code is not proof of anything.** Verify the state you intended,
by observing that state.

- **Push landed?** Confirm the local HEAD commit appears among the remote's
  refs (`git ls-remote <remote>` and compare against `git rev-parse HEAD`).
  Never trust the push command's exit status. A push into an already
  up-to-date repository can exit 0 having transmitted nothing, which is
  indistinguishable from success unless you check the refs.
- **Transport matters.** A filesystem path may support `ls-remote`, `clone`
  and `fetch` while rejecting every push at the receiving hook. Validate the
  transport you intend to publish over, and prefer SSH for publishing.
- **Never push into a pull-mirror.** A pull-mirror is overwritten from its
  upstream on a schedule. Anything pushed directly into one is destroyed at
  the next sync, silently and completely. Detect mirror status before
  publishing and refuse rather than proceed.
- **A mirror protects committed objects only.** Shelves, index-only blobs,
  stashes, untracked files and unreachable commits have no protection from any
  remote whatsoever. Never describe a repository as "backed up" on the
  strength of a mirror existing.
- **Builds are not behaviour.** Compiling, and passing type checks, are not
  evidence a change works. Say what you verified and what you did not.

## Model identity is part of authority

When work is delegated to a model through an adapter, record the model that
**answered**, not only the model that was **requested**. Adapters fall back.

A real, observed case: a session was requested as one vendor's large model at
high reasoning effort; the error returned named an entirely different vendor's
small model, which does not accept effort settings at all. The request and the
responder had diverged silently. Any claim about capability, cost, or quality
based on the requested model would have been false.

So keep `requested_model` and `model` as separate fields, treat a mismatch as
a first-class incompatibility, and preserve that record as evidence rather
than retrying over it.

## Before any Git mutation, state

1. the work item and its bounded objective;
2. the canonical repository, and the owner of every nested repository touched;
3. current branch, HEAD, upstream, ahead/behind, remotes;
4. pre-existing dirty or untracked files, explicitly **excluded**;
5. the exact files proposed, enumerated — never `git add .`, never `-A`;
6. the validation performed, and its result;
7. the proposed commit message;
8. whether commit authority exists for this exact scope;
9. whether push authority exists, and the named remote;
10. recovery facts that do not depend on uncommitted work being mirrored.

If any of these is unknown, the correct output is a **checkpoint plan**, not an
operation.

## Inspection must not mutate

Read-only means read-only in practice, not in intent:

- `git status` refreshes and writes back the index, and can execute
  repository-supplied hooks and fsmonitor programs. Pass
  `--no-optional-locks -c core.fsmonitor=` on every call.
- Bare `git branch` and bare `git worktree` list. **Bare `git stash` does
  not** — it removes uncommitted work from the working tree and reports only
  that it stashed. Guard subcommands by allowlist, and require an explicit
  read-only verb for those that mutate when bare.
- Guard on the first **non-option** token, not on the second argument.
  `git remote -v remove <name>` really does delete a remote; a guard that
  only inspected the second argument would pass it through as "just `-v`".
- Do not execute a version probe or helper that resolves to a path inside the
  repository being inspected. Report it and skip it.

## Preserve by default

Dormant, compatibility, licensed, generated, backup, archive and `tmp/`
material is preserved unless deletion is explicitly requested for those exact
paths. `tmp/` in particular routinely holds work in progress; a tool that
treats it as debris is how that work gets destroyed.

Nothing an inspection reports is a deletion candidate.

## The rule that cost the most to learn

A tool built specifically to prevent data loss destroyed data during its own
audit, because one output flag was mistyped and overwrote a repository's
`HEAD`.

Anything that touches Git gets adversarially verified — tested by someone
trying to make it fail, not by someone confirming it works. There is no
exception for tools whose purpose is safety, and there is no exception for
small changes.

## Verify remote identity by root commit, never by name

A remote's name, and the name of the repo it points at, are both just
strings someone typed — a prior tool, an earlier session, a copy-paste. They
can be wrong and still look completely plausible. The only fact that can't
be faked is shared history.

Before trusting a private-forge/origin-equivalent remote you didn't just set
yourself — and *always* before pointing it at something new — verify by
root commit, not name:

```
git rev-list --max-parents=0 HEAD                       # this repo's root
git fetch <candidate-url> <branch>                       # do NOT set the
git rev-list --max-parents=0 FETCH_HEAD                  # remote yet
```

Exact match on the root commit hash is real, shared history — proof, not a
guess. Only then `git remote set-url`, and verify the *actual configured
remote* connects too (`git fetch <remote-name> -v`), not just the one-off
URL used to check identity.

This caught a real bug directly (2026-08-16): an earlier remote-wiring pass,
run against a project containing dozens of nested `.git` directories
(vendored reference clones), set that project's *own* top-level remote to
the identity of one of the *nested* repos instead. The name looked
plausible enough that it went unnoticed until the mismatch was checked by
root commit, not by reading the string.

## Never discard uncommitted changes without a clean baseline first

The other half of the same incident: diagnosing what a command did by
checking `git status` *after* it ran, with no baseline from *before*,
misattributed pre-existing uncommitted work to the just-run command — and
`git checkout -- <files>` then discarded it for real. Never staged, so git
had no copy anywhere; recovery only worked because an IDE's Local History
happened to still have it, which is luck, not a plan.

`git status` on the exact files in question, *before* running anything —
every time, not just when something feels risky. `git checkout --
<files>`/`git restore <files>` are exactly as destructive as `git checkout
.`/`git restore .` when the target already had real, unstaged changes; there
is no version of "just this one file" that makes the loss smaller once it's
gone.
