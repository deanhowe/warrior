---
name: warrior-exchange
description: Coordinate several AI coding harnesses against one estate using a private forge as the exchange. Use when routing work between agents, verifying which model actually did the work, interpreting a task marked done, resuming sessions, or debugging why an agent's tools are missing.
---

# Warrior exchange

Several harnesses, one estate, no shared memory. The forge is how they talk.

Branches are the messages. Leases are the contracts. The queue records what was
claimed. **None of those three is evidence of what a model actually did** — that
is the part everyone gets wrong, and this skill is mostly about that.

## Branch as message

```
<agent>/<work-item-slug>
```

The agent's name is the namespace. One harness works its lease, commits, and
pushes only that branch to the shared remote. Another fetches it and reviews.
No agent writes to the canonical branch; no agent reviews its own work.

This gives you, for free: attribution without a convention nobody follows,
isolation without trust, and a review boundary that survives an agent losing
its session.

## Requested model is not responding model

Adapters fall back, silently, and then report success.

A real case: a session was requested as one vendor's large model at high
reasoning effort. The error that came back named a **different vendor's small
model**, which does not accept reasoning effort at all. The request and the
responder had diverged, and every downstream claim about capability, cost and
quality was consequently false.

So:

- store `requested_model` and `model` as **separate fields**, always;
- store the effort/parameters actually accepted, not the ones you sent;
- treat a mismatch as a first-class `incompatible` state to **preserve as
  evidence**, not an error to retry past;
- never describe a harness's capability from the profile name. Read what
  answered.

A harness that cannot tell you which model served a turn is a harness whose
results you cannot attribute.

## Capability negotiation, not assumption

Ask what a harness supports; do not infer it from another harness that looks
similar. Parameters that commonly fail: reasoning effort levels, tool trust
scoping, session resume, context compaction, image input, MCP transport.

Where a parameter may be unsupported, prefer the explicit neutral value over
omitting it. A profile that requests no effort level works against models that
accept effort and models that reject it; a profile that requests "medium"
fails half of them.

Probe with an operation that costs nothing — initialise a connection, list
capabilities, create a session — before spending a model turn. Then send one
deliberate prompt.

## A task marked done is not work completed

Distinguish three separate facts, and never let one stand for another:

| Fact | Evidence |
|---|---|
| the queue claimed a task | a claim token and lease in the queue |
| a harness session ran | a session id and turn count from the provider |
| the work is correct | the validation contract passed, observed |

A real case: tasks recorded `done` while their own result text read *"one or
more servers did not load correctly."* The runner treated "the process exited"
as "the objective was met". Both facts were true and stored; only the wrong one
was used to set the status.

Rules that follow:

- a completion needs **completion evidence** defined in advance — a marker
  string, a passing command, a specific artifact — not merely a finished
  process;
- a harness's own error text must gate the status, not sit beside it;
- preserve failed and incompatible records. They are the only proof you had a
  problem, and deleting them makes the same bug new again next month.

## Verification tasks are not build tasks

An agent that has completed twenty tasks of the form *"use no tools and reply
exactly OK"* has proven the transport works. It has proven **nothing** about
its ability to build software.

Climbing the ladder deliberately is correct, and it looks like this:

```
1. reply exactly <marker>, use no tools      transport
2. call exactly one read-only tool           tool plumbing
3. run exactly one read-only shell command   shell trust
4. attempt one mutation and be refused       the guard works
5. a small real change with a passing test   capability
```

Steps 1–4 are cheap and worth doing. Just never describe an agent that stopped
at step 4 as battle-tested. Say which rung it reached.

## Tooling is per-agent and does not hot-load

The trap that costs the most time, because nothing errors:

- **Tool/server configuration attaches to an agent profile, not to a machine or
  a project.** Two profiles in the same directory can have entirely different
  capabilities. An agent working inside a project can be missing that project's
  own tools while a sibling profile has them.
- **A running session's tool list is fixed at start.** Adding a server updates
  the configuration and the management CLI will confirm it — while the live
  session still cannot call it. Verify from inside the session by invoking the
  tool, not from outside by reading config.
- Therefore: before concluding a capability does not exist, enumerate the
  configuration of **every** profile, not just the one you are in.

An agent that does not know what it is holding will rebuild things that already
exist, and will sweep the filesystem for answers a purpose-built tool would
have returned in one call.

## Compaction is not completion

Context compaction, history replacement and session rotation are **context**
operations. They mean "checkpoint and continue", never "the objective is met".

Rotate on a threshold you chose in advance, record that a rotation happened,
and carry the work item forward explicitly. A summary is not a deliverable, and
a fresh session with no evidence of the prior one is a restart, not progress.

## Resuming does not create new work

Loading an existing session resumes a conversation. It does not create a new
work item, and it does not renew authority. Authority attaches to the lease and
the work item; a resumed session inherits exactly what its lease says, no more.

Where sessions are addressed as `profile@session-id`, treat that as
compatibility shorthand and normalise it into an explicit binding — harness,
profile, external session id, project root, model, parameters, status — before
building anything that depends on it.

## Automation enqueues; it never calls a model

A schedule or loop must not invoke a harness directly. It checks budget, time,
authority and existing leases, then **enqueues one ordinary bounded task run**.
The queue stays the single execution path.

Fail closed. If budget freshness cannot be established, nothing runs. And make
sure the freshness window is actually satisfiable: a cache valid for ninety
seconds, with nothing refreshing it, blocks every future run forever while
appearing to be a safety feature working correctly.

## Reading capacity honestly

Percentages from a provider's own display are easy to misread, and models do
misread them:

- `500/500` in a "used / total" column means **fully consumed**, not fully
  available. Confirm which way round the numbers run before acting on them.
- Scopes differ per provider: a rolling short window, a weekly allowance, a
  monthly plan, a bonus pool. They are not interchangeable.
- Label every displayed figure with its age. A stale number presented as live
  is worse than no number, because it will be trusted.
- One harness running out says nothing about the others. Check each.
