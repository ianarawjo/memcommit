# Operation Example Contract Design Rationale

## Problem

An operation can document limits, schemas, and invariants while still leaving
the intended behavior hard to reconstruct. A synthetic boundary string can
prove that a character counter stops, for example, without showing what a
useful bounded explanation looks like. The same gap is more consequential at
a provider boundary: a strict decoder may define the legal shape, yet the
model receives no concrete demonstration of the intended input-to-output
relationship.

Examples are therefore part of the operation contract. A prose statement such
as "examples exist" is insufficient because it does not identify the covered
input, output, exposure boundary, version, or executable oracle.

## Three non-interchangeable example classes

| Class | Exposure | Purpose | May serve as evaluation evidence? |
| --- | --- | --- | --- |
| Application contract example | `HOST_ONLY` | Show and execute one accepted application input → typed result or human projection | It may be a regression oracle, but not unseen semantic-evaluation evidence |
| Provider contract example | `PROVIDER_VISIBLE` | Demonstrate one real prompt input → valid response for a particular prompt/schema/decoder version | No; the provider has already seen it |
| Evaluation example | `CALIBRATION` or `HOLDOUT_NEVER` | Measure or tune semantic behavior without pretending prompt demonstrations are independent evidence | Only according to its declared evaluation role; `HOLDOUT_NEVER` must never enter a prompt |

A strict provider decoder additionally keeps at least one `HOST_ONLY` malformed
response example. It proves rejection behavior, not desired model behavior,
and therefore cannot replace the valid provider-visible pair.

The content behind these roles must remain distinct. Renaming the same fixture
or copying its text under another ID does not turn a prompt example into a
holdout. This separation prevents prompt/evaluation leakage and makes token
cost visible: `PROVIDER_VISIBLE` examples count against the same aggregate
prompt budget as instructions, Context, and other trace material.

## Minimum coverage contract

Each operation owns stable example IDs under the following rules:

1. Every accepted application input form appears in at least one `HOST_ONLY`
   example.
2. Every typed result or human-visible output variant appears in at least one
   `HOST_ONLY` example. One coherent example may satisfy both an input-form and
   an output-variant obligation.
3. Every concrete provider prompt/schema/decoder version has at least one
   minimal, semantically realistic `PROVIDER_VISIBLE` input/output pair.
4. Every strict provider decoder has at least one separate malformed-output
   rejection example executed through the production decoder.
5. An interaction between input forms or output variants needs an additional
   pairwise example only when the operation's behavior depends on that
   combination. The contract does not require a wasteful full Cartesian
   product.
6. Repeated filler, lorem ipsum, and arbitrary character runs do not qualify
   when the behavior under test is semantic coherence, explanation, or
   provenance. A size-only transport boundary may use generated data, but it
   must be paired with a coherent semantic case when both properties matter.
7. A prompt, schema, decoder, accepted input union, or output union change must
   update the bound examples and their oracles in the same change. A wording
   edit that does not alter the contract may retain the version.

"At least one" is the floor, not a claim that one happy path proves the whole
operation. Authority failures, stale revisions, no-op, oversized frames, and
other materially different safety boundaries remain separate test and matrix
obligations.

## Case-to-rule derivation method

Examples become a semantic contract through controlled comparison, not by
collecting several plausible outputs and summarizing their wording. Use this
sequence when an operation's desired model behavior is still being established:

1. **Hold the semantic frame constant.** Freeze one small Source, authority
   frame, and presentation boundary. Vary one request property at a time so a
   changed output can be attributed to behavior rather than different evidence.
2. **Name independent axes before multiplying cases.** Examples include input
   role, evidence coverage, authority, requested effect, output kind, and
   provenance obligation. Start with the meaningful values for the operation,
   not a full Cartesian product.
3. **Author the smallest acceptable output.** Write the concise human result
   first. Label each clause by semantic role and identify its evidence,
   authority, effect, or lack thereof. Remove clauses that have no owned role.
4. **Construct the nearest failure or boundary.** Change one axis: remove one
   support, add one unsupported request part, revoke one capability, make one
   item stale, or turn an explicit input into an ambiguous one. The output
   difference reveals the actual invariant.
5. **Generalize the obligation, not the example vocabulary.** A Korean greeting
   can establish that an input act must be preserved; it does not establish a
   Korean-specific branch. A majority pattern is not universal, and generated
   prose cannot supply evidence absent from the frozen frame.
