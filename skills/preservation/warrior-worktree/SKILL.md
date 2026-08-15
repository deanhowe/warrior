---
name: warrior-worktree
description: Lease a bounded slice of a repository to an agent instead of handing over the repository. Use when creating, reviewing, blocking, returning, or retiring an agent worktree; when deciding what files an agent may touch; or when a proposed patch will not apply.
---

# Warrior worktree leases

Never give an agent a repository. Give it a **lease**: a specific baseline, a
specific branch, a specific tree on disk, an enumerated set of files, the
commands that must pass, and its own authority — separate from every other
lease, including other leases held by the same agent.

A lease is a contract you can audit after the fact. "The agent was working in
the repo" is not.

## The lease shape

Record all of it. A field you left blank is a decision someone will have to
guess at later.

```
work_item          the bounded objective this lease serves
repository         the canonical repository that owns the files
baseline_commit    the exact commit the tree forks from
branch             <agent>/<work-item-slug>
worktree_path      an isolated tree, outside the canonical checkout
role               what this lease is for: builder, reviewer, bridge
agent_profile      who holds it
file_scope         exact paths, enumerated — globs only where genuinely needed
validation         the commands that must pass, verbatim
dirty_baseline     digest of pre-existing mess, to be excluded not committed
return_strategy    how the work comes back
retention          preserve by default
commit_authority   none | local
push_authority     none | approved
push_remote        the one named remote, when push is approved
heartbeat          last time the holder was alive
state              proposed | active | blocked | returned | released
```

## Baseline before branch

Resolve and record the baseline commit **before** creating anything. Two
questions decide whether the lease is even possible:

1. **Is the branch already checked out elsewhere?** Git will refuse a second
   worktree on the same branch, and the error arrives after you have already
   made decisions on the assumption it worked.
2. **Does the baseline share history with what you intend to compare against?**
   If not, stop. See *Incompatible baselines* below.

Create no worktree implicitly. A worktree without an approved work item is an
agent inventing scope for itself.

## The dirty baseline digest

This is the field people skip, and it is the one that prevents the worst
outcome.

Before an agent starts, fingerprint what is *already* modified and untracked in
the repository. Those files are **not** the agent's work and must never appear
in its commit. Without this record you cannot tell, afterwards, whether a
changed file was the agent's doing or was already like that — and the safe
resolution then is to commit nothing, which strands real work.

Record it up front, exclude it explicitly in every checkpoint, and say in the
plan which files you excluded and why.

## The validation contract

State the commands verbatim, including the ones that must **not** run:

```
["npm test -- --run",
 "npx tsc -b --noEmit",
 "no publish step",
 "no binding regeneration"]
```

Negative constraints are part of the contract. An agent that satisfies the
tests by regenerating bindings, publishing, or restarting a service has not
satisfied the contract — it has changed the world to make the tests pass.

Validation runs inside the lease's tree, against the lease's file scope. A
green result elsewhere is not evidence.

## Incompatible baselines — the case that must block

A review lease was rooted at a private mainline that turned out to share **no
common ancestor** with the branch under review. `git apply --check` failed;
semantic inspection confirmed the two lines were genuinely different
architectures of the same application, not a merge conflict.

The correct outcome was `blocked`, with the finding recorded and the modern
line preserved under an explicit name.

The wrong outcomes, all tempting:

- forcing the patch through with `--3way` or manual fixups;
- rebasing one orphaned history onto the other;
- assuming the failure is a mistake and retrying;
- deleting either line to remove the ambiguity.

**Two histories with no common ancestor is a decision, not a retry.** Escalate
it. A blocked lease with a clear note is a successful outcome; a forced merge
of unrelated histories destroys the ability to tell what either one was.

## Returning work

`return_strategy` says how the change gets back. Prefer **reviewed-commit**:
the holder commits inside the lease, pushes only its own branch when it has
push authority for that named remote, and a separate reviewer fetches it.

Never merge your own lease into the canonical branch as the same actor that
wrote it. The review is the point.

## Leases expire; they do not self-renew

Heartbeat the lease while the holder is alive. When a lease's heartbeat goes
stale:

- mark it expired and say so;
- **never auto-requeue the work**;
- never reassign the tree to another agent;
- never clean the worktree.

An expired lease may hold the only copy of hours of work. Automatic recovery
that "tidies up" is how that work disappears. A human decides.

## Removal is destructive

Removing a worktree deletes an entire tree that may contain uncommitted work,
and prunes the branch's checkout state. It is a deletion. It requires its own
explicit approval naming the exact path, and it is never implied by the work
being finished, the lease being expired, the branch being merged, or disk space
being short.

Default `retention` is **preserve**. Retiring a lease means marking it
`released`, not erasing its tree.

## Before proposing any lease, state

1. work item and bounded objective;
2. canonical repository, and every nested repository inside the file scope;
3. baseline commit, and whether the branch is checked out elsewhere;
4. worktree path, and that it sits outside the canonical checkout;
5. enumerated file scope;
6. validation contract, including negative constraints;
7. dirty baseline digest, and which files are therefore excluded;
8. return strategy;
9. commit and push authority, and the named remote if any;
10. retention policy, and that removal remains unapproved.

If you cannot fill all ten, you have a question, not a lease.
