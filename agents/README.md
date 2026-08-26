# Warrior agents

Warrior has three portable roles with one authority model and native profiles
for Kiro CLI, Claude Code, and GitHub Copilot CLI. Codex uses its native skills
rather than an invented profile format.

| Role | Purpose | Headless queue state |
|---|---|---|
| Guardian | preservation and risk gate | read-only; may be dispatched |
| Wayfinder | evidence-backed decision mapping | read-only; may be dispatched |
| Builder | one authorised implementation slice | locked until the adapter enforces its lease and exact file scope |

The canonical contracts are in `roles/`. Harness projections live in `kiro/`,
`claude/`, and `copilot/`. `codex/README.md` maps the same roles to Codex's
native skill mechanism. Run `warrior-agents validate` after any change; role
authority and native format are tested independently from a paid model turn.

The older `kiro-warrior.json`, `claude-warrior.md`, and
`copilot-warrior.md` files remain as compatibility profiles for the original
single preservation persona. They are not the current multi-role contract.

## Install

Installation is plan-first and refuses to overwrite a different existing
profile:

```bash
warrior-agents install copilot guardian --project /path/to/project
warrior-agents install copilot guardian --project /path/to/project --apply
warrior-agents install kiro wayfinder --apply
```

Start a new harness session after installation. Select the resulting agent as
`warrior-guardian`, `warrior-wayfinder`, or (only with a complete lease)
`warrior-builder`.

## What validation proves

`warrior-agents validate` parses every Kiro profile, checks every native
frontmatter name, confirms read-only roles do not gain write authority, checks
the Builder gates, and asks Kiro CLI to validate its own JSON when installed.
It spends no model credits. A later live capability task proves that a selected
model obeys the profile; a successful adapter exit alone does not.