6. **Declare exposure before reuse.** Register the case as `HOST_ONLY`,
   `PROVIDER_VISIBLE`, `CALIBRATION`, or `HOLDOUT_NEVER`. Moving a case into a
   prompt changes its role and prevents later claims that it was independent
   evaluation evidence.
7. **Promote the rule through every enforcing boundary.** Update prompt,
   schema, decoder, typed application result, interface projections, fixtures,
   and tests together when the rule changes observable behavior. Prompt prose
   alone is not a contract when the host still accepts an incompatible result.

Use a new pairwise case only when an interaction changes the result. Use a
multi-axis scenario later as an integration check. This keeps the calibration
set small enough to review while preventing one happy path from standing in
for a semantic method.

`query-case-derived-answer-design-rationale.md` is the first focused
application of this method to input act, corpus coverage, claim role, and
citation obligation in ordinary Query.

## Focused operation matrix shape

The shared consistency matrix owns only `EXAMPLE-01`. Each focused operation
matrix records the exact rows it can prove:

| Column | Meaning |
| --- | --- |
| Example ID | Stable operation-scoped identifier, such as `rationale.provenance.latest` |
| Boundary | Exact application or provider contract crossed by the example |
| Input form | Accepted request variant or frozen provider frame represented |
| Output variant | Typed result, human projection, valid provider response, or decoder rejection |
| Exposure | `HOST_ONLY`, `PROVIDER_VISIBLE`, `CALIBRATION`, or `HOLDOUT_NEVER` |
| Version binding | Prompt/schema/decoder version or `N/A` for a provider-free application projection |
| Artifact | Fixture, capture scenario, or example source of truth |
| Oracle | Production decoder, test, capture assertion, or evaluation harness that checks it |

Rows belong below a focused matrix's existing responsibility and boundary
tables. Adding example columns to every responsibility row would mix two
different questions: who owns a behavior, and which concrete case proves it.
One example may cover several responsibility rows, while one responsibility
may require several examples.

The operation route classification remains solely in
`operation-route-classification.json`. Example coverage must not introduce a
second `CLOSED`/`MIXED`/`LEGACY` status table or imply route completeness from
the presence of one example.

## Inventory and enforcement

Provider inventory is by concrete prompt/schema/decoder contract, not by raw
`provider.complete()` call site. Several call sites may share one contract;
one call site may dispatch distinct versioned contracts. Counting calls would
both duplicate examples and miss semantic variants.

The staged rollout is:

1. Use Rationale's natural-provenance family as the first complete
   `EXAMPLE-01` operation set: the exact `Um...` parent/split/Undo/Redo/Remove
   case, direct Add/Remove/Undo, Atomize parent-to-two-results,
   Distill-then-Edit, branch inheritance, and 15-event material-phase
   compression are `PROVIDER_VISIBLE`; the direct case also binds the
   41-word-overflow → compact-repair prompt variant. Grant-hidden, malformed
   output, and a second over-bound repair response remain `HOST_ONLY`.
2. Add the focused example table whenever an operation matrix is reviewed or
   materially changed. Missing rows remain explicit work rather than a
   fabricated complete state.
3. Inventory each `SEM-01` provider contract and separate existing fixtures
   into provider-visible, decoder-rejection, calibration, and holdout roles.
4. Once the row schema stabilizes, move IDs and bindings to one machine-readable
   registry and generate the coverage view. The verifier should reject missing
   input/output/provider obligations, duplicate IDs, unknown exposure classes,
   prompt/holdout reuse, and artifacts without executable oracles.

The first pass deliberately does not insert an example into every provider
prompt. Doing that before the inventory would spend context unpredictably,
risk exposing holdouts, and make it unclear which provider version each
example constrains. `EXAMPLE-01` first makes the obligation and exposure
boundary reviewable; provider prompts then migrate contract by contract.

## Intentional limits

- Examples specify representative behavior; they do not replace schemas,
  invariants, property tests, or adversarial evaluation.
- Provider-visible examples must stay small enough to fit the operation's
  declared prompt budget. Crossing a budget never authorizes silent truncation
  of an example or frozen input.
- A provider-free operation records provider roles as inapplicable in its
  focused rationale rather than fabricating LLM examples. Rationale is no
  longer in that class: its exact natural-provenance cases are consumed
  calibration and must never be reported as holdout evidence.
- The matrix does not prescribe English-only content. An operation should use
  the language and structure needed to demonstrate its actual contract.
