# Agent configs

One persona, three harnesses, stated honestly by how tested each one is.

| File | Harness | Tested? |
|---|---|---|
| `claude-warrior.md` | Claude Code subagent | **Not yet run, and can't be from inside a running session** — Claude Code loads subagent definitions at startup, not live. Written to the documented format, following the same rules as the other two, but that's a review claim, not a tested one. |
| `kiro-warrior.json` | Kiro CLI agent | **Tested live, and it initially failed.** Kiro checks each `&&`-joined shell sub-command against `allowedCommands` separately, not as one compound string — the agent's own `warrior-scan` calls were rejected by its own allowlist on first run. Fixed by allowing bare `cd <path>` as its own pattern (harmless alone: no read, write, or execute). Retested: the agent ran `warrior-scan` on this repository for real and correctly summarized a genuine finding. |
| `copilot-warrior.md` | GitHub Copilot | **Tested live via ACP session/prompt.** Content installed as `.github/copilot-instructions.md`, asked directly what it must do before any git operation, answered correctly from the instructions on the first attempt — no editing needed. Not an agent-JSON config: Copilot has no verified equivalent format on the machine this was built on, and this project won't invent one and present it as real. |

Two of three have now been run for real, not just reviewed. The Kiro result
is the reason this table exists: the file looked correct — valid JSON,
sensible patterns — and was still broken until it was actually executed.
Review and testing are different claims; say which one you mean.

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
