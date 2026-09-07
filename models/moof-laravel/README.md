# moof-laravel

A free, local, Laravel-specialised coding model. No subscription, no API key,
no data leaving your machine.

## What this actually is

**A curated system-prompt and parameter configuration of the open
[qwen2.5-coder:7b](https://ollama.com/library/qwen2.5-coder) model — not a
fine-tuned or retrained model.** The `Modelfile` in this directory is the
entire artifact: a `FROM` line, a couple of parameters, and a system prompt.
If you're expecting new weights trained on a Laravel corpus, that's not what
this is, and we're not going to imply otherwise. What it is, honestly: the
same open model, configured specifically for Laravel work, with real,
verified behavioural properties (below) that the base model doesn't have on
its own.

## Why this exists, not something bigger

Real fine-tuning needs a curated dataset, a training pipeline, GPU time, and
a genuine evaluation methodology to prove it's actually *better* — not just
different. That's a real, ongoing engineering commitment we haven't made
yet. This is the honest, shippable version: it costs nothing to build, costs
nothing to run, and every claim about it below is something we actually
tested, not something we assumed.

## Why it's Laravel-relevant right now, specifically

Laravel ships fast. Laravel 13 landed March 2026 with PHP attributes
replacing `$fillable`/`$hidden`/table-name properties, a first-party AI SDK,
a Reverb database driver, and JSON:API support. Any model - local or
frontier - trained before a release simply doesn't know about it. The one
thing we can actually build into a 7B local model is the discipline to say
so instead of guessing. That's what the system prompt is for.

## Verified behaviour, not claimed behaviour

Two real tests, run against this exact model, both included here because
one of them wasn't perfect:

**Asked to name the Laravel version it was assuming**, unprompted mid-answer:
> "As for the Laravel version, I don't know. You can check the version..."

**Asked directly about a real Laravel 13 feature it can't know about**
(the Reverb database driver):
> "I don't know. Laravel 13 and its features are not yet released, so I
> don't have information on the Reverb database driver. To find out about
> new features, you should check the official Laravel documentation..."

That second one is instructive, honestly: Laravel 13 *has* shipped - the
model's reasoning about *why* it doesn't know is wrong (it assumes "not
released" rather than "released after my training data"). But the actual
safety property held: it didn't invent a plausible-sounding fake API for a
real feature it has no knowledge of. That's the property that matters here,
and the one this whole system prompt exists to produce.

**One real limitation, also observed directly, also not hidden**: asked to
summarise a Form Request in one sentence, it called it "a type of
controller" - imprecise (it's a dedicated request/validation class, not a
controller). A 7B model under tight constraints will blur related concepts
sometimes. Expect that, verify anything that matters.

## Why this is broadly portable, not tied to one tool

Ollama exposes `moof-laravel` through its native API *and* a genuine
OpenAI-compatible endpoint (`/v1/chat/completions`, `/v1/models`) - verified
directly, not assumed. Anything that supports "custom OpenAI-compatible
endpoint" - which by now is most of the AI coding tooling ecosystem - can
use this with zero integration work. Point it at
`http://127.0.0.1:11434/v1`. It's also usable as a genuine MCP tool (see
`mcp/moof_ollama_server.py` in the Moof repo, with `MOOF_OLLAMA_LOCAL_ONLY=1`
if you want to hard-disable any paid fallback for a given session, not just
prefer local).

For a fully free, zero-subscription coding agent stack: pair this with
[OpenCode](https://opencode.ai) (open-source, terminal-based, no account
needed) - `ollama launch opencode --model moof-laravel` on Ollama v0.15+
auto-configures the whole thing. That's one real example, not the only
supported path.

**One real, practical fix already applied**: Ollama defaults every model to
a 4096-token context window regardless of what the base model actually
supports. Real agentic tool use (file edits, bash, multi-step reasoning)
needs more than that or tool calls silently break. This Modelfile sets
`num_ctx 16384`.

## Install

```bash
git clone git@github.com:deanhowe/warrior.git
cd warrior/models/moof-laravel
ollama create moof-laravel -f Modelfile
```

## What it's good for, and what it isn't

Good for: routine Laravel scaffolding, explaining established conventions,
quick lookups, working entirely offline. Not a replacement for a frontier
model on genuinely hard architectural decisions, ambiguous requirements, or
anything where being wrong is expensive - a 7B local model will be wrong
about specifics more often than a large cloud model, by design, and this
system prompt is built to make it say so rather than bluff.
