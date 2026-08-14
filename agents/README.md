# Agent configs

One persona, three harnesses, stated honestly by how tested each one is.

| File | Harness | Tested? |
|---|---|---|
| `claude-warrior.md` | Claude Code subagent | Not yet run. Written to Claude Code's documented subagent format, following the same rules as the other two, but this exact file has not been exercised end-to-end. |
| `kiro-warrior.json` | Kiro CLI agent | Not yet run. Modelled directly on a real, working, deny-by-default Kiro config from the private system this project was extracted from — the shape is proven, this exact file is not. |
| `copilot-warrior.md` | GitHub Copilot | Not an agent config — Copilot has no verified equivalent JSON format on the machine this was built on, and this project won't invent one and present it as real. This is content for `.github/copilot-instructions.md`, Copilot's actual documented mechanism for persistent repo-level instructions. |

## Install

- **Claude Code**: copy `claude-warrior.md` into your project's
  `.claude/agents/` directory.
- **Kiro CLI**: copy `kiro-warrior.json` into `~/.kiro/agents/` or your
  project's `.kiro/agents/`, then run with `--agent warrior`.
- **Copilot**: copy the content of `copilot-warrior.md` (everything after the
  HTML comment) into `.github/copilot-instructions.md` at your repository
  root.

## The shared rules, in one place

All three carry the same standing instructions: scan before touching
anything, handle CRITICAL/HIGH findings first, copy before you touch an
original, never run a destructive git verb without explicit named approval,
verify effects rather than trust exit codes, and withhold sample filenames
from sensitive-looking paths even when a finding still fires.

If you find a way any of these three drift from that shared contract, that's
a bug — the point of writing it once and copying the rules into three formats
is that they shouldn't diverge.
