---
name: warrior-fork-parity
description: How to actually verify a feature you added to a fork of critical infrastructure is complete, and how to safely rename an identifier across a codebase without breaking things that coincidentally share its string. Use whenever "we extended X to also do Y, modeled on how it already does Z" is the claim, before trusting it, and before any bulk find-and-replace of an identifier.
---

# Warrior fork parity

Owning the fork means nobody upstream will catch your extension's gaps for
you. That's the whole point of forking — you're not waiting on a maintainer
to accept a PR, you decide what "done" means. But it cuts both ways: nothing
stops you from shipping something that *looks* finished and isn't, because
the only thing that would have caught it — someone else's review, someone
else's test suite, someone else's users filing issues — doesn't exist
anymore. You are the only check. This is what to actually do about that.

## Part 1 — the reference-diff completeness check

The claim to distrust: "I extended X to also support Y, modeled on how X
already does Z" — followed by a commit that builds, a manual click-through
that works, and a description of the change that lists which files got
touched. None of that proves completeness. A file list describes what
*was* touched, not what *should have been*.

**What actually proves it:** find every place the existing, mature feature
(Z) is referenced across the whole codebase — not by memory, not by
skimming the file that defines it, but with a real reference-finding tool
(an LSP `references` call, or if none is available, a disciplined grep for
the exported symbol name). Find every place the new feature (Y) is
referenced the same way. Diff the two location lists, file by file. Every
place Z appears that Y doesn't is either a deliberate difference or a real
gap — check each one, don't assume.

This is not a hypothetical. Doing exactly this against a real fork (a
custom Gitea build, extended to add a second wiki-like content unit
modeled directly on the existing Wiki unit) found five real gaps that
"it builds, the page renders in the browser, SSH clone works" had missed
for a full day:

- a permission-scoping code path (CI token permissions) that had a case
  for the old feature and no case for the new one — silently unsupported,
  not erroring loudly enough to notice;
- a settings-page list that enumerated the old feature and simply didn't
  mention the new one — an omission a screenshot of the page working
  wouldn't reveal, because the page still rendered fine, just incomplete;
- an import/migration API whose typed options struct had a field for the
  old feature and no field for the new one — confirmed live, by checking
  real production data: every repository imported through that path had
  neither the old nor the new feature enabled, because the specific field
  needed to request either had never been passed;
- an integration test that asserted the old feature auto-enables under a
  specific condition, with no equivalent assertion for the new one — so
  the claim that the new feature had the same behavior was completely
  untested, not verified;
- **zero dedicated test files for the new feature anywhere in the
  codebase**, versus six for the old one spanning every architectural
  layer. The new feature's only test coverage, a full day after it
  shipped, was one incidental assertion inside a test that was really
  about something else.

None of these were found by reading the commit. All five were found by
enumerating references and diffing. The lesson generalizes past this one
fork: **"modeled on Z" is a design intention, not a completeness proof.**
Prove it with the tool, every time you make that claim, before writing it
down as done anywhere a future session (human or agent) might read it and
trust it.

## Part 2 — renaming an identifier is not one operation, it's three

The trap: an identifier (a username, an owner name, an account label) gets
renamed in the one system that's obviously in charge of it — and the
rename gets *reported* as complete, because the one obvious system now
shows the new name. It isn't complete. The old string is still sitting in
every local config, every hardcoded default, every doc example that
referenced it, and — this is the dangerous part — in other things that
happen to contain the same substring for a completely unrelated reason.

Before running any bulk find-and-replace of an identifier, sort every hit
into exactly one of three bins:

1. **Means the renamed thing.** A repo owner path, an API URL, a hardcoded
   default that's genuinely referring to the entity that got renamed. This
   is the only bin that should actually change.
2. **Coincidentally the same string, means something else.** A local
   secret-storage label, a directory name, a test fixture — anything that
   happens to contain the identical string but isn't a reference to the
   renamed entity at all. Changing these doesn't fix a stale reference, it
   *creates* a new bug, often a silent one (a credential lookup that now
   fails because the label it searches for no longer matches what's
   actually stored).
3. **A stale reference that should be updated but isn't urgent.** Historical
   records, dated logs, anything that's an accurate account of what was
   true *at the time* — rewriting these is revisionist, not a fix.

