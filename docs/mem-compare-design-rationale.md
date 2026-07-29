# Targetless peer-Context comparison

## Status

The first bounded Compare slice is implemented as:

```text
mem compare --to PEER
mem compare --to PEER --refresh
```

The active Context is the display reference and `--to` names the compared
Context. Both sources have equal authority. `REFERENCE` controls layout and
navigation only; it is not a baseline and does not win a disagreement.

Compare performs one aggregate semantic call over the two complete bounded
direct-Memory frames. It saves an immutable `ComparisonAnalysis` containing:

- exact ordered source Context identities, names, digests, Memory order, and
  Memory snapshots;
- one overview;
- one exhaustive N:M primary relation ledger; and
- visible issues that may later become grounding turns.

It has no target Context, target proposal, conversational turn, readiness
state, acceptance action, checkpoint, or mutation authority.

## Why the analysis persists

One-shot interaction does not imply disposable analysis. Provider output is
not assumed to be deterministic, and a later Meld must be able to identify
the exact relations the person inspected. Reopening an unchanged ordered pair
therefore renders the saved analysis without another provider call.

The latest ordered slot is:

```text
~/.mem/comparison-analyses/
  <reference-context-uid>--<compared-context-uid>.json
```

Context names do not determine storage paths. If either source UID, name,
complete direct record digest, or order changes, ordinary `mem compare`
performs a fresh analysis and atomically replaces that ordered latest slot.
`--refresh` forces a fresh analysis even when both source snapshots still
match. A changed semantic ruleset also performs a fresh analysis while an
older supported artifact remains readable for replacement CAS. Provider or
validation failure leaves the prior saved analysis intact.

Version 1 intentionally keeps `A → B` and `B → A` as separate ordered slots.
This preserves the ability to study whether presentation order changes a
model's judgments. A later product decision may canonicalize the pair and
render two projections from one analysis, but that must not be silently
inferred from the sources' equal authority.

Only the latest analysis for an ordered pair is retained. Revision history,
diffing two analyses, and selecting an older analysis remain future work.

## Relation contract

Every source Memory appears in exactly one primary relation. Relations may be
1:1, 1:N, N:1, or N:M; positional zipping and Cartesian pair enumeration are
both rejected.

| Relation | Meaning |
| --- | --- |
| `EQUIVALENT` | The peers express the same operational claim under the same relevant scope. |
| `COMPATIBLE` | Both claims can remain without inventing a missing scope distinction. |
| `SCOPED` | An explicit condition explains the difference and must be retained. |
| `CONFLICT` | Ordinary scope-aligned readings cannot jointly govern the same case. |
| `DISTINCT` | One peer contains independently useful information absent from the other. Absence is not automatically a deficiency. |
| `UNCLEAR` | The supplied frames do not justify safe placement or interpretation. |

`EQUIVALENT`, `COMPATIBLE`, `SCOPED`, and `DISTINCT` are resolved comparison
descriptions. `CONFLICT` and `UNCLEAR` are unresolved and must be linked to a
visible `REQUIRED` issue. These issues are candidate grounding Cases, not user
judgments, golden Cases, or permission to reconcile anything.

`COMPATIBLE` requires a shared operational decision or policy dimension;
mere coexistence or broad topical similarity would arbitrarily pair unrelated
Memories. Likewise, `DISTINCT` is not a miscellaneous one-sided bucket.
Several same-side Memories may share a `DISTINCT` relation only when they
restate or split one underlying claim. Independent one-sided claims receive
independent relations so a later relation-by-relation viewer has a meaningful
unit of inspection.

The schema deliberately omits Meld dispositions and target Memories. Compare
describes what exists in both, what differs, and what exists on only one side;
Meld later decides what an accepted target should contain.

## Provider and trust boundary

The provider receives call-local opaque frame and Memory IDs, full bounded
direct Memory content, source order, and equal-authority instructions. Context
names remain local presentation metadata: sending advisor names is unnecessary
for comparison and could introduce identity or ordering bias. The provider may
return only `overview`, `relations`, and `issues` under a strict JSON schema.

The schema deliberately omits JSON Schema `uniqueItems` because the Codex
structured-output subset rejects that keyword. Alias uniqueness remains an
invariant and is enforced by the strict local parser before an analysis can
be saved.

Local validation rejects:

- missing, duplicate, unknown, or wrong-side Memory references;
- a `DISTINCT` group containing both sources;
- a non-`DISTINCT` group missing one source;
- omitted or multiply assigned source Memories;
- unknown relation references;
- an unresolved relation without a visible required issue;
- unknown fields, duplicate JSON keys, invalid enums, excessive results, or
  over-limit input; and
