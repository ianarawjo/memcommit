# Semantic provider design rationale

## Decision

Semantic inference is selected through one provider-neutral completion
contract. `codex_chatgpt`, loopback `ollama`, and `openrouter` are allowlisted
adapters; model names, endpoints, or persisted Context values are never treated
as executable commands. Codex remains the default until a person explicitly
selects another provider.

```text
semantic operation
  → freeze configured provider/model once
  → construct the existing bounded prompt and JSON Schema
  → make exactly one provider completion
  → validate the returned text with the operation's existing local parser
  → preserve the operation's existing review and mutation boundary
```

The first local target is the installed Ollama model
`qwen3.6:35b-a3b`. Qwen is not encoded as a special semantic backend: it is
one model selected through the Ollama adapter. The same operation contracts can
therefore be evaluated with a different local model or a fixed OpenRouter model
without changing command semantics.

## Motivation

Recent commands already share the structural completion interface
`complete(prompt, operation, output_schema)`, but command modules historically
imported a Codex-named connector. Earlier `forget`, the now-retired Integrate
pipeline, and developer evaluation paths separately used a small
Ollama/OpenAI-compatible client. This
split made local configuration irrelevant to the newer Ground, Find, Compare,
Atomize, Meld, Translate, Review, Impact, and Update paths and prevented an
honest cross-model evaluation.

Provider independence is also a research requirement. A saved or published
semantic result should eventually identify the provider, exact model or model
digest, runtime, generation settings, ruleset, prompt/schema version, and any
upstream route that produced it. A mutable model tag or a router-level model
name alone is not a reproducible identity.

## Provider and model are different axes

The provider owns transport, authentication, routing, and structured-output
mechanics. The model supplies the semantic completion.

| Provider | Model selection | Execution boundary |
| --- | --- | --- |
| `codex_chatgpt` | Codex-managed selection, or an explicit model and reasoning effort | isolated ephemeral Codex process authenticated with ChatGPT |
| `ollama` | exact installed local model tag and catalog digest | tool-less loopback HTTP service |
| `openrouter` | exact OpenRouter model slug | authenticated remote API with explicit routing policy |

OpenRouter is not treated as merely another model. Its default routing can
choose among upstream providers and fallbacks, so memcommit disables fallback,
requires requested parameters for structured calls, denies data-collecting
routes, and can require zero-data-retention routing. The actual upstream model
and provider, when returned, belong in completion provenance.

### Codex Luna-low option

`gpt-5.6-luna` is a model selection inside the `codex_chatgpt` provider, not a
fourth provider. Treating it as another provider ID would mix transport and
model policy and make later model additions multiply adapter names. The CLI
therefore exposes `--preset luna-low` as a convenience option that expands to
the exact model `gpt-5.6-luna` and Codex `model_reasoning_effort = "low"`.
The equivalent `--model` and `--reasoning` options remain available for an
explicit evaluation matrix.

The preset is persisted as all three pieces—provider, model, and reasoning—so
`status`, `probe`, and later provenance can distinguish it from Codex's managed
selection. A bare `mem provider use codex_chatgpt` intentionally clears the
Codex-specific model, reasoning, and preset values and restores the historical
managed behavior. This reset is asymmetric with retained Ollama/OpenRouter
model values because the bare Codex command was already the documented escape
hatch back to the original behavior.

## Structured-output contract

Operation schemas stay authoritative and operation parsers remain the final
local acceptance boundary. A provider accepting a `format` or
`response_format` parameter is not evidence that a particular model follows
the schema.

An initial synthetic run against local `qwen3.6:35b-a3b` demonstrated this
distinction: passing the schema only as Ollama's `format` produced valid JSON
that violated the required fields and enum. Supplying the same trusted schema
in a system instruction as well as `format` produced the exact required
object. The Ollama and OpenRouter adapters therefore mirror the host schema in
a trusted system message and still return the response to the existing strict
parser.

Malformed, truncated, empty, duplicated-envelope, oversized, unknown-ID, or
out-of-scope output fails closed. The adapter does not silently remove schema
constraints, make a hidden repair completion, or fall back to Codex or another
model. Those behaviors would violate both the one-provider-call contract and
the interpretability of a model comparison.

