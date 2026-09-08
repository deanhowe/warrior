# Laravel Warrior (Kiro CLI agent)

A Haiku-pinned, Laravel-specialised Kiro agent. Portable by design: nothing in
`laravel-warrior.json` depends on Moof, DNS++, giga-brain, or any private
infrastructure. It runs on `claude-haiku-4.5` for near-zero cost, and uses
only capabilities every Kiro CLI install already ships.

## Install

Copy the file to Kiro's agent directory, then start a fresh session (agent
configs do not live-reload into a running chat):

```bash
cp laravel-warrior.json ~/.kiro/agents/laravel-warrior.json
kiro-cli chat --agent laravel-warrior
```

Or drop it into a specific project's own `.kiro/agents/` directory instead of
the global one, if you only want it available there.

## What's genuinely built in, verified 2026-09-08

- **`knowledge` tool** — Kiro CLI maintains a local, per-agent knowledge store
  automatically (`~/Library/Application Support/kiro-cli/knowledge_bases/<agent>_<hash>/`).
  It costs nothing, needs no setup, and is populated by using it in-session
  (Kiro's `/knowledge` mechanism). Confirmed real by inspecting a live,
  populated store on disk — this is stock Kiro, not a Moof add-on.
- **`todo` / `thinking` / `delegate` / `introspect`** — free Kiro built-ins,
  wired into this agent's `tools` list so the model actually reaches for them
  instead of defaulting to raw shell/grep for everything.

## Laravel Boost — optional, name varies per project

If the target project has [Laravel Boost](https://github.com/laravel/boost)
installed, its MCP server gives real tools that beat guessing at Laravel
internals. **Boost only registers `boost:mcp` when the app has a real
`.env` with an `APP_KEY`** — without one, Laravel defaults toward
production and Boost deliberately stays silent (confirmed live: `php
artisan boost:mcp` failed with "no commands defined in the boost namespace"
in an otherwise-correct project that was simply missing `.env`). If Boost
seems unavailable, check `.env`/`APP_KEY` exist before suspecting the MCP
wiring itself. The prompt tells the agent to look for a tool whose name
contains "boost" — but **Kiro's `tools`/`allowedTools` arrays require an
exact server name**, and that name is not standardised. In one real project
on this machine it's registered as `laravel-boost-local`; Boost's own docs
describe the default as `laravel-boost`. Check the target project's
`.kiro/settings/mcp.json` (or ask Kiro to list its own available tools once
a session is open) and add the exact name to this file's `tools` array as
`"@<real-name>"` if you want Boost tools available without the agent
needing to discover them mid-session.

**The real tool list**, verified against `laravel/boost` v2.7.1 source on
2026-09-08 (the [official docs](https://laravel.com/docs/boost) lag the
installed version by at least one tool, so source beat docs here):
`search-docs`, `application-info`, `database-schema`, `database-query`,
`database-connections`, `browser-logs`, `last-error`, `read-log-entries`,
`get-absolute-url`, `record-rule` — all registered by default. `tinker`
exists in source but is **off by default**
(`config('boost.tinker_tool_enabled', false)`); don't assume it's there
just because Boost is installed.

**`.ai/rules/index.md` — a real mechanism worth using deliberately.**
Boost's project-rules system (separate from Kiro's own per-agent
`knowledge` store) files recorded rules under `.ai/rules/*.md` with
path-glob frontmatter, and maintains an index mapping globs to files.
Laravel's docs are explicit that agents should read this index before
planning or editing any file. `record-rule`'s real schema needs three
required params — `glob`, `title`, `note` — not two; an earlier version of
this agent's prompt only knew about two of them. For an established
codebase with no `.ai/rules` yet, Boost ships an `infer-conventions` skill
that sweeps existing code and proposes rules from what it actually finds —
the right way to bootstrap, rather than re-deriving the same conventions by
hand every session.

## PHP language server — real code navigation, not just grep

Adding `@php-lsp` (with `definition`/`references`/`hover`/`diagnostics`
auto-approved, `edit_file`/`rename_symbol` gated behind approval like
`fs_write`) gives the agent real symbol-level navigation instead of relying
on text search for everything. This uses
[`mcp-language-server`](https://github.com/isaacphi/mcp-language-server) — a
generic, public LSP-to-MCP bridge, not anything Moof-specific — pointed at
[Intelephense](https://intelephense.com/), a standard PHP language server.

Setup on macOS:

```bash
# 1. Intelephense (the actual PHP language server)
npm install -g intelephense

# 2. mcp-language-server (the generic bridge, works with any LSP)
go install github.com/isaacphi/mcp-language-server@latest
```

Two real macOS gotchas, hit and confirmed on this machine, not theoretical:

- **`go install` puts the binary in `$(go env GOPATH)/bin`, which is not on
  `PATH` by default.** Add it: `export PATH="$(go env GOPATH)/bin:$PATH"` in
  your shell profile. If `mcp-language-server` isn't found when Kiro tries to
  launch it, this is almost certainly why — confirmed live, `which
  mcp-language-server` returned nothing until this was added.
- **If you manage Node via `nvm`, `npm install -g` installs into whichever
  Node version is currently active**, and switching versions later can hide
  the binary again even though it's still on disk. A Homebrew-installed
  Node avoids this; with `nvm`, either pin the version you installed
  Intelephense under, or reinstall it after switching.

Add this to the target project's `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "php-lsp": {
      "command": "mcp-language-server",
      "args": ["-workspace", ".", "-lsp", "intelephense", "--", "--stdio"]
    }
  }
}
```

First run indexes the whole project and can take a couple of minutes on a
large codebase — this is Intelephense building its index, not a hang.

## RTK — the one real setup step, and why it's needed

`rtk hook kiro` (the `preToolUse` hook wired into this agent) does not exist
in public `rtk` yet. Checked live on 2026-09-08: Dean's own PR
(`rtk-ai/rtk#3302`) was closed as a duplicate of `#1596`, and neither is
merged — upstream's current README has no Kiro CLI row at all. The working
version of this feature exists only on Dean's own public fork:

```bash
# build from the fork branch that has the feature (public GitHub, no Moof needed)
cargo install --git https://github.com/deanhowe/rtk --branch feat/kiro-cli-hook

# then wire the hook into Kiro automatically
rtk init -g --agent kiro-cli
```

**Not yet verified**: what happens if this agent's `preToolUse` hook fires
and `rtk` isn't installed at all (command-not-found vs. Kiro's own hook
error handling). Test this deliberately in a low-stakes session before
relying on it — don't assume it fails open.

