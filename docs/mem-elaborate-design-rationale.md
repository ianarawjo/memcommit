# `mem elaborate` design rationale

## Purpose

Elaborate owns top-down proposal generation that must not be confused with
evidence-bound Distill:

```text
Goal  --Elaborate--> suggested Rules
Rules --Elaborate--> suggested FIT / BOUNDARY / CONTRAST Case propositions
```

All outputs are `[Suggested] [Unverified]`. A Goal is intent rather than
evidence, and generated Cases are not real-world observations. Each direction
must nevertheless return at least one candidate. Elaborate exists to make an
abstract or underspecified idea concrete enough to inspect and correct, so a
sparse input is not a valid reason to return an empty result. When no exact
number is requested, the provider need not pad to the configured maximum;
proposals beyond the required first one should add a distinct Rule hypothesis
or Case role. `--n N` (also `-n` and `--number`) deliberately changes that
contract: the provider must return exactly `N` distinct proposals or the
complete operation fails.

## Shared application contract

`ElaborateRequest` accepts exactly one direction: one nonempty Goal or one or
more distinct nonempty Rules, plus an optional exact proposal number.
`ElaborateSemanticConfig` owns the safe directional maxima, text, rationale,
overview, and response limits. One complete request is
`WHOLE_FRAME_ONLY`; hidden batching could duplicate, omit, or distort the
requested proposal set. Input normalization occurs before prepared lookup; on
an exact prepared miss, the one-turn budget is validated before provider
construction.

Provider output uses a strict direction-specific schema. Goal input returns
one to four Rules by default. Rule input returns one to three Cases by default,
while `--number` fixes both JSON Schema bounds to the same requested value.
The supported exact range is therefore 1–4 for Goal-to-Rules and 1–3 for
Rules-to-Cases; the directional bounds continue to prevent an unbounded
one-turn request. The provider instruction, decoder, typed analysis validator,
prepared-result check, and atomic publication count all share this exact
request value. A count mismatch publishes nothing.

Every Case is linked to one source Rule index and classified as `FIT`,
`BOUNDARY`, or `CONTRAST`. Structural domain validation and active-config
validation are separate so an injected configuration is applied consistently
to live and prepared output.

The nonempty-output invariant is enforced independently by the Provider
instruction, JSON Schema `minItems`, strict decoder, and typed analysis. This
redundancy is intentional: a Provider or prepared lookup cannot turn an empty
array into a successful Elaborate result. The Provider contract version was
advanced when this invariant replaced the earlier zero-proposal behavior.
Provider contract version 4 additionally distinguishes an exact-number
request from the default bounded range so an older prepared result cannot
silently satisfy a different generation instruction.

An injectable exact prepared lookup may avoid provider construction only when
the normalized direction, complete input tuple, and exact-number request match.
There is no persisted
Elaborate cache artifact yet and no subset/projection reuse claim.

## Standalone Add and endpoint contract

Standalone Elaborate is a semantic Add. It generates a complete proposal set
and appends every generated proposition to one existing ordinary Context in a
single checkpoint; there is no `--apply` gate. The two endpoint options fill
from one Current snapshot:

| Invocation | Source | Target |
| --- | --- | --- |
| `mem elaborate` | Current | Current |
| `mem elaborate --to B` | Current | `B` |
| `mem elaborate --from A` | `A` | Current |
| `mem elaborate --from A --to B` | `A` | `B` |

With no inline input, directly owned ordinary Source Memories are interpreted
as Rules by default and Elaborate generates Cases. `--as goal` instead requires
exactly one direct Memory and generates Rules. This role belongs to the
invocation, not to the Context name: `goals`, `rules`, and other naming
conventions carry no hidden semantics. Inline `--goal` or repeatable `--rule`
remains available and uses Current or `--to` as its existing Target.
`--n`/`-n`/`--number` has the same exact meaning for inline input, Context
input, and both Ground directions.

Source and Target may be the same Context. The command freezes their common
pre-image before provider construction, so a provider turn cannot consume the
Memories that it generates. A later invocation naturally sees earlier output;
the operation does not maintain a hidden exclusion set across runs. Separate
Source bindings and the Target digest remain locked through the atomic write.
If either exact input changes, no generated Memory is published.

`mem impact elaborate` runs the same preparation path and displays the exact
would-add set while leaving both endpoints unchanged. Generated propositions
remain explicitly `SUGGESTED` and `UNVERIFIED` after Add; durable storage is
not evidence acceptance.

### Compact Rule rows preserve complete content

Goal-to-Rules catalogs use `[N] CONTENT — SUGGESTED · UNVERIFIED`. The status
suffix stays adjacent to every proposal, while its rationale remains available
in the Rule detail instead of consuming a second default catalog row. This
compact form applies only to Rule catalogs; Rules-to-Cases retains its distinct
role, expected-result, and Source-Rule fields.

The renderer folds stored whitespace into one logical row but never truncates
or paraphrases Rule content. A terminal may visually wrap a long row at its
viewport edge, yet the complete Rule remains present in display projection,
copy output, typed analysis, and any later Add. An ellipsis would be unsafe
here because the omitted tail may carry the condition that distinguishes an
unverified suggestion from a broader claim. Focused and whole-proposal copy
retain the full rationale even though the default catalog keeps it in detail.

For Goal-to-Rules, `PROPOSED RULES` is also the single default report location
for generated Memories. The read-only Impact route hides the generic
`IMPACT`/`[ADD]` effect ledger and Results block because they merely restate
that Rule catalog; rationale remains available in detail and copy, and exact
endpoint immutability remains visible in the Context-location header and
close-time digest verification. Rules-to-Cases keeps its separate proposal and
Impact projections because the compact Rule-only catalog contract does not
apply to Case role, expected-result, and Source-Rule fields.

## Ground route

Ground CLI accepts one exact saved Ground and either `--from-goal` or
`--from-rules`, plus the same optional exact `--number`. It calls the same
`run_elaborate` application function. The
Ground adapter freezes and revalidates the exact Ground UID, revision, and
record digest before and after the provider call. Active Ground Rules are
`PROPOSED` or `ACCEPTED` Rules; rejected/deferred material is not silently
reused. Ground Elaborate remains proposal-only until its non-Context workspace
records can participate in the same exact source-lock publication boundary.

No Elaborate route promotes or accepts a Ground Rule or Case automatically.

## Interfaces

The standalone Context route is plain, line-oriented output by default even in
a TTY. The explicit semantic TUI Viewer and plain CLI project the same typed result. The Viewer
uses shared neutral report chrome and deterministic focused/whole-document
`y`/`Y` copy. The public Python client exposes the same two directions plus
exact Ground projections. Versioned agent and MCP tools expose all four input
forms and the same optional exact number, and return
`verification: UNVERIFIED` and `effect: NONE`; this first Add
slice does not silently broaden those callable adapters into mutations.

Elaborate currently opens directly on its result Viewer rather than providing
an input-composer TUI. That is intentional for this slice: CLI, Python, or
agent input is validated before provider construction, while a future composer
can remain a presentation adapter over the same request.

## Remaining limits

- no durable proposal/review session;
- no automatic Ground promotion or Ground-source Add;
- no persisted hidden-prewarm artifact;
- no interactive input composer; and
- no claim that generated or stored Case propositions are evidence.
