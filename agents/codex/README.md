# Codex role mapping

Codex agent definitions are TOML files in this directory and install to
`~/.codex/agents/` (or a project's `.codex/agents/`). Each definition delegates
to the canonical contract in `agents/roles/` and the matching Warrior skills.
The files are intentionally small: the contract, authority, and acceptance
checks remain in the shared role documents so every harness stays aligned.

| Warrior role | Codex skills |
|---|---|
| Guardian | `warrior`, then `warrior-authority` before any Git mutation |
| Wayfinder | `warrior`, then the evidence-backed wayfinder contract |
| Builder | `warrior-authority` and `warrior-worktree`, then the relevant implementation skill |

Builder has the same activation contract as every other harness: a work item,
leased worktree, exact file allow-list, Git authority, and acceptance checks.
