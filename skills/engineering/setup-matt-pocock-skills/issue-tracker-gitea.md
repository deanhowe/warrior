# Issue tracker: Gitea (self-hosted)

Issues and specs for this repo live as issues on a self-hosted Gitea (or
Forgejo — the API is identical) instance. Unlike GitHub or GitLab, there is
no universally-installed CLI for Gitea, so operations below use its REST
API directly via `curl`. If a Gitea CLI is available in this environment
and behaves like `tea`, prefer it and adapt the commands below to match its
flags — but don't assume it exists; verify with `command -v tea` first.

## Setup

Two things this template needs from the person or project configuring it:

- **`$GITEA_HOST`** — the instance's base URL, e.g. `http://git.example.local`
- **`$GITEA_TOKEN`** — an API token with issue read/write scope. Store it in
  the OS keychain or a secrets manager, never in a tracked file. Read it
  once per shell session into an environment variable; never print it.

Infer `<owner>/<repo>` from `git remote -v` — Gitea remotes follow the same
`ssh://git@<host>:<port>/<owner>/<repo>.git` shape as GitHub/GitLab.

Base URL for API calls: `$GITEA_HOST/api/v1/repos/<owner>/<repo>`

## Conventions

- **Create an issue**:
  `curl -sS -H "Authorization: token $GITEA_TOKEN" -H "Content-Type: application/json" -d '{"title":"...","body":"..."}' $BASE/issues`
- **Read an issue**: `curl -sS -H "Authorization: token $GITEA_TOKEN" $BASE/issues/<number>`.
  Comments: `$BASE/issues/<number>/comments`.
- **List issues**: `curl -sS -H "Authorization: token $GITEA_TOKEN" "$BASE/issues?state=open"`
- **Comment on an issue**:
  `curl -sS -H "Authorization: token $GITEA_TOKEN" -d '{"body":"..."}' $BASE/issues/<number>/comments`
- **Apply / remove labels**: Gitea labels are referenced by **numeric id**,
  not name — list them first via `$BASE/labels`, then:
  `curl -sS -H "Authorization: token $GITEA_TOKEN" -X POST -d '{"labels":[<id>]}' $BASE/issues/<number>/labels`
- **Close**:
  `curl -sS -H "Authorization: token $GITEA_TOKEN" -X PATCH -d '{"state":"closed"}' $BASE/issues/<number>`
- **Pull requests**: Gitea calls them "pull requests" like GitHub. Same
  `/pulls` resource shape as `/issues`, with `/merge` to merge.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats
external PRs as feature requests; `/triage` reads this flag. On a private,
single-owner instance — the common case for a self-hosted Gitea — this is
almost always `no`.)_

When set to `yes`: `$BASE/pulls?state=open` to list, filter by author not
matching the repo owner, then the same comment/label/close operations as
issues but against `/pulls/<number>`.

## When a skill says "publish to the issue tracker"

Create a Gitea issue via the API above.

## When a skill says "fetch the relevant ticket"

`curl -sS -H "Authorization: token $GITEA_TOKEN" $BASE/issues/<number>` plus
`/comments`.

## Wayfinding operations

Gitea has no native sub-issue/dependency-graph equivalent to GitHub's or
GitLab's premium tier. Fall back to the same convention both of those use
when their native features are unavailable:

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes /
  Decisions-so-far / Fog body.
- **Child ticket**: an issue with `Part of #<map>` at the top of its body,
  labelled `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
  Once claimed, assign it to the driving dev.
- **Blocking**: a `Blocked by: #<n>, #<n>` line at the top of the child's
  body — there is no native link to fall back from here, this line IS the
  representation. A ticket is unblocked when every blocker referenced this
  way is closed.
- **Frontier query**: list the map's children (`$BASE/issues?state=open`,
  filtered to those referencing the map), drop any with an open blocker in
  its `Blocked by` line or an assignee; first in map order wins.
- **Claim**: `curl ... -X PATCH -d '{"assignees":["<username>"]}' $BASE/issues/<n>`
  — the session's first write.
- **Resolve**: comment the answer, close the issue, append a context
  pointer to the map's Decisions-so-far.