- target, proposal, readiness, command, or approval-shaped output.

The persisted frame also recomputes its canonical Context record digest from
the exact ordered Memory snapshot. A stored analysis cannot retain a valid
live-Context digest while displaying altered “exact source” text.

The first slice supports at most 200 direct Memories and 400,000 encoded input
characters. It rejects an over-limit frame rather than truncating or hiding
retrieval calls.

After provider latency, both Contexts are reloaded while their cooperative
write locks are held. Their complete records must still match the analysis.
The ordered slot is also compare-and-swapped against the analysis UID observed
before the call. A changed source or newer concurrent analysis prevents the
new result from being saved.

Comparison artifacts copy source text and derived explanations. Deleting
either bound source therefore removes both ordered orientations involving
that Context. Compare never opens query-only sources.

## First presentation

The non-interactive snapshot groups the complete ledger into:

```text
WHAT BOTH CONTAIN
WHAT DIFFERS
ONLY IN REFERENCE
ONLY IN COMPARED
UNCLEAR
GROUNDING CANDIDATES
```

Every relation remains reachable, including resolved equivalent, compatible,
scoped, and distinct relations. This differs from Atomize, where unchanged
atomic Memories can be omitted from the issue list.

Every source string and provider-authored explanation is rendered through an
injective single-line escape boundary. Embedded newlines, tabs, bidi controls,
or other terminal controls therefore cannot impersonate trusted section
headings.

The first slice is intentionally static. It establishes semantic quality,
durable resume, and relation coverage before view-state persistence or a TUI
is added.

## Task 2 smoke-test observation

The first 20-by-20 advisor fixture exposed two useful design failures. The
initial ruleset grouped nine unrelated one-sided Memories into one
`DISTINCT` relation and paired two broadly audience-related but operationally
independent claims as `COMPATIBLE`. Version 2 added the shared-decision rule
and the prohibition on miscellaneous `DISTINCT` buckets. A fresh run then
produced 30 inspectable relations: ten cross-source relations and twenty
independent one-sided relations, with three required conflict questions.

Running the same snapshots in both orientations preserved the same two scoped
relations, three conflicts, and twenty distinct relations. It nevertheless
shifted the short/descriptive-heading pair across the
`EQUIVALENT`/`COMPATIBLE` boundary, yielding counts of 2/3 in one orientation
and 3/2 in the other. This is a small but concrete order effect despite the
equal-authority prompt, so version 1's decision to retain separate ordered
slots remains useful for the research prototype. Canonicalizing A↔B into one
model call would hide that observation.

## Relationship to Atomize and Meld screens

The Atomize workbench already demonstrates the useful interaction grammar:
overview, list, arrow navigation, exact-source detail, explanation, stable
resume, and a separate application boundary. Compare can reuse that grammar
and the neutral terminal primitives, but not Atomize's semantic session.

The primary Compare list unit must be a **relation**, not an Atomize issue or
a Meld target proposal. A future Compare TUI may use:

```text
overview
→ relation list and category filters
→ arrow/Enter detail
→ exact source Memories, classification, and reason
→ return to the same saved position
```

Choice, free-form comment, impact propagation, and acceptance belong to a
subsequent grounding/Meld session. Compare view state must not be stored as
Atomize choices, and peer relations must not be disguised as atomization
findings.

This follows the existing boundaries in
[`mem-atomize-workbench-design-rationale.md`](mem-atomize-workbench-design-rationale.md),
[`mem-meld-design-rationale.md`](mem-meld-design-rationale.md), and
[`shared-tui-command-review-design-rationale.md`](shared-tui-command-review-design-rationale.md):
share tested terminal mechanics and interaction grammar while preserving
operation-specific identities, evidence, persistence, and mutation semantics.

## Current limitations and next connection

- Compare accepts two normal direct-Memory Contexts only. References, embedded
  Contexts, and query-only sources are rejected rather than silently omitted.
- There is no interactive relation picker, category filter, expanded-detail
  command, JSON output, history browser, or analysis diff yet.
- Automatic fresh analysis after a source change is intentional for Compare;
  it differs from an in-progress Atomize review, whose reviewed proposal fails
  stale rather than silently changing.
- Compare and the current target-bound Meld implementation use the same
  relation vocabulary but still have separate persisted schemas and provider
  parsers. A later shared relation-ledger core should be extracted only after
  the first real Compare result shows which fields both operations genuinely
  need.
- Meld does not yet import a `ComparisonAnalysis`. That future adapter must
  bind the exact comparison UID and digest, create target-specific result
  proposals, and retain the distinction between inspected candidate issues
  and accepted grounding turns.
