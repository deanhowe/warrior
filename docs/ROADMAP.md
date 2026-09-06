# Roadmap

## Chapter 1 — Know your machine, never lose work (SHIPPED)

Thirteen tools, each read-only or additive, each with real tests:

- **`warrior-scan`** — read-only work-loss scan: what could be lost right now,
  and where. Eleven vectors, from JetBrains shelves to unreachable commits.
- **`warrior-facts`** — answers questions about this developer's machine,
  read-only: where is X, what repositories exist, what's unprotected.
- **`warrior-protect`** — gives an unprotected local repository a verified
  home on a git server, and proves it landed by checking the server's refs,
  not by trusting an exit code.
- **`warrior-classify`** — classifies the repositories on a git server by
  purpose (first-party, mirror, archive, package), and can record that as
  forge topics.
- **`warrior-credits`** — live credit/quota balance across every AI harness
  on this machine, at zero token cost, using each harness's own client-side
  status command rather than a billed prompt.
- **`warrior-server-status`** — is your git forge actually healthy: reachability,
  disk headroom, mirror staleness, backup freshness. "Answers HTTP 200" and
  "wired up correctly" are different claims; this checks the second one.
- **`warrior-sidecar`** — gives a project a named, versioned space beside it
  that its own commit history never sees (goals, tmp, wiki), instead of a
  gitignored directory with zero protection at all. Scaffolds only;
  `warrior-protect` does the actual pushing, so there's one implementation
  of verified-by-refs safety, not two drifting apart.
- **`warrior-knowledge`** — verifies the authored Git source behind an AI
  knowledge base without assuming a particular harness, index, or forge.
- **`warrior-history`** — assesses reachable and unreachable repository
  history without rewriting it: large blobs, database/archive/build artifacts,
  unrelated roots, and commits on Git's expiry clock.
- **`warrior-upstream`** — verifies a transformed vendored source against an
  explicit manifest: pinned commit, selected trees, renames, declared
  divergences, and local extras. It never fetches or updates either tree.
- **`warrior-project`** — discovers nested Git and Composer boundaries before
  import and produces a state-pinned checkpoint closure plan with one verdict
  per repository. It withholds sensitive names and does not create checkpoints,
  repositories, packages, remotes, commits, or pushes.
- **`warrior-laravel`** — builds a bounded Laravel/PHP evidence dossier from
  Composer and known framework marker paths. It never reads environment or
  dependency trees and never invokes Git, Artisan, Composer, a model, or a
  network service.

Exact file/directory history removal into a new, disconnected, verified
candidate is shipped. So are a one-branch public-history audit and a public
projection builder: it can rewrite identity metadata, apply a private
`git-filter-repo` replacement file, exclude every unselected ref, and fail
closed unless the result passes the same audit. Canonical cutover, commit
surgery, and pushes remain explicit human operations. Upstream
refresh/candidate generation is also not shipped.

This chapter is real. It has been run against 415 repositories on a live
machine, adversarially audited for safety and portability, and used to
recover work that had been sitting unprotected for years.

## Chapter 2 and beyond — build your own control plane (ROADMAP, NOT SHIPPED)

Nothing below this line exists yet. It describes the direction, not a
capability you can use today.

1. **Fact discovery about your machine** — beyond `warrior-facts`' current
   scope: a persistent index of what's where, refreshed rather than
   recomputed from scratch every time.
2. **Durable memory of decisions** — a record of what was found, what was
   decided, and why, that survives a single session and can be queried later.
3. **Routing work to cheap models** — a deliberate policy for sending
   mechanical, well-specified work to the cheapest capable model, and
   reserving expensive judgment for what actually needs it.
4. **Running your own private git forge** — the parts of this project that
   currently assume "a forge exists, configured via environment variables"
   becoming a guided setup of that forge itself.
5. **Bridging multiple AI harnesses together** — letting different coding
   agents hand work to each other with a shared, auditable authority model,
   rather than each operating in isolation.

Each of these is a real, working pattern in the private system this project
was extracted from. None of it has been generalised, ported, or tested
outside that one machine yet. Until a chapter appears above the line in
Chapter 1, treat it as intent, not delivery.
