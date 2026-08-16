---
name: warrior-registry
description: Turn a self-hosted forge's package registry from a checkbox feature into something that actually intercepts real installs — what to harvest, what to automate, and the specific gotchas that will otherwise cost hours. Use during bootstrap Provision, or whenever a developer asks why their private registry isn't actually being used.
---

# Warrior registry

A forge with "package registry: yes" on its feature list is not the same
thing as a package manager that actually stops hitting the internet for
things it already has. Getting from one to the other is mechanical, but
every step has a real, non-obvious failure mode. This is what to actually do,
and why each gotcha below is real rather than theoretical — every one of them
was hit, diagnosed from the forge's own source rather than guessed at, and
fixed, on the machine this was extracted from.

## The shape of the problem

A package manager (Composer, npm, pip, cargo, ...) resolves dependencies
from a *list* of sources, in order. Self-hosting a registry only helps if
it's genuinely in that list, genuinely gets checked, and genuinely doesn't
break the case where it doesn't have what's needed. Miss any one of those
and you get something that looks configured but changes nothing — every
package still comes off the public internet, and nobody notices until they
check.

Don't start by trying to intercept live installs. Start by populating the
registry with what's **already installed and already working** on the
machine — real, already-vetted content, zero new network activity, zero
risk to any project. Only after that's proven do you wire up interception
going forward.

## Step 1 — harvest what's already there

For every ecosystem in use, walk the already-installed dependency trees
(`vendor/<name>` for Composer, `node_modules/<name>` for npm, and so on),
cross-reference against the lockfile for the exact resolved version, and
publish each one built from that real, on-disk, already-running content —
not re-downloaded from anywhere.

This is safe because it's **read-only on every source project** — no
`install`, no `update`, no lifecycle script ever runs against projects you
don't control the state of. Skip anything whose lockfile doesn't have a
matching installed copy on disk; that's a "would need a real install to get"
case, not a harvest case, and running that live against a project nobody's
touched in years is a real risk, not a hypothetical one.

## Step 2 — the ecosystem-specific gotchas

These are not edge cases. Every one of them fires on the very first attempt
and produces an error message that does not obviously point at the real
cause.

**Composer, Content-Type.** `curl --data-binary` (and several HTTP client
defaults) send `Content-Type: application/x-www-form-urlencoded` unless told
otherwise. Gitea's composer upload handler reads the request body as form
data first when that header is present, which drains the stream before the
package-upload code ever sees it — the failure surfaces as a generic `500
EOF`, nothing about form encoding. Set `Content-Type: application/octet-stream`
explicitly on every publish.

**Composer, canonical repositories.** Adding a custom repository to
Composer's config makes it **canonical by default** — meaning if it has *any*
version of a package, Composer refuses to consider the public registry's
*other* versions for that same name, even ones that actually satisfy the
current requirement. This is backwards from "check locally first, fall
through if not found" — it's "if found at all, block everything else,"
which silently breaks every future install of anything newer than whatever
got harvested. Set `"canonical": false` on the repository entry, or every
version bump becomes an unresolvable-conflict error with no obvious cause.

**npm, the publish envelope.** Unlike a raw file PUT, npm's registry
protocol expects a full JSON envelope — `_id`, `name`, `dist-tags`,
`versions` (keyed by version, each value shaped like a `package.json` plus a
`dist` object), and `_attachments` (keyed by filename, holding
`content_type` + base64 `data` + `length`). Get the shape from the forge's
own source rather than guessing from memory — small protocol details
(exact field names, nesting) genuinely vary between implementations.

**npm, integrity validation.** A self-hosted npm registry may verify
`dist.integrity` for real: split the SRI string (`"sha512-<base64>"`),
decode the hash, and compare it against the *actual* hash of the uploaded
attachment bytes — reject on mismatch. The legacy `shasum` field alone is
not sufficient; compute and include a real SRI `sha512-` hash of the exact
tarball bytes being uploaded, or every publish fails with a bare "integrity"
error that doesn't say what's missing.

