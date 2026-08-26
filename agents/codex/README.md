# Codex role mapping

Codex uses skills as its native role mechanism; Warrior does not invent a
fourth agent-file format and call it support.

| Warrior role | Codex skills |
|---|---|
| Guardian | `warrior`, then `warrior-authority` before any Git mutation |
| Wayfinder | `wayfinder`, with `warrior` first when preservation is uncertain |
| Builder | `warrior-authority` and `warrior-worktree`, then the relevant implementation skill |

Builder has the same activation contract as every other harness: a work item,
leased worktree, exact file allow-list, Git authority, and acceptance checks.
