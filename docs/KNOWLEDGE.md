# Git-backed knowledge sources

An AI knowledge source is authored material under Git. A harness embedding
database or search index is a rebuildable projection, not the authority. Keep
the source small, curated, provenance-aware, and explicit about freshness;
do not equate indexing more files with understanding more accurately.

`warrior-knowledge` is the portable, read-only foundation check:

```bash
warrior-knowledge /path/to/project/.knowledge --remote origin --json
```

It discovers the remote's symbolic HEAD rather than hardcoding `main` or
`master`, reports dirt and detached state, redacts URL userinfo, and requires
the local commit to equal the remote default branch. It does not create a
repository, enable a forge feature, commit, push, index, compact, or delete.
Those are project- and authority-specific operations layered above Warrior.

Private control planes can dogfood this contract with stricter local tools that also
checks its private Forge native-unit row and storage. Those Moof-specific
checks do not belong in universal Warrior.
