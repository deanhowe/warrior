---
name: warrior-bootstrap
description: Guide a developer from "a decade of scattered repositories" to their own working local control plane — a private forge, a small brain, and an authority-bounded work queue for AI agents. Use when setting Warrior up on a new machine, when deciding what to provision, or when a developer asks how to build something like this for themselves.
---

# Warrior bootstrap

Your job is not to install a product. It is to take a developer who has ten
years of repositories scattered across a machine and leave them with a control
plane **they own and understand**.

Work in this order. Never skip ahead: each step exists because the next one is
dangerous without it.

```
1. Assess      what is actually here?               read-only
2. Preserve    what could be lost right now?        read-only
3. Provision   what is missing?                     installs, with consent
4. Protect     give every repository a home          mutates, with consent
5. Brain       record what we learned                new local database
6. Control     bound the work agents may do          new local schema
```

Read `warrior-authority` before step 4. Nothing after step 2 is safe without it.

## Platform

This reference implementation targets **macOS 26 "Tahoe" and later, exclusively**.
Latest SwiftUI/AppKit only; no back-compatibility shims. The Python inspection
tools (`warrior-facts`, `warrior-scan`, `warrior-classify`, `warrior-protect`)
are cross-platform and have no macOS dependency — only the optional desktop app
is Tahoe-bound.

Do not port the desktop app backwards. Suggest the CLI instead.

## 1. Assess — read-only

```
warrior-facts orient          # cold-start bundle
warrior-facts toolchains      # languages, runtimes, package managers
warrior-facts services        # what is listening right now
warrior-facts repos <roots>   # bounded repository inventory
```

Report what is present and what is missing. Expect to need:

| Need | Why | Check |
|---|---|---|
| `git` | everything | `git --version` |
| Python 3.11+ | the inspection tools | `python3 --version` |
| SQLite 3 | the brain | usually already present |
| Xcode Command Line Tools | required before Homebrew or any Swift build on macOS | `xcode-select -p` |
| Full Xcode | only if building the desktop app | `xcodebuild -version` |
| A Git forge | off-repository homes | step 3 |

**Verify the interpreter, not the command name.** `python3` on a developer
machine frequently resolves to a different install than the one holding their
packages. Confirm the interpreter that actually has what you need, and record
its absolute path. Never assume `python3 -m <module>` will work because
`<module>` is "installed".

State plainly what you could not determine. An unknown is not an absence.

## 2. Preserve — read-only, and do this before touching anything

```
warrior-scan <roots>
```

Eleven loss vectors, including several that no Git command will ever show:
editor shelves, index-only blobs, stashes, unreachable commits, untracked work,
repositories with no remote at all.

On the machine this was built for, that scan found a **706-day-old editor
shelf**, 58 stashes going back eleven years, four blobs existing only in the
index, 37 unreachable commits, and 50 repositories with no remote whatsoever.
None of that was carelessness. It is what happens when a tool shows you one
slice of state and hides the rest.

Preserve findings to a dated directory before any consolidation. Nothing the
scan reports is a deletion candidate — not `tmp/`, not archives, not
generated output, not "obviously dead" branches.

## 3. Provision — installs, with explicit consent per item

Present a list; install nothing silently. For each missing item show what it
is, what it changes, and let the developer decline.

**The forge is the important choice.** Warrior needs *a* forge with an HTTP API
and SSH transport. It does not need any specific one. Gitea is the reference
because it is a single binary, self-hosts trivially, and includes a package
registry. Forgejo works identically. A hosted server the developer already
pays for is also fine — skip provisioning and just configure.

Reference deployment shape:

```
HTTP API      http://127.0.0.1:3030/api/v1
Web UI        http://forge.example.internal        (a friendly local hostname)
Git SSH       ssh://git@127.0.0.1:2222/<owner>/<repo>.git
Service       a user-level service manager, keep-alive enabled
Config        <forge-root>/custom/conf/app.ini
```

Two details that will bite otherwise:

- **The API returns the bind address, not the friendly hostname.** Repository
  `html_url` values come back as `http://127.0.0.1:3030/...`. If you show those
  to a human, rewrite the origin to the friendly hostname. Keep the API address
  for requests and the friendly address for links; do not conflate them.
- **Local hostname resolution needs a resolver entry, not a `dig` test.** On
  macOS, a bare `dig <name>` bypasses `/etc/resolver/*` and returns a false
  `NXDOMAIN` even when the name resolves correctly for every real client.
  Verify with the actual client path (`curl`, a browser, `ping`) or by querying
  the resolver's address and port explicitly.

Do **not** have the desktop app manage the forge's lifecycle. Provisioning is a
one-time, consent-gated CLI operation. The app only ever observes.

## 4. Protect — the first step that mutates

```
warrior-protect --unprotected        # list candidates, then stop
warrior-protect <path>               # dry run: show the plan
warrior-protect <path> --apply       # create, wire, push, verify
```

Dry run by default. Requires `warrior-authority`. The three rules that matter:

