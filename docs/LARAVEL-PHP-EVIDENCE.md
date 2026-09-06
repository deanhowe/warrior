# Laravel/PHP evidence

`warrior-laravel dossier <project-root> [<project-root> ...]` is the first
Laravel-aware Warrior surface. It is deliberately a dossier, not an agent: it
collects deterministic evidence that a human or a later harness can inspect.

```bash
warrior-laravel dossier /path/to/laravel-app
warrior-laravel dossier /path/to/laravel-app --json
```

The command is read-only. It does not invoke Git, Artisan, Composer, a model,
or a network service. It reads only `composer.json` and a small allow-list of
known Laravel marker paths. It never reads or returns `.env`, `.tax`, `vendor`,
`node_modules`, build output, or generated files; it reports those only as
protected boundaries when present.

The JSON contract separates:

- `kind`: `laravel`, `php`, or `unknown`;
- `composer`: package identity, PHP/Laravel constraints, dependency names, and
  repository count (never repository URLs);
- `signals`: Laravel, multitenancy, broadcasting, Livewire, Mingle, tests, and
  frontend markers;
- `evidence_paths`: safe, structural paths that were present;
- `boundaries`: environment, tax, agent-state, and pruned-tree facts;
- `next_read_only_checks`: bounded follow-up work for a Guardian or Wayfinder.

This is intentionally independent of Moof. Moof can feed the JSON into its
knowledge or queue layers, but Warrior remains useful on a machine with no
Forge, DNS++, harness, or Ollama installation.

## Laravel Warrior workflow

1. Run `warrior-scan` first when the root is an existing repository.
2. Run `warrior-laravel dossier --json` to establish structural evidence.
3. Give the dossier to a read-only Guardian or Wayfinder model with an
   instruction to distinguish verified facts from uncertainty.
4. Store the resulting evidence and decision in the host project's knowledge
   unit; never let a model silently edit the project or its Git history.
5. Only a later, explicitly leased Builder may change exact files, after a
   deterministic test and authority record exist.

The dossier is not a claim that a Laravel application is healthy or deployable.
It is the small, repeatable evidence layer that makes those questions answerable
without handing a model the entire machine.
