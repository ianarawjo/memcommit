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
sparse input is not a valid reason to return an empty result. The provider need
not pad to the configured maximum; proposals beyond the required first one
should add a distinct Rule hypothesis or Case role.

## Shared application contract

`ElaborateRequest` accepts exactly one direction: one nonempty Goal or one or
more distinct nonempty Rules. `ElaborateSemanticConfig` owns proposal counts,
text, rationale, overview, and response limits. One complete request is
`WHOLE_FRAME_ONLY`; hidden batching could duplicate, omit, or distort the
requested proposal set. Input normalization occurs before prepared lookup; on
an exact prepared miss, the one-turn budget is validated before provider
construction.

Provider output uses a strict direction-specific schema. Goal input returns
one to four Rules by default. Rule input returns one to three Cases by default,
each linked to one source Rule index and classified as `FIT`,
`BOUNDARY`, or `CONTRAST`. Structural domain validation and active-config
validation are separate so an injected configuration is applied consistently
to live and prepared output.

The nonempty-output invariant is enforced independently by the Provider
instruction, JSON Schema `minItems`, strict decoder, and typed analysis. This
redundancy is intentional: a Provider or prepared lookup cannot turn an empty
array into a successful Elaborate result. The Provider contract version was
advanced when this invariant replaced the earlier zero-proposal behavior.

An injectable exact prepared lookup may avoid provider construction only when
the normalized direction and complete input tuple match. There is no persisted
Elaborate cache artifact yet and no subset/projection reuse claim.

## Standalone and Ground routes

Standalone CLI accepts `--goal` or repeatable `--rule`. Ground CLI accepts one
exact saved Ground and either `--from-goal` or `--from-rules`. Both call the
same `run_elaborate` application function. The Ground adapter freezes and
revalidates the exact Ground UID, revision, and record digest before and after
the provider call. Active Ground Rules are `PROPOSED` or `ACCEPTED` Rules;
rejected/deferred material is not silently reused.

No Elaborate route changes a Ground, Context, Rule, or Case. Promotion or
acceptance must remain a separate reviewed operation.

## Interfaces

Plain CLI and the semantic TUI Viewer project the same typed result. The Viewer
uses shared neutral report chrome and deterministic focused/whole-document
`y`/`Y` copy. The public Python client exposes the same two directions plus
exact Ground projections. Versioned agent and MCP tools expose all four input
forms and return `verification: UNVERIFIED` and `effect: NONE`.

Elaborate currently opens directly on its result Viewer rather than providing
an input-composer TUI. That is intentional for this slice: CLI, Python, or
agent input is validated before provider construction, while a future composer
can remain a presentation adapter over the same request.

## Remaining limits

- no durable proposal/review session;
- no Apply or automatic Ground promotion;
- no persisted hidden-prewarm artifact;
- no interactive input composer; and
- no claim that generated Case propositions are evidence.