- **Create ordinary repositories, never push into a pull-mirror.** A pull-mirror
  is overwritten from upstream on a schedule; anything pushed into one is
  destroyed at the next sync. Detect and refuse.
- **Publish over SSH, and verify by refs.** A filesystem path supports
  `ls-remote`/`clone`/`fetch` but its push is rejected at the receiving hook —
  and a filesystem push into an up-to-date repository **exits 0 having sent
  nothing**. Confirm the local HEAD appears among the remote's refs.
- **Say what this does and does not buy.** If the forge's bare repositories sit
  on the same physical volume as the working trees, this protects against a
  deleted tree, a bad checkout, or a lost branch. **It is not off-machine
  redundancy.** And a remote protects committed objects only — shelves, index
  state, stashes, untracked files and dangling objects gain nothing from it.
  Never let a developer believe a mirror means "backed up".

## 5. Brain — a small local database they own

One SQLite file. Plain tables, no service, no daemon, readable with any client.
Start with facts the developer will actually query:

```
projects        path, name, status, purpose, languages, frameworks, last_scanned
repositories    path, branch, head, remotes, ahead/behind, dirty counts
findings        loss-vector findings over time, so risk can be seen falling
lessons         mistakes, wins, patterns — with what to do differently
decisions       decision, reasoning, outcome
```

Two hard-won rules:

- **One store, or explicit synchronisation between stores.** Two memory tables
  that both look authoritative will silently diverge, and you will trust the
  empty one. If a second store exists, make the boundary explicit and visible.
- **Cache entries carry an expiry, and readers must honour it.** A snapshot
  table with a short validity window and nothing refreshing it does not
  degrade gracefully — every consumer either blocks forever or reads stale
  numbers as truth. Label staleness in every surface that displays it.

## 6. Control plane — bound what agents may do

This is what makes AI agents safe against a decade of irreplaceable work.

```
work_items      objective, acceptance evidence, state
task_runs       one bounded assignment to one agent profile
leases          worktree, file scope, validation contract, authority
events          append-only record of every transition
```

Minimum viable bounds on any agent task: **objective, completion evidence,
maximum turns, timeout, maximum cost, file scope, and Git authority.** A task
without all seven is not bounded, whatever its prompt says.

For work an agent performs in isolation, give it a **lease**, not the
repository:

```
repository + baseline commit     where it forks from
branch <agent>/<work-item-slug>  the agent's name is the namespace
worktree path                    an isolated tree
file scope                       exact paths, enumerated
validation contract              the commands that must pass
dirty baseline digest            pre-existing mess, to be excluded not committed
return strategy                  how the work comes back
retention policy                 preserve by default
commit / push authority          per lease, never per agent
```

Branch namespacing by agent turns the forge into the exchange between them:
one agent pushes `<agent>/<slug>`, another fetches and reviews it. The forge is
the medium, branches are the messages, leases are the contracts.

**Record which model answered, not only which was requested.** Adapters fall
back silently. Keep `requested_model` and `model` as separate fields and treat
a mismatch as a first-class incompatibility to preserve, not an error to retry
past.

**Automation never calls a paid model directly.** A schedule may enqueue a
bounded task run after checking budget, time, authority and existing leases.
Fail closed: if budget freshness cannot be established, nothing runs.

## The optional desktop surface

A menubar app is the right shape: always available, never in the way. It
observes; the CLI acts.

On macOS 26, the primary window must be created imperatively —
`NSWindow` + `NSHostingView` in the app delegate's launch callback. A SwiftUI
`Window(title, id:)` used as the first scene is silently suppressed, and
`WindowGroup` is also suppressed once other `Window` scenes exist. Keep SwiftUI
scenes for secondary windows only.

Three implementation rules, each from a real failure:

1. **One polling task, not several timers.** Multiple timers writing a shared
   stored reference caused sustained CPU load, because each overwrote the
   previous and none could be cancelled. Use a single cancellable task that
   sleeps between cycles and cannot re-enter while a cycle is in flight.
2. **Kill the process group, not the process.** Subprocesses that spawn their
   own children survive an ordinary timeout and can spin at full CPU
   indefinitely. Terminate the group, and always set a timeout.
3. **Make the token unprintable.** Wrap it in a type whose string and debug
   representations are redacted, keep it in the OS keychain, and short-circuit
   to a mock when running in a UI preview so previews never read real
   credentials.

## Deliberately not in v1

- No merge-conflict UI. Divergence sends the developer to their own tools.
- No filesystem watcher, no auto-commit. Warrior inspects; it does not sync.
- No SSH key generation. Use the keys the developer already has.
- No forge lifecycle management from the desktop app.
- No destructive Git operations anywhere, at any privilege level.
- No history rewriting. Rotate a leaked credential instead; rewriting breaks
  every existing clone and is rarely the proportionate response.

## Done looks like

The developer can answer, from their own machine, without asking anyone:

- what work exists here that has only one copy?
- which repositories have nowhere else to live?
- what is this repository for, and is it still alive?
- what may an agent change, in which files, with what authority?
- what did we learn last time, and what did we decide?

They do not have your control plane. They have theirs, and they know how it
works, because they watched it get built.
