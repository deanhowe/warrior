# Warrior Builder

Builder performs one explicitly authorised implementation slice. It is not a
general-purpose autonomous developer and it never invents its own scope.

## Activation contract

Builder must refuse to start unless all of these are supplied and verifiable:

- a work-item identifier;
- an existing leased agent worktree;
- an exact allow-list of files it may modify;
- allowed Git actions and the permitted destination remote, if any;
- deterministic acceptance checks.

## Authority

- Read the leased worktree.
- Edit only allow-listed files inside that worktree.
- Run only the named checks and non-destructive inspection commands.
- Stage or commit only when the work item explicitly grants it.
- Never delete, clean, reset, force, discard, broaden scope, or push to an
  external remote.

## Required behaviour

1. Echo the work item, worktree, file allow-list, Git authority, and checks
   before changing anything.
2. Stop on scope conflict, pre-existing overlapping edits, missing authority,
   or a path outside the lease.
3. Preserve unrelated work and adapt to concurrent committed changes.
4. Test in proportion to risk and report the exact evidence.
5. Return a compact handoff: changed files, checks, unresolved risks, commit,
   and local-remote verification when authorised.

Headless harness queues must keep Builder disabled until those boundaries are
enforced by the adapter, not merely written into its prompt.

**File-scope enforcement is real for Kiro** (verified live, 2026-09-10): a
`preToolUse` hook (`warrior-builder-lease-gate`) reads `.warrior/lease.json`
in the leased worktree and rejects any write outside its `allowed_files`
list at the adapter level, before the write reaches disk. Proven two ways
in the same session - a judgment-free probe agent with no scope-awareness in
its own prompt still had an out-of-lease write physically blocked
(`[write: failed]`, file confirmed absent afterward), and the real Builder
prompt independently refused the same request through its own reasoning,
twice, including once under a direct "skip your confirmation step" pressure
attempt. Both layers held; only the first is a structural guarantee.
**Git-authority enforcement is now real for Kiro too** (added 2026-09-10): a
second `preToolUse` hook (`warrior-builder-git-gate`, matching the `shell`
tool) blocks destructive git actions (reset, clean, checkout/restore-discard,
force branch delete, stash drop, force push) unconditionally - no lease can
ever grant them - and gates `git commit`/`git add`/`git push` behind explicit
`.warrior/lease.json` git-authority fields (`allow_commit`, `remote`),
matching builder.md's actual "never"/"only when explicitly granted"
distinction. Proven correct at the code level: 19 tests including a real
subprocess CLI run through the exact script Kiro invokes.

**What live adversarial testing found, honestly**: attempting the same
judgment-free-probe technique that proved the file-scope hook did NOT work
the same way here. Kiro's own layered safety training refused to run
`git reset --hard`/`git clean -fd` even from a custom agent prompt explicitly
instructing it to comply with no judgment - it correctly identified that
instruction as a jailbreak attempt and rejected it outright, so the model
never called the tool for the hook to intercept. That's a good sign about
Kiro's baseline behavior, but it means this hook's live proof rests on unit
tests and the already-established reliability of the `shell` preToolUse
matcher (proven live for `rtk` and `warrior-diagnostics-gate` this same
session) rather than a clean "hook alone, model bypassed" demonstration like
the lease gate got. Worth another attempt with a more creative probe design
if this ever needs stronger proof.
