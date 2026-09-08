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
