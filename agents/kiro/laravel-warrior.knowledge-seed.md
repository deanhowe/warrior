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

## Why "verify before claiming done" isn't optional

A cheap model será wrong about specifics more often than a frontier one —
that's not a flaw to route around, it's the tradeoff for the cost. The fix
isn't smarter guessing, it's cheap, fast verification always being available:
`vendor/bin/pint --dirty --format agent` after any PHP edit, `diagnostics` on
any touched file, `rtk test <command>` for compact failure-only test output.
None of these are optional flourishes — they're what makes a 10x-cheaper model
trustworthy enough to actually delegate to.
