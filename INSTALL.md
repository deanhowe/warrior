# Install

No dependencies beyond Python 3.9 or later. Everything is stdlib.

```bash
git clone <this-repo>
cd warrior
chmod +x bin/*
```

That's it — the tools run in place, from `bin/`.

## Try it

```bash
python3 bin/warrior-scan --help
python3 bin/warrior-facts --help
python3 bin/warrior-credits --help
python3 bin/warrior-history --help
python3 bin/warrior-upstream --help
```

`warrior-scan`, `warrior-facts`, `warrior-history`, and `warrior-credits` need **no
configuration at all**. Point `warrior-scan` at a directory and it works:

```bash
python3 bin/warrior-scan ~/code
```

`warrior-upstream` is also network-free. It needs an explicit provenance
manifest and a local checkout of the source commit to compare:

```bash
python3 bin/warrior-upstream audit \
  --manifest upstreams/mattpocock-skills.json \
  --source /path/to/mattpocock-skills
```

## If you want repo protection and classification

`warrior-protect` and `warrior-classify` talk to a git forge (Gitea,
Forgejo, or Gogs), and need it configured through environment variables —
never a config file, never a URL, never anything that could end up committed
by accident:

| Variable | What it is |
|---|---|
| `WARRIOR_GIT_SSH` | SSH base URL of the git server, e.g. `ssh://git@git.example.internal:2222` |
| `WARRIOR_GIT_API` | base URL of the forge API, e.g. `https://git.example.internal/api/v1` |
| `WARRIOR_GIT_OWNER` | owner/namespace on the git server that repositories belong to |
| `WARRIOR_GIT_TOKEN` | the forge API token — or omit this and store it in your OS keychain instead (see below) |

The API token is read from `$WARRIOR_GIT_TOKEN` if set, otherwise from the OS
keychain (macOS `security`, Linux `secret-tool`) under the service name in
`WARRIOR_KEYCHAIN_SERVICE`. It is never read from a file and never printed.

Don't have a forge yet? `skills/warrior-bootstrap/SKILL.md` walks through
setting one up.

## Everything else

`warrior-scan` and `warrior-credits` need nothing beyond what's above. Full
tool-by-tool detail, including what each one actually protects you from and
why, is in `docs/JOURNEY.md` — that's the guide to actually read once this
part's done.
