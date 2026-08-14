<!-- Place this content in .github/copilot-instructions.md at the root of a
     repository to give GitHub Copilot the same standing rules as the other
     Warrior agent configs. This is Copilot's real, documented mechanism for
     persistent repo-level agent instructions — there is no verified "Copilot
     agent JSON" format to match claude-warrior.md or kiro-warrior.json, and
     this project won't invent one and present it as real. -->

# Warrior — repo instructions for GitHub Copilot

This repository is preservation-first. Before proposing or running any git
operation beyond `status`, `diff`, `log`, or `show`:

1. Run `python3 bin/warrior-scan <root>` first, every time. It is read-only.
2. Read the findings ranked CRITICAL, HIGH, MEDIUM, INFO in that order.
   Resolve CRITICAL and HIGH before continuing with whatever else was asked.
3. For any recovery, copy the content out before touching the original —
   never apply a shelf, pop a stash, or reset toward a found commit first.
4. Never run `git reset --hard`, `git clean`, `git stash drop`, `git gc`, or
   any force-push yourself. If a genuine recovery needs one, state the exact
   command and wait for explicit approval — do not infer permission for it.
5. A command exiting successfully is not proof it did the right thing. Check
   the resulting state, not just the exit code — `warrior-protect` verifies
   by checking the server's own refs for exactly this reason.
6. If a path looks like it holds credentials or financial records, keep the
   finding but do not print sample filenames from it.

Full detail: `docs/SAFETY.md` (what protects you and why) and
`docs/JOURNEY.md` (the guided path through every tool).
