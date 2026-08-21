## What this is

How to extend a self-hosted Gitea (or Gitea fork) with a new **native repository unit** — a first-class product surface like Wiki, alongside Code/Issues/PRs/Releases, not a plugin and not a separate app bolted on the side. Wiki is the shape to copy: every repo can have one, it has its own storage, its own access rules, its own UI. Nothing stops you adding others — Docs, Notes, Goals, Specs, whatever your own workflow needs — as real, equal citizens of the fork, not a workaround living outside it.

This doc is written to stand on its own. It doesn't assume you're looking at any particular fork's source — it assumes you have *a* Gitea fork, and teaches the method for finding the real, current call-site list in *your* fork, because Gitea's own source changes over time and a hardcoded file list from someone else's fork will eventually be wrong for yours. Where a concrete example helps, it draws on a real one (a fork that added five native unit types this way, one of which shipped with a real, confirmed bug), but the actionable part is the method, not the specific paths.

## Why extend the fork instead of building something else

Three real alternatives exist for "I want a new kind of first-class content attached to my repos," and native units beat all of them for anyone running their own Gitea:

- **A separate app/service reading the Gitea API.** Works, but now you have two systems, two auth models, and your new content isn't a native repo unit — no unified access control, no Actions token scoping, no place in the repo's own UI.
- **A plugin/webhook system, if your fork has one.** Lighter weight, but still bolted on — it can't share Gitea's permission model or its git storage conventions without real integration work anyway.
- **A plain directory convention (a special folder name inside the repo).** Zero extension work, but you lose independent access control, independent history, and independent discoverability — everything a native unit gets for free.