The real-world proof this matters: renaming a forge's primary account
looked complete after fixing the server-side record, then turned out to
still be live in **234 separate local git configs** across the filesystem
(a bulk "add a remote everywhere" pass had run once, long before the
rename, and every one of those remotes still pointed at the old name) —
far more than an earlier, already-"fixed" record claimed. Separately, two
scripts' keychain-lookup defaults matched the old name too, and got
changed in the first sweep along with everything else — which would have
broken every future credential lookup, because the keychain item's own
label was never tied to the renamed entity in the first place; it just
happened to be the same string. That one was caught by checking the real
keychain entry before trusting the edit, not after.

**Do the classification before the sed, not after.** A single grep that
returns 250 hits is not 250 things to fix identically — it's 250 things to
individually place into one of the three bins above, and the bulk edit
only ever touches bin 1.

## Part 3 — the actual git commands, not just the methodology

Everything above is the reasoning. Here are the real commands, tested
tonight against a live forge with hundreds of real repositories, each
tied to the specific thing it caught.

**Find every local repo with a remote pointing at a specific host/owner
path**, before touching any of them:

```bash
find ~/PROJECTS ~/.kiro -type f -path "*/.git/config" \
  | xargs grep -lE 'git\.example\.com[:/]+.*[:/]old-owner/'
```

Confirm there's exactly one URL shape before bulk-editing — don't assume:

```bash
grep -hoE 'git\.example\.com[:/]+[0-9]*/?old-owner/' $(cat matched-files.txt) | sort -u
```

Then, and only then, rewrite — a plain `sed` across every matched file is
safe *because* you've already confirmed the shape and classified what
"old-owner/" actually means everywhere it appears (Part 2):

```bash
sed -i '' 's#git\.example\.com:2222/old-owner/#git.example.com:2222/new-owner/#g' "$file"
```

**Fix a stale `origin` on a bare repo directly on the server** — no
working tree needed, `--git-dir` points straight at the bare repo:

```bash
git --git-dir=/srv/git/repositories/org/repo.git remote set-url origin \
  /srv/git/repositories/other-org/upstream.git
git --git-dir=/srv/git/repositories/org/repo.git remote -v   # verify
```

**Compare HEADs across a mirror → primary → personal-fork chain without
checking anything out** — the real way to verify "these are actually the
same content," not just "the API said 201":

```bash
git --git-dir=/srv/git/repositories/mirror-org/upstream.mirror.git rev-parse HEAD
git --git-dir=/srv/git/repositories/org/upstream.git rev-parse HEAD
git --git-dir=/srv/git/repositories/personal/upstream.git rev-parse HEAD
```

**Test whether an old path still resolves after a server-side rename**,
before assuming every local reference to it is now broken:

```bash
git ls-remote ssh://git@host:2222/old-owner/repo.git   # still works? Gitea (and similar forges) keep a redirect table
git ls-remote ssh://git@host:2222/new-owner/repo.git   # confirm the new path works too
```

**Don't trust an "N unpushed commits" claim until you diff against the
branch that's actually checked out** — the real bug hit tonight:

```bash
git branch -a                                    # what's checked out, and what does it track?
git log origin/master..HEAD --oneline             # WRONG if the real branch is "main" or something else
git log "origin/$(git branch --show-current)..HEAD" --oneline   # right — your actual branch, not a guess
git push origin "$(git branch --show-current)" --dry-run        # cheapest and most authoritative — no diffing needed at all
```

That last command is the one to reach for first, always — it asks the
remote directly rather than reasoning about local refs, so there's no
branch-name assumption to get wrong.

**Inspect a file's exact content on a remote branch without checking
anything out** — used to verify a `git-crypt`-encrypted file was genuinely
ciphertext on the *server* side, not just locally where the key is
unlocked:

```bash
git show origin/main:path/to/file.md | head -c 200 | xxd | head -5
```

If the key is unlocked locally you'll see plaintext from your own working
tree; this command reads the actual stored blob, which is the only way to
confirm what's really sitting on the remote.

## Why this belongs in Warrior specifically

All three parts above share one throughline: owning your own fork removes the
safety net of someone else checking your work, and replaces it with
nothing, unless you build the check yourself. "It builds," "it renders,"
"the API returns 201," and "the rename script exited zero" are all real
signals — and all of them are compatible with a genuine, non-obvious gap
sitting right next to the thing that worked. Verify completeness with the
same rigor you'd want from a maintainer who no longer exists, because for
a fork you control end to end, that maintainer is you.
