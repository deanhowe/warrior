# Laravel Warrior: starter knowledge

A seed for this agent's project-native knowledge, not its personal `/knowledge`
store (that's local and ephemeral — see the README). Publish this into your
own project's native Knowledge unit (or just drop it in a `docs/` folder if
your fork has none) so it survives across machines and teammates, not just
one Kiro session:

```bash
# if your fork has a native Knowledge unit and you're using warrior-knowledge:
cp laravel-warrior.knowledge-seed.md /path/to/your/.knowledge/laravel-warrior.md
cd /path/to/your/.knowledge && git add laravel-warrior.md && git commit -m "seed: laravel-warrior starter knowledge"
warrior-knowledge /path/to/your/.knowledge --remote origin --publish

# otherwise, just point Kiro's own /knowledge at it directly:
# /knowledge add laravel-warrior docs/laravel-warrior.knowledge-seed.md
```

Everything below was verified live, on a real project, not copied from
documentation — each item earned its place by being wrong once.

## rtk: what's actually worth wrapping

Measured directly, not assumed:

| Command | Real result |
|---|---|
| `rtk grep -rn 'fn '` (large tree) | ~94% smaller |
| `rtk find` | ~81% smaller |
| `rtk git status` / `git log -50` | 63–76% smaller |
| `rtk ls` (small dir) | **2–5x bigger than plain `ls`** |
| `rtk tree` (small dir) | **5x bigger than plain `tree`** |
| `rtk read FILE` (default) | **0% — identical to `cat`** |
| `rtk read -l aggressive FILE` | ~70%+ smaller |

The pattern: rtk wins scale with genuine output size. It has real overhead of
its own, so wrapping something already small or already using a native tool
(`fs_read`, `grep`, `glob`) makes things worse, not better. Prefer native
tools for anything they already do; reach for `rtk` only for shell commands
with no native equivalent and genuinely large output (`git log`, `composer
show`, a real cross-file grep) — and always add `-l aggressive` to `rtk read`,
never call it bare.

## LSP tools need real coordinates, not guesses

`hover`/`definition`/`references`/`rename_symbol` take an exact line and
column — they are not "find this by name" tools. Confirmed live: an agent
asked to check a method's signature guessed line 1, column 1 (the top of the
file) and got useless results back. The correct pattern, also confirmed live:
`grep -n` the symbol first to get its real line, then call the LSP tool at
that exact position. Never skip the grep step.

## Kiro CLI config changes can need a desktop-app restart, not just a new session (verified live, 2026-09-08)

Adding new `preToolUse` hooks to `laravel-warrior.json` and starting a fresh
ACP session did NOT pick them up - even though this project's own README
already said "agent configs do not live-reload into a running session" and
a *new* session should have been enough. Confirmed the config file on disk
was correct; confirmed a brand-new, never-before-used agent name picked up
equivalent hooks instantly in the same conditions. The difference: a
`kiro_cli_desktop` background process (`ps aux | grep kiro`) had been
running since long before the hooks were added and had apparently already
resolved/cached "laravel-warrior" by name. `kiro-cli restart` (its own
documented command - not a raw `pkill`) restarted that background process;
the identical hook then fired correctly on the very next session. If a
hook or tool change to an agent you've already used this session doesn't
take effect in a fresh session, restart the desktop app before assuming
the config itself is wrong.

## `postToolUse` hooks are real but a pure side-channel (verified live, 2026-09-08)

Confirmed via a marker-file test: `postToolUse` hooks DO exist and DO fire
in this Kiro CLI version (matcher `@php-lsp` fired correctly on an
`edit_file` call). But unlike `preToolUse` - whose rejection message
becomes visible, reactable tool-call-failure content the model actually
sees and responds to - a `postToolUse` hook's own output never reaches the
model at all; the tool's `rawOutput` after a `postToolUse` hook fires is
identical to what it would be with no hook present. `postToolUse` is only
useful for side effects invisible to the agent (external logging, kicking
off a separate process) - never for injecting a nudge back into the
model's own reasoning. Anything meant to influence the model's next move
has to happen through a `preToolUse` block-and-suggest, the same mechanism
`rtk hook kiro` already proved works.

## A missing hook command fails open, not closed (verified live, 2026-09-08)

Long flagged as unverified (README used to say so explicitly): pointed a
`preToolUse` hook at a command that doesn't exist anywhere on PATH and
tried a real tool call. The call completed normally - Kiro CLI does not
block a tool call just because its hook command itself failed to launch.
This means it's safe to reference an optional tool (`rtk`,
`warrior-diagnostics-gate`) in an agent's hooks unconditionally: on a
machine that doesn't have it installed, the hook silently does nothing
rather than breaking every matching tool call.

## `warrior-diagnostics-gate`: enforcing rule 11 structurally, not just asking nicely (2026-09-08)