If you own the fork (you're not waiting on an upstream PR to merge), extending it directly is usually the right call: the new unit gets real git-backed storage, its own SSH/HTTP access rules, its own permission scope, and shows up in the UI the same way Wiki does — because it *is* Wiki's mechanism, reused.

## The contract — every place a native unit type touches

This is the real list, produced by diffing every reference to Gitea's most complete existing unit type (usually Wiki) against every reference to a newly-added one, across the whole source tree — not by reading one commit and assuming it's complete. That distinction matters: a naive copy of Wiki, done by a careful human reading the code, missed five of these rows in practice. Trust the method (a full reference diff), not any specific list handed to you, including this one.

| Layer | What to look for | Why it's easy to miss |
|---|---|---|
| Model | The type constant, the unit's own struct literal, its entry in the "all unit types" list and any per-context default-units lists (regular repo, mirror, template) | Forgetting the mirror/template defaults is invisible until someone actually creates a repo that way |
| API routes | The route group + a "must be enabled" guard function | — |
| API edit | The "enable/disable this unit" handling in the repo-settings update endpoint | — |
| **SSH access** | Suffix detection (`<repo>.<type>` → route to this unit) in whatever handles `SSH_ORIGINAL_COMMAND` | **The exact bug found in the worked example below — silently broken, no error, for months** |
| **HTTP git access** | The same suffix detection, for the HTTP smart-git protocol handler | Same shape as SSH, separate file, separate bug surface |
| Web controller | A full parallel controller (list/view/edit/history) | Usually the most "obviously new" file, least likely to be forgotten |
| Web settings | The enable/disable toggle in the repo settings UI | — |
| **Public/anonymous access settings** | Wherever your fork lets an owner make a unit publicly readable/writable | Easy to scroll past — no obvious "next entry" to add |
| Route guards | Reader/writer permission-check middleware for the new unit's routes | — |
| Template/rendering context | Wherever unit types are exposed to server-rendered templates | — |
| API conversion | Wherever a repo's enabled units get serialized to JSON for the API | — |
| Service layer | Delete-repo and default-branch-change logic for the new unit's storage | — |
| **Actions/CI token scope** | Wherever your fork parses which units a CI token is allowed to touch | **Invisible until someone's Action tries to touch the unit and gets refused** |
| **Migrate/import API** | The "enable this unit on import" option — struct field, both migrate handlers, all import UI templates | **Invisible until someone imports a repo and finds the unit wasn't enabled — no error, just silently off** |
| Storage | A real migration if you're tracking unit-enablement in a DB column | — |
| **Mirror-pull behavior** | A test (or manual check) that the unit actually auto-enables on mirror sync if your defaults claim it should | **Config claiming a default and runtime behavior actually doing it are two different things — verify, don't assume** |
| **Test coverage** | The unit's own test files, not just "it happens to get exercised while testing Wiki" | A feature with zero tests of its own isn't finished, it's unverified |

The five bold rows are the ones a careful, by-hand copy of Wiki missed in the real worked example below — verified by actually shipping and finding each gap live, not by inspection. Assume your fork has at least that many blind spots your inspection won't catch; verify live wherever the row is genuinely load-bearing (permission scoping, migrate/import, mirror defaults), not just by reading the source and reasoning it should work.

## The verification method

1. Pick the most complete existing sibling unit (Wiki is usually it).
2. Get every reference to that sibling's type constant across the whole source tree — an LSP "find references" call, not a memory of where you think it's used. `grep`/`ripgrep` finds textual matches; an LSP reference search finds actual symbol usages, including ones grep's pattern won't catch (renamed locals, interface satisfaction, generated code).
3. Get the same for your new unit's type constant.
4. Diff the two location lists, file by file. Every place the sibling appears that the new unit doesn't is either a deliberate, considered difference or a real gap. Check each one — don't assume either way, and don't skip re-running this diff for your *next* new unit type just because you did it once; the fork's own source may have grown new call sites for the sibling since you last checked.
5. For anything genuinely load-bearing (permission scoping, migrate/import, mirror defaults), verify against real, live behavior — create a real repo, exercise the real path, check the real result. A gap in the migrate-import path was only provably real, in the worked example, once checked against repos actually imported that day, not by reading the migrate code and reasoning it should work.
6. Build the new unit's own isolated test suite before calling it done.

## Building a generator — do this once the pattern is proven by hand, not before

Once you've added a second unit type by hand using the contract above, most of the work is a mechanical parallel of the first — same shape, different name, across a dozen-plus files. That repetition is exactly why the bold gaps above happen: a human copies by hand and misses spots with no obvious visual "next case to add" (a permission `switch` statement has no natural cue that a case is missing; a migrate-options struct gap requires knowing the field should exist at all).

A generator — driven by a small spec per unit type (name, whether it's git-backed, default permission) — can emit or patch every row in the contract table at once, making the gaps structurally impossible to forget instead of relying on a human remembering a checklist.

**The one hard-won lesson, worth taking seriously before you write a line of merge logic**: most of the contract rows above live in files that already contain accumulated logic for *every* unit type mixed together — you can't cleanly diff-replay a single-type patch onto them the way you can for a brand-new standalone file. You'll end up hand-patching these with string-anchored text insertion, and **that is exactly where a real generator shipped a real, silent, production bug**:

> One merge function anchored its insertion on the literal, pristine text of an existing sibling branch, then replaced that text with itself-minus-its-own-closing-brace plus the new branch. That works exactly once. On the *next* type added, the anchor text no longer exists verbatim anywhere in the file — the previous insertion altered its ending — so the string-replace call silently no-ops. No exception, no warning, exit code 0, file written to disk looking plausible. Two of four newly-added unit types shipped with SSH `git clone` access silently, invisibly broken as a direct result — not caught until someone actually tried to clone one of them, months later.

Two concrete defenses, both worth building into a generator from the start rather than after it bites you:

1. **Anchor insertions on something structurally invariant, not a snapshot of one past state.** If you're inserting the Nth branch into a growing `if/else if` chain, don't anchor on the *previous* branch's exact text (it changes shape every time something gets inserted near it) — anchor on whatever unconditionally follows the *entire* chain, a marker that no insertion in this chain ever touches. That makes the insertion point self-relative to the chain's real current end, correct for the 2nd, 3rd, or Nth type, not just the 1st.
2. **Verify the merge's own output, every time, mechanically.** After a hand-patch merge runs, check that the specific markers it claims to have added — the exact identifiers, the exact condition fragments — are actually present in the resulting text, and fail loudly, with a specific diagnostic, if they aren't. A merge that completes without raising an exception is not evidence it worked. This one check is what turns "silent gap, discovered live, possibly months later" into "immediate, specific, build-time failure" — for every future unit type, not just the one that already broke.

Build both from day one of the generator, not after the first silent gap ships. The cost of the check is trivial; the cost of a native unit type silently missing SSH access in production is not.

## A note on "fast, accurate, native"

Whatever tooling you build around this — the generator itself, the reference-diff step, the verification pass — keep it dependency-light and fast to run locally. This is infrastructure you'll re-run every time you add a unit type, not a one-shot script: a generator that takes minutes or needs a heavyweight toolchain will get skipped "just this once," and "just this once" is how the silent gap above happened in the first place.
