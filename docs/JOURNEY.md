# The journey

This is written for one specific reader: someone who knows git — really
knows it, could explain a merge commit at a dinner party — but has never
*trusted* it. Maybe you used a GUI for years because it made state visible in
a way the terminal never did. Maybe you've been burned before, on a real
project, and the fear that followed was a rational response to a tool with
real footguns, not a gap in your understanding.

That's the audience. If that's you, keep reading. Each chapter: what you'll
find, the exact command, how to read what comes back, what's safe, what
isn't, and what to do next.

## The mental model, first

Work you do in a git repository can live in one of four places, and most of
the fear around git comes from not knowing which place a given piece of work
is currently in:

1. **The working tree** — files on disk, as you see them in your editor.
2. **The index** (also called "the stage") — what's queued for the next
   commit. `git add` moves things here.
3. **The object store** — committed history. Once something's here and a
   branch or tag points at it, it's genuinely durable.
4. **Somewhere else entirely** — a shelf, a stash, an index-only blob with no
   working-tree copy, a commit no branch points at anymore. This is the
   category git hides best, and it's where most of what this tool finds
   actually lives.

The commands that move work between these places are the ones people fear:
`reset` (moves things backward, sometimes destructively), `checkout`
(overwrites the working tree from elsewhere), `clean` (deletes untracked
files), `stash drop` / `gc` (lets category 4 expire). Once you know which
category your work is in, you know exactly which commands are safe to run
near it and which aren't. That's the whole trick.

## Chapter 1 — See what git hides from you

```bash
warrior-scan ~/code
```

This reads. It never writes, stages, commits, stashes, or deletes anything —
that's not a promise in a README, it's enforced by a single guarded choke
point that every git call in the tool passes through, checked one token at a
time, adversarially tested against the tool's own guard.

Read the output top to bottom — it's sorted worst-first:

- **CRITICAL** — the only copy of something real, and git will never show it
  to you unprompted. Deal with these first.
- **HIGH** — one copy exists, but it's at least visible if you go looking
  (an unmirrored repo, a stash).
- **MEDIUM** — recoverable today, but sitting on a clock (git's default
  garbage collection eventually prunes unreachable objects).
