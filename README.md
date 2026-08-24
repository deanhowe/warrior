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
only ever shows you one slice of it at a time.

**Warrior is two things married into one plugin**: preservation-first git
tooling that finds what's at risk before you touch anything, and a set of
real-engineering practice skills — TDD, code review, spec/ticket flows,
domain modelling — sourced from
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT, see
`NOTICES/`). Neither half is complete without the other: practising good
engineering on a machine that's quietly losing work isn't safety, and never
losing anything is worthless if what you keep was never any good.

## Quick start

Read-only, no configuration required, no network access:

```bash
git clone <this-repo>
cd warrior
python3 bin/warrior-scan ~/code
```

It prints what it found, ranked by how bad it would be to lose:

```
CRITICAL — only copy of real work, and Git will not show it to you
HIGH      — single copy: no mirror, ahead of every mirror, or shelved off to the side
MEDIUM    — recoverable today, but on an expiry clock
INFO      — structural: understand it before you move or clean anything
```

## Install as a Claude Code plugin

```
/plugin marketplace add <this-repo>
/plugin install warrior
```

`.claude-plugin/marketplace.json` makes this repo its own single-plugin
marketplace, the same pattern upstream uses. Run
`claude plugin validate . --strict` after touching either manifest file.

## What's here

### Preservation — the layer everything else sits on

Ten tools in `bin/`, all read-only or additive:

| Tool | What it does |
|---|---|
| `warrior-scan` | Finds the eleven ways work can be invisible to git — shelves, stashes, index-only content, unreachable commits, unmirrored repos, and more |
| `warrior-facts` | Answers questions about your machine: where is this repo, what exists under this root, what's unprotected |
| `warrior-protect` | Gives an unprotected repository a real, *verified* home on a git server — verified by checking the server's own refs, never by trusting an exit code |
| `warrior-classify` | Works out what each repository on your server is *for* — your own code, a mirror of someone else's, an archive — and records it |
| `warrior-credits` | Live credit/quota balance across every AI harness you run, at zero token cost, without spending a prompt to ask |
| `warrior-server-status` | Is your git forge actually healthy right now — reachability, disk headroom, mirror staleness, backup freshness — not just whether it answers HTTP 200 |
| `warrior-sidecar` | Give a project a named, versioned space beside it that its own history never sees — goals, tmp, wiki — instead of a gitignored directory with zero protection |
| `warrior-knowledge` | Read-only health check for a Git-backed knowledge source: identity, dirt, remote symbolic HEAD, and exact local/remote commit equality; no harness or forge assumptions |
| `warrior-history` | Read-only history doctor: explains large blobs, databases, archives, compiled artifacts, multiple root lineages, and unreachable commits before any rewrite is considered |
| `warrior-upstream` | Proves a vendored source relationship from a manifest: exact commit, byte-identical files, renames, declared adaptations, omissions, and undeclared drift—without fetching or updating anything |

### macOS 26 native ML tools (companion repo)

28 Swift CLI tools wrapping Apple's on-device ML frameworks — zero cost, no
API keys, no network, no tokens. OCR, transcription, vision, embeddings,
sentiment, summarisation, classification, and more.

```bash
git clone git@github.com:deanhowe/ml-tools.git
export PATH="$PWD/ml-tools:$PATH"
ml-ocr document.png        # instant, local, free
ml-transcribe recording.m4a
ml-vision classify photo.jpg
```

Requires macOS 26 (Tahoe) and Swift 6.2+. See the ml-tools README for the
full list. These are not bundled inside Warrior to avoid duplication — they're
a standalone repo, usable independently.

`warrior-scan` has had the full adversarial treatment — three independent
agents trying to break it, live, against real repositories — and found four
real bugs, now fixed. `docs/SAFETY.md` states exactly what's proven per tool,
not a blanket claim. See `docs/JOURNEY.md` for the full guided path.

Five skills in `skills/preservation/` bring this discipline into an agent
session directly — see `skills/preservation/README.md`.

### Engineering and productivity — real practice, not vibes

These split on one axis — who can invoke them. **User-invoked** skills are
reachable only when you type them (e.g. `/grill-me`); their job is to
orchestrate. **Model-invoked** skills can be invoked by you *or* reached for
automatically by the agent when the task fits; they hold the reusable
discipline.

#### Engineering

Daily code work.

**User-invoked**

