# Warrior

`git status` does not show you most of the ways you can lose work.

A scan of 415 real repositories on one developer's machine — a decade of
accumulated projects, no different from what's probably sitting on yours —
found:

- a JetBrains shelf **403 days old**, another **706 days old**, both invisible
  to `git status`, invisible to `git stash list`, hidden by `.gitignore`
- **58 stash entries across 27 repositories**, most of them automatic
  safety-net stashes from **2014–2019** — the oldest is **eleven years old**
- **4 files that existed only in `.git/index`** — one `git reset` away from
  gone, with no reflog entry to recover them
- **37 commits with no branch or tag pointing at them**, sitting on git's
  default two-week garbage-collection clock
- **50 repositories with no remote at all** — no mirror, no backup, nothing
  but the one copy on disk

None of that is carelessness. It's what happens when a tool hides state and
only ever shows you one slice of it at a time. If you've ever felt afraid of
git — not because you don't understand it, but because you've been burned by
it — that fear is a rational response to a real problem, not a gap in your
knowledge.

Warrior is the tool that finds what git isn't showing you, and gets it
somewhere safe, before you touch anything else.

## Quick start

```bash
git clone <this-repo>
cd warrior
python3 bin/warrior-scan ~/code
```

That's it. Read-only, no configuration required, no network access. It
prints what it found, ranked by how bad it would be to lose:

```
CRITICAL — only copy of real work, and Git will not show it to you
HIGH      — single copy: no mirror, ahead of every mirror, or shelved off to the side
MEDIUM    — recoverable today, but on an expiry clock
INFO      — structural: understand it before you move or clean anything
```

Nothing is fixed automatically. `warrior-scan` only ever reads. What you do
with what it finds is next.

## What's here today

Five tools, all read-only or additive, all with real tests, all adversarially
audited before being trusted:

| Tool | What it does |
|---|---|
| `warrior-scan` | Finds the eleven ways work can be invisible to git — shelves, stashes, index-only content, unreachable commits, unmirrored repos, and more |
| `warrior-facts` | Answers questions about your machine: where is this repo, what exists under this root, what's unprotected |
| `warrior-protect` | Gives an unprotected repository a real, *verified* home on a git server — verified by checking the server's own refs, never by trusting an exit code |
| `warrior-classify` | Works out what each repository on your server is *for* — your own code, a mirror of someone else's, an archive — and records it |
| `warrior-credits` | Live credit/quota balance across every AI harness you run, at zero token cost, without spending a prompt to ask |

Every one of them was extracted from a working production system where it
was built under real pressure, then adversarially audited by agents whose
only job was to try to break it. That audit found **four real bugs** in the
scanner alone — including one where a mistyped `--output` flag overwrote a
repository's `.git/HEAD` and broke it. All four are fixed. `docs/SAFETY.md`
explains exactly what protects you now and why each protection exists.

## What's not here yet

Chapter 1 — "know your machine, never lose work" — is what ships today.
Everything past that is a roadmap, not a feature: your own private git
server, durable memory of decisions, routing work to cheap models
automatically, bridging multiple AI coding agents together. See
`docs/ROADMAP.md` for the honest version, including what's proven and what
isn't.

`docs/JOURNEY.md` is the guided path through Chapter 1 — what to run, in what
order, and how to read what comes back, written for someone who knows git but
has never trusted it.

## Who this is for

You, if any of this sounds familiar: you've used a GUI for git for years, not
because you don't understand the command line, but because it made state
*visible* in a way the CLI never did. You have projects going back a decade.
You're not sure what's actually backed up. You've been burned before. That's
not a knowledge gap — it's a rational response to a tool that hides things.
This is built for you.