- **INFO** — not urgent, but you should understand it before you run a broad
  command near it (a symlinked directory that's really the same repo twice,
  a bare repository that isn't a normal working tree).

If it finds nothing: good, genuinely. That's real information, not a failure
of the tool.

## Chapter 2 — Rescue it, without breaking anything

Every CRITICAL and HIGH finding has a safe recovery path. The rule that
matters most: **copy before you touch the original.** Never apply a shelf,
pop a stash, or reset toward a found commit as your first move — copy the
content out somewhere separate first, verify the original is untouched, and
only then decide what to do with the original.

- **A shelf** (JetBrains IDEs) is a `.patch` file. `git apply --check
  <the.patch>` in the right repository tells you if it would apply cleanly,
  without touching anything. Copy the `.patch` file itself out first.
- **A stash** is `git stash show -p stash@{N}` to look, `git show <sha>` if
  you have the commit SHA directly (stashes are commits — the SHA survives
  even if the stash entry itself is later dropped). `git stash apply` (not
  `pop`) keeps the stash entry after applying, in case you need to look again.
- **An index-only blob** — content staged, then deleted from the working
  tree, so it exists only in `.git/index` — is recovered with `git cat-file
  -p <blob-sha>`, found via `git ls-files --stage -- <path>`. This is the
  most fragile category: a `git reset` on that path removes it from the
  index with no reflog entry pointing back to it. Copy it out immediately.
- **An unreachable commit** — no branch or tag points at it — is still fully
  inspectable with `git show <sha>` and fully restorable with `git
  cherry-pick <sha>` or by creating a new branch at it (`git branch
  recovered <sha>`). It only truly disappears once `git gc` prunes it, which
  by default happens to objects unreachable for more than two weeks.

None of these recovery commands mutate the original location. That's
deliberate: recovery should never require you to trust that you got the
first step right.

## Chapter 2½ — Understand a messy history before doctoring it

```bash
warrior-history assess ~/code/my-project
```

This is the history-specific companion to `warrior-scan`. It reads both
reachable history and unreachable commits, and explains:

- database files and database dumps;
- zip/tar archives, Git bundles, installers and compiled binaries;
- media and other blobs above the configurable size threshold;
- paths that still exist now versus paths found only in older commits;
- multiple root commits, which can mean unrelated projects or a deliberately
  preserved pre-rewrite lineage share one object store;
- commits with no branch or tag protecting them.

A match is a **review candidate**, never a deletion recommendation. A tracked
SQLite database may be the product. A large video may be the source asset. A
second root may be an intentional backup branch. The report tells you what is
true; it does not decide what you meant.

For machine-readable output:

```bash
warrior-history assess ~/code/my-project --json
```

The default large-blob threshold is 10 MiB. Override it when a repository has
a deliberately different policy:

```bash
warrior-history assess ~/code/my-project --large-mb 50
```

Sensitive-looking paths and commit subjects are counted but withheld from both
text and JSON reports. File contents are never read. This command does not scan
file content for leaked secrets, move source refs, run garbage collection, or
alter a remote.

### Build an exact-path removal candidate

Assessment and rewriting remain separate commands. First write a pinned plan:

```bash
warrior-history plan ~/code/my-project \
  --remove-path old-export.zip \
  --output ~/Desktop/my-project-rewrite-plan.json
```

The source must be clean, the named path must exist in reachable history, and
the output file must not already exist. Review the JSON, then build a new bare
candidate at a path that does not exist:

```bash
warrior-history build-candidate \
  --plan ~/Desktop/my-project-rewrite-plan.json \
  --destination ~/Desktop/my-project-rewritten.git
```

Warrior clones with `--mirror --no-local`, runs `git-filter-repo` only inside
that new candidate, removes its remote, runs `git fsck`, proves the requested
paths are absent from every reachable candidate ref, and rechecks that the
source HEAD and refs did not move. A partial or failed candidate is preserved
for inspection; Warrior never deletes it and never retries over it.

This rewrite surface removes exact files or whole directory trees. The
candidate is evidence to inspect, not permission to replace a repository.

### Build a public projection without rewriting your private source

Audit exactly the branch you intend to publish:

```bash
warrior-history public-audit ~/code/my-project \
  --ref main \
  --allow-email owner@users.noreply.github.com \
  --json
```

Exit code `3` blocks publication. The JSON reports categories and locations
but never the matched values. For anything real, write `git-filter-repo`
replacement expressions in a private file outside the source repository, then
pin the release inputs:

```bash
warrior-history public-plan ~/code/my-project \
  --ref main \
  --public-email owner@users.noreply.github.com \
  --remove-path private-directory \
  --replace-text ~/private/replacements.txt \
  --output ~/private/public-plan.json

warrior-history build-public-candidate \
  --plan ~/private/public-plan.json \
  --destination ~/private/my-project-public.git
```

The public candidate contains only `main`; other branches, tags, backup refs,
and unrelated roots are not copied. Every historical author/committer email is
rewritten to the declared public identity. Warrior disconnects the candidate,
applies removals/replacements there, verifies objects, audits it again, and
proves the source did not move. It does not add a public remote or push. Review
the candidate and use a normal non-force push only under explicit authority.

## Chapter 2¾ — Know what came from upstream

Before leaving history work, one adjacent problem deserves its own boundary:
vendored source. A copied directory is easy to mistake for either wholly
upstream or wholly yours after a few months of edits.

```bash
warrior-upstream audit \
  --manifest upstreams/mattpocock-skills.json \
  --source /path/to/source-checkout
```

The manifest pins the source commit and declares selected trees, renames,
intentional divergences, and local-only files. The audit hashes both sides and
fails on a dirty source checkout, the wrong source commit, a missing file, an
undeclared edit, an undeclared extra, or a declaration that has gone stale. It
reads file bytes only to hash them and never prints their contents.

This is deliberately not an updater. It does not contact a remote, fetch,
merge, overwrite the vendored copy, or decide that a newer upstream version is
better. Updating a transformed import requires human review of both the new
source and the declared local intent; turning that into one automatic command
would erase the boundary this tool exists to make visible.

When that review chooses individual portable fixes instead of a bulk source
refresh, record the reviewed source commits and exact backports in the manifest.
The auditor reports both, while continuing to verify the reproducible pinned
base and every resulting local divergence.

## Before importing a project or package estate

Do not create repositories from directory names or publish whatever happens to
be in a dirty working tree. Build the evidence dossier first:

```bash
warrior-project dossier ~/code/packages
warrior-project dossier ~/code/packages --json
```

`warrior-project` discovers independent Git boundaries while pruning dependency
and build trees. It records root commits, current refs, dirty state and redacted
remotes. Composer release evidence comes from committed `HEAD`, never an
uncommitted working manifest; any difference is reported separately. It accepts
only versions declared in the committed manifest or proven by semantic-version
tags whose own manifest has the same
package identity. Tags from a pre-fork or pre-rename identity are reported as
lineage evidence, never borrowed as releases of the current package. Placeholder
names, applications/metapackages, repositories with no commit, packages with no
evidence-backed version, and duplicate package identities remain explicit
blockers. The command is read-only: it does not create a repository, add a
remote, publish a package, or decide who owns a fork.

### Turn the dossier into a checkpoint closure plan

Run `warrior-scan` on the same roots first, then:

```bash
warrior-project checkpoint-plan ~/code/packages
warrior-project checkpoint-plan ~/code/packages --json \
  --output ~/Desktop/packages-checkpoint-plan.json
```

The plan pins each repository's current `HEAD`, root commits, and a SHA-256
digest of its exact porcelain status. It reports checkpoint state separately
from package state, so an unversioned package is not confused with an
unprotected working tree. Every repository receives one closure verdict:
`ready`, `checkpoint-needed`, or `human-review-required`.

Ordinary changed paths are listed with their two-character Git status.
Credential-shaped and private-state filenames are counted but withheld; their
presence blocks automation instead of leaking their names into a report.
Duplicate Composer identities and committed-manifest blockers are attached to
each affected repository, not left only as an estate-wide footnote.

This command creates evidence, not a checkpoint. `required_artifacts` says
which independent representations would be needed—staged-index patch,
tracked-worktree patch, and/or untracked-content manifest—but no apply command
exists yet. The report writer uses Warrior's guarded output path and refuses to
overwrite an existing file unless `--overwrite` is explicit.

## Chapter 3 — Know your estate

```bash
warrior-facts where <name>
warrior-facts repos --root ~/code
warrior-facts unprotected --root ~/code
```

This answers the questions you'd otherwise answer by remembering, or by
`find`-ing around and hoping: where is this project, what repositories exist
under this root, which of them have no remote at all. It's read-only, bounded
in depth, and never follows a symlink outside the root you gave it.

## Chapter 4 — Give every repo a home

```bash
warrior-protect ~/code/some-old-project
warrior-protect ~/code/some-old-project --apply
```

Dry run first, always — that's the default, not a flag you have to remember.
It tells you what it would do before it does anything. `--apply` creates a
repository on your configured git server if one doesn't exist, adds a remote,
pushes, and then — this is the part that matters — **verifies by checking
that your local `HEAD` actually appears in the server's own refs.** Not by
trusting that the push command exited with code `0`. That distinction is not
paranoia: a filesystem-path push into an already-up-to-date repository exits
`0` having sent nothing at all, and looks identical to success unless you
check.

## Chapter 5 — Name what things are for

```bash
warrior-classify
warrior-classify --apply-topics
```

Not every repository on your server is the same *kind* of thing. Some are
your own work. Some are mirrors of someone else's code you depend on. Some
are archives you're keeping but not developing. Treating all of them the
same way — "push everything" — is how a server-side mirror flag
(`is_mirror`, meaning "this syncs from somewhere else") gets confused with
*ownership*, which is a real mistake this tool's own author made once: it
mislabelled repositories that were mirrors of the author's own GitHub account
as if they were someone else's code, because the mirror flag describes the
sync mechanism, not who wrote the thing. Caught by spot-checking a result
before trusting it at scale — which is the actual lesson, more than the bug
itself.

## An honest example: routing work to a cheap model

Part of this project's roadmap is routing well-specified mechanical work to
cheaper models instead of doing everything with an expensive one. Here's
what actually happened the first time that was tried for real, kept in here
because a guide that only shows the version where everything works isn't
useful.

Three writing tasks — a license file, a safety document, a roadmap document —
were sent to a cheap model through an existing task queue. Two came back with
genuinely usable prose. The third came back having failed every tool call it
attempted, because the queue profile that ran it was deliberately configured
read-only — no write access, by design, matching the rest of the system's
default-deny posture. That wasn't a bug to route around; it was the correct
policy operating correctly, and the fix was to treat the model's *text
response* as a draft to review and place by hand, not as a finished file.

One of the two "successful" results still needed real editing: it drifted
into reassurance language ("users can have confidence in the security...")
in a document that had explicitly been asked to state facts, not reassure —
and it slightly misdescribed one of its own safety guards. Caught by reading
it before shipping it, not by trusting that "the task completed" meant "the
content is right."

The honest summary: cheap-model routing for mechanical work is real and
worth doing. It is not yet unsupervised. Every result needs a human — or
another model acting as a checker — verifying both that something actually
landed, and that what landed is true.

## What comes next

Chapters past this point don't exist yet. `docs/ROADMAP.md` says so
explicitly, and repeats it, because the easiest way to erode trust in a tool
like this is to describe tomorrow's plan as though it shipped today.
