# Contributing

## Running tests

```bash
python3 -m unittest discover -s tests
```

Run this on **Python 3.9**, not just whatever version you have installed
locally. This project found a real crash that only reproduced under 3.9 —
macOS's still-common default system Python — and worked fine under 3.14. A
change that only passes on the latest interpreter hasn't actually been tested
for the audience this project is for.

## The safety contract every new tool must follow

Read `docs/SAFETY.md` in full before writing anything that touches git or
the filesystem. In short:

- **Every token of a git command is checked against an allowlist, not just
  the first one.** A guard that only inspects the subcommand's first
  argument can be bypassed — `git remote -v remove <name>` slips past a
  guard that only checks for `-v`, and has been verified to actually delete
  a remote. Validate every token.
- **`--output` (or any file-write flag) must refuse**: overwriting an
  existing file without an explicit `--force`, writing anywhere inside a
  `.git` directory, writing to a non-data file extension, and writing to a
  dotfile. All four traced back to a real incident: a mistyped `--output`
  once overwrote a repository's `.git/HEAD` and broke it.
- **Every `git status` call passes `--no-optional-locks -c core.fsmonitor=`.**
  Without them, `git status` rewrites `.git/index` and can execute a
  repository-supplied fsmonitor program — a tool that claims to be
  read-only and isn't is worse than one that admits it mutates.
- **No `shell=True`, ever.** Subprocess calls take a list of arguments, not
  an interpolated string.

## Before opening a pull request

1. Run the full test suite, on Python 3.9 if you can.
2. If your change touches a tool's read/write behavior, say in the PR
   description what you tried to break and what held.
3. Don't add a claim to the docs that isn't backed by something in this
   repo's own history or tests — this project has already had to walk back
   an overclaim once, and would rather stay accurate than sound impressive.