Rule 11 already said, twice, in increasingly explicit wording, to run
`diagnostics` after any php-lsp edit. Live-tested twice: the agent skipped
it both times regardless, relying on the test run alone to catch its own
mistakes (which happened to work, but is slower and misses error classes a
single test won't exercise). Prompt wording alone hit a real ceiling on a
cheap model. `bin/warrior-diagnostics-gate` (a `preToolUse` hook, wired
for both the `shell` and `@php-lsp` matchers) enforces it structurally
instead: a `@php-lsp/edit_file` or `rename_symbol` call marks the session
"diagnostics owed"; the next `shell` call that looks like a test run is
rejected once - exactly the `rtk` hook's own proven block-and-suggest
pattern - naming `@php-lsp/diagnostics` as the fix; running diagnostics
clears the flag. Verified live, post the desktop-restart fix above: the
block fired with the exact intended message, and the agent's own next
words were "I'll run diagnostics first as required" before actually
calling it. State is a small per-session JSON file (`tempfile.gettempdir()
/ "warrior-diagnostics-gate"`), one-shot on block so a model that ignores
the message once can never hit a permanent deadlock.

## Rule 6's self-indexing is reliable, but not spontaneous (verified live, 2026-09-08)

Two real, live ACP sessions against `local-starter` (raw wire log inspected,
not the friendly summary) settle this precisely: given a task that didn't
obviously need memory ("find how Fortify rate-limiting works and run the
test"), the agent never called `knowledge` at all — no `show`, no self-
indexing, despite rule 6 saying to do this "at the start of a session."
Given a task that made the need explicit ("check whatever knowledge you
have recorded, then summarize"), it correctly called `knowledge` twice
(show, then a real query) and cross-checked what it found against the
actual current `phpunit.xml`/`config/database.php`/`.env.example` rather
than trusting stale notes blindly - matching rule 3's verify-don't-assume
discipline.

**Conclusion: the self-indexing capability genuinely works; it just isn't
reliably self-initiated by a cheap model on a task that doesn't obviously
call for it.** This is a real, measured limitation of running Haiku-cheap,
not a broken tool wire-up - don't claim "it self-indexes every session"
without qualifying that it responds correctly when memory is clearly
relevant, but won't always reach for it unprompted otherwise.

## Everything else, shaken and verified live (2026-09-08)

Same two sessions also confirmed, via the raw ACP wire log:
- Native tools preferred correctly over shell: `glob`/`grep`/`read`
  (Directory and Line modes) used for all file discovery; `execute_bash`
  never touched for anything a native tool could do.
- Boost actually used as instructed: `@laravel-boost/application-info`
  called first, then `@laravel-boost/search-docs` with real, well-scoped
  queries (`"Fortify login rate limiting throttle"`, package-filtered to
  `laravel/fortify`) before answering a version-specific question - exactly
  rule 4's order of operations, not assumed from training data.
- The `rtk hook kiro` preToolUse hook fired for real on a raw
  `php artisan test ...` shell call, blocked it, and suggested the
  `rtk`-prefixed form. The agent's very next tool call was the corrected
  command verbatim, which then ran and reported 3 real, accurate passing
  tests with real timings - genuine adaptive retry, not a stall or a
  fabricated "it works" claim.

## Laravel Boost, verified against v2.7.1 source (2026-09-08)

Read from the actual installed package (`vendor/laravel/boost/src/Mcp/`),
not assumed from a plausible-sounding docs skim — and cross-checked against
the real published docs at laravel.com/docs/boost, which turned out to lag
the installed version by at least one tool.

**Real, default-enabled MCP tools** (kebab-case names are
`Str::kebab(class_basename($tool))`, confirmed via
`Laravel\Mcp\Server\Primitive::name()` — no `#[Name]` overrides exist on any
Boost tool): `search-docs`, `application-info`, `database-schema`,
`database-query`, `database-connections`, `browser-logs`, `last-error`,
`read-log-entries`, `get-absolute-url`, `record-rule`.

**`tinker` is real but off by default** — its class exists
(`Tinker.php`) but `shouldRegister()` returns
`config('boost.tinker_tool_enabled', false)`. This is why it's absent from
the official docs' tool table even though the source ships it: it's opt-in,
presumably for blast-radius reasons (arbitrary PHP execution). Never assume
it's available just because a boost-named MCP server exists — check the
live tool list, or fall back to a real `php artisan tinker --execute=`
shell call.

**`record-rule`'s real schema has three required params, not two**:
`glob`, `title`, `note` — all required (confirmed in `RecordRule.php`'s
`schema()`). A rule recorded with only a glob and a note will be rejected;
this was wrong in an earlier version of this very file.

**`.ai/rules/index.md` is a real, documented, load-bearing mechanism**, not
personal-knowledge boilerplate: Boost's project-rules system stores rules
as markdown files under `.ai/rules/`, each with YAML frontmatter declaring
the path globs it applies to, and maintains an `index.md` mapping globs to
files. Laravel's own docs state plainly: "Agents are instructed to consult
this index before planning or editing any file, so a rule is only loaded
when it is relevant." This is separate from `record-rule`'s target (same
directory, but the AGENT-facing consumption side) and from a Kiro agent's
own personal `knowledge` tool (session-scoped, not shared/committed).

**`infer-conventions` is a real Boost skill**, not a guess — it sweeps an
existing codebase across a checklist (validation, controllers,
authorization, models, architecture, testing, frontend, database, console)
and proposes rules from what the code actually does, skipping framework
defaults and anything Pint/Rector already enforce. For a years-old
application with no `.ai/rules` yet, this is the right way to bootstrap —
not re-deriving the same conventions by hand every session.

**Guidelines vs. skills, precisely**: guidelines (`AGENTS.md`/`CLAUDE.md`
etc.) load upfront and are broad/foundational; skills
(`livewire-development`, `pest-testing`, `infer-conventions`, and any
project's own `.ai/skills/*/SKILL.md`) activate on-demand for a specific
task. Neither describes *your* application's own conventions — that's what
project rules (`.ai/rules/`) are for.

## Laravel Boost silently disappears without a real `.env`

If `php artisan boost:mcp` reports "no commands defined in the boost
namespace" even though `laravel/boost` is genuinely installed in `vendor/`,
check for a missing `.env`/`APP_KEY` before suspecting the MCP wiring itself.
Boost only registers its MCP command in local/testing-like environments;
without `.env`, Laravel defaults toward production and Boost stays silent —
confirmed as the actual cause once, after wrongly suspecting the MCP config
first.

## Fresh-clone test failures: three specific gaps, not a code bug

Confirmed live on a real project (local-starter, 2026-09-08): a fresh clone
went from "44 tests failing" to "44 passing, 1 legitimately skipped" without
touching a single line of application code. All three causes below are
environment gaps, and all three are checked automatically by
`warrior-laravel doctor <path>` (read-only — never opens `.env` for anything
but a boolean "is this key present" check, never prints a value). Run it
first, before editing app code in response to a failing suite.

1. **Per-connection env drift.** A multitenancy app (spatie/laravel-
   multitenancy or similar) typically defines separate `tenant`/`landlord`/
   `testing` connections in `config/database.php`, and — easy to miss — each
   one resolves its host/port through its OWN env var with its OWN default:
   `env('DB_LANDLORD_PORT', '3325')`, `env('DB_TESTING_PORT', '3325')`, etc.
   Fixing one connection's `.env` entry (say, after chasing an "access
   denied" error) and assuming the sibling connections inherited the fix is
   silent: the unfixed one keeps resolving to its own stale coded default
   and fails with a *different*, unrelated-looking error. Real sequence hit
   live: fixed `DB_LANDLORD_HOST`/`DB_LANDLORD_PORT`, suite went from one
   error to 44 different ones, because the `testing` connection was still
   silently defaulting to port 3325 (an old, unrelated MySQL instance) while
   `landlord` now correctly pointed at 3306. Fix: `php artisan tinker
   --execute="dump(config('database.connections.<name>'))"` for EVERY named
   connection the failing test touches, not just the one already suspected.

2. **Multitenancy needs a global-grant DB user, not a scoped one.** If the
   app provisions a real, separate physical database per tenant (grep for
   `ensureDatabaseExists`/`CREATE DATABASE` in `database/factories` or
   `database/migrations`), the DB user needs `GRANT ALL PRIVILEGES ON *.* TO
   '<user>'@'%'` — global CREATE/DROP — not grants scoped to a handful of
   named databases. A narrowly-scoped grant looks complete (it covers every
   database you already know about) but fails the moment a test factory
   creates a brand-new tenant with a Faker-generated slug: `Access denied
   for user '<user>'@'%' to database '<random-slug>'`. This is normal and
   expected for this architecture, not a security mistake to second-guess —
   just grant it.

3. **Vite manifest missing means the frontend was never built, not a bug.**
   `Vite manifest not found at: public/build/manifest.json` on any test that
   renders a Blade layout calling `@vite(...)` means exactly what it says:
   run `npm install && npm run build`. Don't chase this in PHP.

Also: Laravel Sail's installer (`artisan sail:install --with=mysql`)
modifies existing tracked files as a side effect — it edited a real
project's `phpunit.xml` (replaced commented-out sqlite lines with a real
`DB_DATABASE` env entry) and created a new `compose.yaml`. Diff what changed
and say so plainly; don't silently accept or silently revert either one.

## Why "verify before claiming done" isn't optional

A cheap model será wrong about specifics more often than a frontier one —
that's not a flaw to route around, it's the tradeoff for the cost. The fix
isn't smarter guessing, it's cheap, fast verification always being available:
`vendor/bin/pint --dirty --format agent` after any PHP edit, `diagnostics` on
any touched file, `rtk test <command>` for compact failure-only test output.
None of these are optional flourishes — they're what makes a 10x-cheaper model
trustworthy enough to actually delegate to.
