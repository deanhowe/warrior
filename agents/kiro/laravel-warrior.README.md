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
installed, its MCP server gives real tools (`search-docs`, `database-schema`,
`tinker`, `record-rule`, etc.) that beat guessing at Laravel internals. The
prompt tells the agent to look for a tool whose name contains "boost" — but
**Kiro's `tools`/`allowedTools` arrays require an exact server name**, and
that name is not standardised. In one real project on this machine it's
registered as `laravel-boost-local`; Boost's own docs describe the default as
`laravel-boost`. Check the target project's `.kiro/settings/mcp.json` (or ask
Kiro to list its own available tools once a session is open) and add the
exact name to this file's `tools` array as `"@<real-name>"` if you want Boost
tools available without the agent needing to discover them mid-session.

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

## Design note

This agent intentionally answers from bare Laravel idioms and whatever
Boost/knowledge tools are actually present in the project — it does not
assume any Moof-specific infrastructure exists. That's what makes it usable
at a day job with only Kiro CLI and nothing else installed.