## `warrior-laravel doctor` — fresh-clone test-environment checks

A real, tested (`tests/test_warrior_laravel_doctor.py`, run via `pytest`)
read-only diagnostic, added after a multi-hour live debugging session turned
up the same pattern three times: a failing test suite on a fresh clone was
never an application bug, it was one of three environment gaps. Rule 15 in
`laravel-warrior.json` tells the agent to run this first, before touching
app code, whenever tests fail on what looks like a fresh or freshly-changed
environment:

```bash
# from anywhere inside your project (warrior's bin/ needs to be on PATH,
# or call it by full path: python3 /path/to/warrior/bin/warrior-laravel doctor .)
warrior-laravel doctor .
```

It checks, without ever reading or printing a value from `.env` (only
whether a given key is *present*):

- **DB connection drift** — a multi-connection app (tenant/landlord/testing
  split) where one connection's host/port env var was overridden in `.env`
  and a sibling's wasn't, so it silently stays on a stale coded default.
- **Vite manifest missing** — a Blade layout calls `@vite(...)` but
  `public/build/manifest.json` doesn't exist, meaning the frontend was never
  built (`npm install && npm run build`).
- **Multitenancy dynamic-database provisioning** — an informational note
  when `spatie/laravel-multitenancy` is present alongside
  `ensureDatabaseExists`/`CREATE DATABASE` in factories or migrations: the DB
  user needs global `CREATE`/`DROP`, not grants scoped to named databases.

If `warrior-laravel` isn't on `PATH` (e.g. this warrior clone isn't
installed on the target machine), the agent's prompt has the same three
checks spelled out to do by hand — the tool is a shortcut, not a
requirement.

## Design note

This agent intentionally answers from bare Laravel idioms and whatever
Boost/knowledge tools are actually present in the project — it does not
assume any Moof-specific infrastructure exists. That's what makes it usable
at a day job with only Kiro CLI and nothing else installed.