- **[ask-warrior](./skills/engineering/ask-warrior/SKILL.md)** — Ask which skill or flow fits your situation. A router over the user-invoked skills in this repo.
- **[grill-with-docs](./skills/engineering/grill-with-docs/SKILL.md)** — Grilling session that also builds your project's domain model, sharpening terminology and updating `CONTEXT.md` and ADRs inline.
- **[triage](./skills/engineering/triage/SKILL.md)** — Move issues through a state machine of triage roles.
- **[improve-codebase-architecture](./skills/engineering/improve-codebase-architecture/SKILL.md)** — Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whichever one you pick.
- **[setup-engineering-skills](./skills/engineering/setup-engineering-skills/SKILL.md)** — Configure this repo for the engineering skills (issue tracker, triage labels, domain doc layout). Run once per repo before using the other engineering skills.
- **[to-spec](./skills/engineering/to-spec/SKILL.md)** — Turn the current conversation into a spec and publish it to the issue tracker.
- **[to-tickets](./skills/engineering/to-tickets/SKILL.md)** — Break any plan, spec, or conversation into a set of tracer-bullet tickets, each declaring its blocking edges.
- **[implement](./skills/engineering/implement/SKILL.md)** — Build the work described by a spec or set of tickets, driving `/tdd` at pre-agreed seams and closing out with `/code-review` before committing.
- **[wayfinder](./skills/engineering/wayfinder/SKILL.md)** — Plan a huge chunk of work, more than one agent session can hold, as a shared map of decision tickets resolved one at a time.

**Model-invoked**

- **[prototype](./skills/engineering/prototype/SKILL.md)** — Build a throwaway prototype to answer a design question.
- **[diagnosing-bugs](./skills/engineering/diagnosing-bugs/SKILL.md)** — Disciplined diagnosis loop for hard bugs and performance regressions.
- **[research](./skills/engineering/research/SKILL.md)** — Investigate a question against high-trust primary sources and capture the findings as a cited Markdown file.
- **[tdd](./skills/engineering/tdd/SKILL.md)** — Test-driven development with a red-green-refactor loop, one vertical slice at a time.
- **[domain-modeling](./skills/engineering/domain-modeling/SKILL.md)** — Actively build and sharpen a project's domain model.
- **[codebase-design](./skills/engineering/codebase-design/SKILL.md)** — Shared discipline and vocabulary for designing deep modules.
- **[code-review](./skills/engineering/code-review/SKILL.md)** — Two-axis review of the diff since a fixed point: Standards and Spec, run as parallel sub-agents.
- **[resolving-merge-conflicts](./skills/engineering/resolving-merge-conflicts/SKILL.md)** — Work through an in-progress merge or rebase conflict hunk by hunk, never `--abort`.
- **[wizard](./skills/engineering/wizard/SKILL.md)** — Generate an interactive bash wizard for steps only a human can perform.

#### Productivity

General workflow tools, not code-specific.

**User-invoked**

- **[grill-me](./skills/productivity/grill-me/SKILL.md)** — Get relentlessly interviewed about a plan or design until every branch is resolved.
- **[handoff](./skills/productivity/handoff/SKILL.md)** — Compact the current conversation into a handoff document.
- **[teach](./skills/productivity/teach/SKILL.md)** — Teach the user a new skill or concept over multiple sessions.
- **[to-questionnaire](./skills/productivity/to-questionnaire/SKILL.md)** — Turn a decision you can't answer alone into a Markdown questionnaire for the person who can.
- **[wait-what](./skills/productivity/wait-what/SKILL.md)** — Fire this the moment a message doesn't land; the agent re-pitches it in plain English.

**Model-invoked**

- **[grilling](./skills/productivity/grilling/SKILL.md)** — The reusable interview primitive behind `grill-me`, `grill-with-docs`, `triage`, `wayfinder` and `improve-codebase-architecture`.
- **[writing-for-agents](./skills/productivity/writing-for-agents/SKILL.md)** — Write documentation and instructions an agent will actually follow correctly.

### Not part of the plugin, but worth knowing about

`skills/misc/git-guardrails-claude-code` — a Claude Code hook that blocks
dangerous git commands (`push`, `reset --hard`, `clean`, `branch -D`) before
they execute. It's the other half of the preservation coin: guardrails stop
the destructive command from running at all, `warrior-scan` finds and
recovers what's already at risk. Install it separately per its own `SKILL.md`.

## What's not here yet

`docs/ROADMAP.md` — the honest version of what's proven versus what's still
a direction, not a feature.

## Attribution

`skills/engineering/`, `skills/productivity/`, and
`skills/misc/git-guardrails-claude-code/` are sourced unmodified from
[mattpocock/skills](https://github.com/mattpocock/skills), MIT licensed.
See `NOTICES/` for the full license text and provenance. Everything else is
original work under this repo's own `LICENSE`.

## Who this is for

You, if any of this sounds familiar: you've used a GUI for git for years, not
because you don't understand the command line, but because it made state
*visible* in a way the CLI never did. You have projects going back a decade.
You're not sure what's actually backed up. You've been burned before. That's
not a knowledge gap — it's a rational response to a tool that hides things.
And separately: you want to build software the way an experienced engineer
does, not just the way that happens to compile. This is built for both.