**npm, nested dependency names.** A real lockfile's package paths are not
always `node_modules/<name>` — version conflicts produce nested paths like
`node_modules/chalk/node_modules/supports-color`. Naively stripping only the
first `node_modules/` prefix treats the whole nested path as the package
name, which silently 404s on publish (it doesn't match any valid route,
scoped or not) with no indication why. Take the segment after the *last*
`node_modules/` occurrence, not the first.

**npm, the repository field.** Some registries' Go-typed metadata expects
`repository` as an object (`{"type", "url"}`); a large fraction of real
`package.json` files in the wild use the shorthand string form instead
(`"repository": "github:owner/repo"`). Passing that string straight through
fails server-side JSON unmarshalling with a generic 500 that gives no hint
it's this one field. Either normalise the shorthand into the expected shape
or drop the field — it isn't essential to the registry actually working.
Don't stop at this one field: `bin` (string shorthand for "one executable
named after the package" vs. the typed `{name: path}` object) and
`keywords` (bare string vs. array) fail the exact same way, and more will
surface the wider the real-world sample gets. Coerce or drop defensively for
the whole class of "package.json allows loose shorthand, the registry's
typed struct doesn't" rather than patching one field at a time as each one
is discovered failing.

**npm, no upstream proxy.** This is the one that doesn't have a clean
one-line fix, so don't present it as solved when it isn't. A self-hosted
registry with no proxy-to-upstream capability will 404 outright for
anything not already published there — and unlike Composer, npm's own
client has no "try this registry, fall through to the public one"
mechanism; its `registry` config is one value, full replacement. Two honest
paths, pick one deliberately and say which:
  - stand up a real caching proxy in front of both registries (npm has a
    long history of exactly this shape of tool), or
  - scope the self-hosted registry to first-party/scoped packages only, and
    leave the public registry as the default for everything else.
Do not silently point the global registry setting at the local forge and
call it done — that breaks every package not yet harvested, the moment a
developer needs something new.

## Step 3 — going forward, not just once

A one-time harvest is a snapshot, not a solution — it goes stale the moment
anyone installs something new, and "install it once manually so it's
harvestable" defeats the entire point. The real fix is a package-manager
plugin that publishes automatically as a side effect of normal use, so the
registry grows from what's actually needed, staying current with zero extra
developer action. Composer has a genuine plugin API for exactly this
(subscribe to the post-install/post-update package events); confirm whether
the ecosystem in front of you has an equivalent before assuming a harvest
script is the whole answer.

Register such a plugin **globally**, not per-project — the point is that a
project's own manifest never needs to know the local forge exists at all,
so it stays identical and portable when it leaves the machine.

## Step 4 — if you want automatic, HTTPS is probably required

Package manager clients frequently refuse to talk to a plain-HTTP custom
registry by default (Composer's `secure-http`; others have equivalents).
Getting real, working trust for a self-signed local certificate is its own
multi-layer problem — and the layer that actually matters is easy to get
wrong:

**Check what TLS backend the package manager's own runtime actually uses,
not the system's default tool.** A locally-built or vendor-bundled PHP/npm
install frequently links its own OpenSSL and reads a *file-based* CA bundle
— completely independent of the OS keychain, even on the same machine where
the OS's own command-line tools use the native keychain-backed trust store.
Trusting a certificate authority in the OS keychain can look like it should
work, get confirmed by the OS's own tools, survive a reboot, and still do
nothing for the package manager, because it was never reading that trust
store in the first place. Ask the runtime directly which CA file or
directory it actually consults (most languages expose this — don't assume
from the platform) before spending time on OS-level trust configuration.

## Where this fits organisationally

Everything above answers "does the registry work." It does not answer
"whose namespace do published packages live under" — that's a separate,
larger decision (personal vs. organisation-scoped, tiered by trust level,
grouped by purpose) that this skill deliberately doesn't make for you.
Populate the registry first, prove the mechanism works end to end, *then*
decide the namespace/ownership model — doing it in the other order means
re-publishing everything once the real structure is chosen.
