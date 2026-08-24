# Install

Warrior targets macOS Tahoe 26 and requires Python 3.9 or later. The assessment
tools use only the standard library. Building a history rewrite candidate also
requires `git-filter-repo`:

```bash
brew install git-filter-repo
```

```bash
git clone <this-repo>
cd warrior
chmod +x bin/*
```

Add the checkout's `bin` directory to the macOS login-shell path. For the
standard Warrior checkout on this machine, add this line to `~/.zprofile`:

```bash
export PATH="$HOME/PROJECTS/warrior/bin:$PATH"
```

Use the real checkout path if Warrior lives elsewhere, then start a new login
shell (`exec zsh -l`). The commands no longer need a `python3 bin/` prefix.

## Try it

```bash
warrior-scan --help
warrior-facts --help
warrior-credits --help
warrior-history --help
warrior-upstream --help
```

`warrior-scan`, `warrior-facts`, `warrior-history`, and `warrior-credits` need **no
configuration at all**. Point `warrior-scan` at a directory and it works:

```bash
warrior-scan ~/code
```

`warrior-upstream` is also network-free. It needs an explicit provenance
manifest and a local checkout of the source commit to compare:

```bash
warrior-upstream audit \
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