An isolated subscription-backed synthetic probe also confirmed that the
installed Codex CLI accepts `gpt-5.6-luna` with reasoning effort `low` and
returns the same exact strict JSON probe object. This verifies transport and
schema conformance only; it is not a claim that Luna and the earlier Codex
selection have equal semantic quality across memcommit operations.

## Configuration and process snapshot

`mem provider use` records an explicit provider and optional model. `status`
is local and provider-free. `probe` makes one synthetic strict-schema call and
does not read a Context or save a semantic artifact.

The provider factory reads configuration once when a command requests its
provider. A Ground or other interactive process keeps that provider instance;
it does not observe later edits to global config during the process. There is
no automatic fallback. Codex remains the default when no provider is selected,
preserving the earlier command behavior.

The timeout printed by `mem provider status` is also the transport timeout
passed to every configured adapter, including the temporary Codex process.
Leaving Codex on its adapter's historical 120-second constructor default while
status reported 600 seconds was rejected: it made aggregate failures look like
model latency and made the displayed configuration false. Operation-local
overrides remain possible only where a documented aggregate contract requires
one; ordinary Sever uses the configured value and reports the effective limit
and frozen frame counts when a provider call fails.

During rollout the historical command connector name remains a compatibility
seam because tests and downstream experiments patch it. Its implementation now
performs provider selection. Query-only routing bypasses this seam and uses its
persisted allowlisted provider instead.

## Local Ollama boundary

The Ollama base URL is restricted to a plain loopback HTTP origin. This is a
privacy boundary as well as an SSRF boundary: selecting local execution must
not turn an arbitrary configured URL into silent Memory export. Connection
probes obtain the Ollama version and require the exact model tag to exist
before semantic input is constructed or query-only source content is opened.

The adapter uses non-streaming generation, temperature zero, and an explicit
context allocation and output budget. Thinking defaults to capability-based
selection: it is enabled when the exact Ollama model advertises support and
disabled otherwise, with an explicit command override. In the initial Qwen
smoke test, non-thinking generation matched the JSON grammar but incorrectly
returned a clean Memory as an ambiguity finding; thinking generation omitted
that clean item and passed the same local semantic validator. This observation
motivates the default but is not a general quality claim for every operation.

## Query-only boundary

A persisted `QueryContextRef.provider` remains authoritative. Global semantic
selection must never reroute a recorded `codex_chatgpt` source to Ollama or
OpenRouter. Every supported query adapter authenticates or probes its service
before the concealed source loader runs.

The newer authority-grant registry currently discards the provider named by
the study bundle and its command path still uses the known Codex provider.
Migrating that path requires a versioned grant-schema change that preserves the
provider through validation and freshness binding. It is intentionally not
reinterpreted from global config during the first provider rollout.

## Rollout and evaluation

1. Preserve Codex as the default and add provider-neutral configuration,
   adapters, connection probes, and transport tests.
2. Run local Qwen through a read-only strict-schema operation such as
   `find-ambiguities`, then through representative Ground dialogue schemas.
3. Evaluate aggregate Compare, Atomize, Translate, and Meld inputs at visible
   context and output limits.
4. Evaluate mutation-producing Update and Review paths without weakening their
   existing exact-review, CAS, provenance, or approval boundaries.
5. Version the authority-grant provider field before enabling non-Codex
   provider selection for those query-only views.
6. Add provider/model provenance envelopes to durable analyses and findings
   before treating cross-provider results as reproducible study data.

Evaluation must separately measure transport/schema conformance, local parser
acceptance, semantic precision/recall, stability across repeated runs,
Korean/English behavior, prompt-injection resistance, long-context failure,
latency, and memory use. A syntactically valid local completion is not evidence
of semantic equivalence with the prior Codex result.

## Intentional limitations

- The first rollout does not claim that Qwen matches Codex quality for every
  operation; it makes the comparison possible and fail-closed.
- Context-window preflight remains conservative and model-specific evaluation
  is required before increasing aggregate input limits.
- The earlier chat-shaped `forget` implementation and retired Integrate
  evaluation pipeline still use the compatibility Ollama model setting.
  Selecting Ollama synchronizes that model name, but live Forget would need to
  move onto the shared completion/result contract before it supports
  OpenRouter or Codex. Integrate remains frozen for research comparison rather
  than returning as a public command.
- Provider call metadata is available from the adapters, but existing durable
  analysis schemas do not yet persist it. That schema migration is required
  for reproducible saved results.
