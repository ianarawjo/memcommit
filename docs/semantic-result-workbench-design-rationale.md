# Semantic result workbench design rationale

## Status

This document generalizes the result-explanation contract first developed for
the atomize workbench. It defines the shared presentation and inspection
boundary for bounded, one-shot semantic operations such as atomize, update,
compare, and meld. It does not make those operations share one semantic model,
provider prompt, persisted session, or mutation contract.

The atomize workbench is the first implemented adapter. Other operations may
adopt the common result view only when they can supply the required evidence
without inventing an explanation or silently omitting unresolved findings.

## Decision summary

A table, diff, relation ledger, or count can expose exact result records, but
it does not by itself answer the questions a person uses to judge a semantic
operation:

1. **What did the operation understand about its input?**
2. **What did it do with that understanding?**
3. **What could it not safely resolve?**
4. **How did its judgment behave in a representative case and at a difficult
   boundary?**

These questions recur even when the operation's arity, authority, output
vocabulary, and mutation boundary differ. The shared result workbench
therefore presents:

```text
compact counts and status metadata

WHAT MEM UNDERSTOOD
WHAT HAPPENED
WHAT REMAINS UNRESOLVED
REPRESENTATIVE / BOUNDARY CASES
```

Counts remain at the top because they are useful for orientation and workload
estimation. They are deliberately not a fifth semantic section and never act
as a quality score.

The first three sections give complete overview claims for the bounded
operation. Representative and boundary cases form an interactive inspection
layer beneath those claims. Selected cases supplement the overview; they do
not prove coverage and must not hide the complete actionable unresolved list.

## Motivation: semantic results are not adequately explained by rows

The first atomize preview reported facts such as:

```text
51 direct Memories -> 61 projected
14 atomic, 7 composite, 15 uncertain, 15 non-propositional
7 proposed splits -> 17 children
```

Those figures accurately described scale while leaving the important review
questions unanswered. They did not reveal whether:

- an important exception or alternative disappeared;
- an unresolved expression was converted into an unsupported assertion;
- scope, negation, modality, or a relation survived the operation;
- a proposed finding or transformation would be useful for the next action;
- an ordinary item was handled consistently; or
- the operation failed at the boundary where its judgment was hardest.

The same limitation is not specific to atomization:

- an update diff can show edited strings while omitting whether the planner
  understood the source change or propagated it to the right target scope;
- a compare table can align rows while omitting the main relationship between
  the two inputs or the assumptions behind a difficult alignment;
- a meld ledger can enumerate relations while leaving the user to reconstruct
  what the combined result now means;
- a finder can list matches while failing to explain the bounded interpretation
  that made a finding actionable.

Showing every row is not a scalable remedy. It makes review equivalent to
reading the complete input and result again, and it still forces the person to
construct the global account manually. Conversely, a fluent summary without
traceable records can conceal an omission or unsupported inference. The
workbench therefore combines a compact overview with selective, traceable
drill-down.

## Information hierarchy

### Counts and status are top metadata

Counts answer only orientation questions:

- How much input was considered?
- How much output or change is proposed?
- How many items may require review?
- Is this a preview, a ready proposal, or an applied result?

They are useful navigation and workload signals, so they appear immediately
under the operation title. They remain visually compact because:

- a larger result is not automatically better;
- an unchanged count does not prove preservation;
- a small unresolved count does not show issue severity; and
- operation-specific counts are not comparable quality scores.

Counts should be computed locally from validated operation artifacts whenever
possible. A provider must not invent cardinalities that the result model can
derive.

### `WHAT MEM UNDERSTOOD`

This section answers:

> What content and major commitments did the operation think were present?

It is needed because locally plausible transformations or aligned rows can
coexist with a missing subject area. The account should include
opposite-direction information that materially changes interpretation, such
as:

- restrictions and continuing access;
- closures and exceptions;
- unavailable services and replacements;
- a general rule and its narrower scope; or
- agreement and meaningful distinction.

The section lets a person detect global omission or skew without reading every
result. It must be concise, source-linked, and limited to the operation's
declared evidence. It must not claim independent verification merely because a
semantic provider produced it.

### `WHAT HAPPENED`

This section answers:

> What transformation, comparison, selection, or synthesis did the operation
> perform on what it understood?

Understanding and action are separate review dimensions. An operation may
summarize its input correctly while splitting at unusable boundaries, editing
the wrong target, flattening a scoped distinction, or synthesizing claims that
should remain separate.

The section therefore explains material outcomes rather than repeating counts
or implementation rules. Its vocabulary remains adapter-specific:

| Operation | Example outcome vocabulary |
| --- | --- |
| atomize | preserved, split, reconstructed, retained uncertain |
| update | added, edited, preserved, blocked |
| compare | equivalent, compatible, distinct, conflicting, unclear |
| meld | preserved, coalesced, synthesized, kept unresolved |

The exact records remain available in a table, diff, ledger, or detail view.
`WHAT HAPPENED` explains their aggregate semantic consequence.

Meaning loss is not a successful `WHAT HAPPENED` category. When the operation
detects or cannot rule out a material omission under its declared validation
contract, it must block application or retain the source rather than normalize
loss as an ordinary transformation.

### `WHAT REMAINS UNRESOLVED`

This section answers:

> What could the operation not safely decide, and what judgment or action does
> that uncertainty block?

An unresolved referent, incompatible rule, missing scope, unsupported target,
or ungrounded relation is not permission to invent a repair. Surfacing it:

- prevents uncertainty from being hidden inside a confident overview;
- preserves the original evidence instead of replacing it with a guess;
- tells the person what additional context or decision would matter; and
- creates an explicit entry point for a later grounding turn.

The overview may summarize unresolved themes, but the adapter must retain the
complete actionable unresolved items. When an operation supports interaction,
those items are navigable and resumable. Their priority and blocking meaning
remain operation-specific.

An empty unresolved section means only that the operation reported no
unresolved item under its bounded contract. It is not a claim that every
possible external uncertainty was disproved.

### `REPRESENTATIVE / BOUNDARY CASES`

Cases provide concrete inspection of the overview:

- a **representative case** shows how the operation's normal judgment maps
  source evidence through its reasoning to a result;
- a **boundary case** shows the closest difficult, exceptional, ambiguous, or
  scope-sensitive judgment where a mistake would be most informative.

This section is interactive because its value lies in drill-down rather than
in another prose summary. The default row is compact. Expanding a case should
show, as supported by the adapter:

```text
source evidence
-> operation judgment and reason
-> result or proposed action
-> unresolved qualification, if any
```

Case selection must be traceable to real source and result identities. A model
may help select semantically informative cases, but a local validator must
reject unknown identities, duplicate roles that violate an adapter's
contract, or text unsupported by the saved operation artifact.

Representative and boundary cases do **not** establish complete coverage. A
selected sample can look correct while an entire topic is missing. They
therefore supplement, rather than replace:

- `WHAT MEM UNDERSTOOD`;
- `WHAT HAPPENED`;
- the complete actionable unresolved list; and
- operation-specific structural validation.

A result-review case is also not automatically a named Ground Case or golden
Case. Promotion into a Ground requires its own explicit curation and approval
boundary.

## Shared asset boundary

The common asset is a result-explanation and inspection workbench, not a
universal semantic-operation engine.

The shared layer may own:

- compact metric and status presentation;
- the three source-linked overview sections;
- representative and boundary case roles;
- operation-neutral source/result reference containers;
- overview-to-case navigation and detail expansion;
- terminal-safe rendering;
- snapshot behavior; and
- resumable presentation state when an adapter supplies persistence.

Each operation adapter continues to own:

- source arity and authority;
- evidence visibility and privacy boundaries;
- domain-specific finding and outcome vocabulary;
- completeness rules for unresolved items;
- representative and boundary selection criteria;
- semantic provider prompt and output schema;
- persisted operation artifact and stale-input checks;
- reanalysis behavior;
- exact approval and mutation boundary; and
- trace and rationale semantics.

The common renderer must never infer a domain judgment, synthesize missing
provenance, or obtain mutation authority merely because two operations share a
screen.

## Adapter contract

An adapter projects one already validated operation artifact into a common
read-only view:

```text
ResultWorkbenchView
  operation and subject label
  compact metrics and status
  understood section
  happened section
  unresolved section
  complete actionable unresolved descriptors
  representative and boundary inspection cases
```

Every prose section records the source or result identities that support it.
Every case records enough local identity to reopen its operation-specific
detail. Opaque adapter references are preferable to flattening every operation
into one false universal Memory relation.

The projection is read-only. Returning an operation-specific action from the
workbench does not itself apply that action; the owning command validates,
persists, reanalyzes, or applies through its normal boundary.

## Relationship to the shared TUI and Ground

The shared TUI primitives provide terminal mechanics such as safe text,
layout composition, viewport anchoring, and exact-command review. The semantic
result workbench builds on those primitives but owns a different information
contract.

Ground provides a durable Goal--Rules--Cases process for jointly refining
judgment criteria. It may be used to develop or evaluate a result explanation
profile, but ordinary result rendering does not run `mem ground`, and
inspection cases are not silently promoted into Ground Cases.

The reusable relationship is:

```text
shared terminal primitives
          |
semantic result workbench
          |
atomize / update / compare / meld adapters
```

## Alternatives considered

### Count-only output

Rejected as a review interface. Counts convey scale but cannot reveal
omission, unsupported inference, scope damage, relation loss, or poor finding
boundaries.

### Full result table as the primary explanation

Rejected as the only explanation. Exact rows remain important evidence, but
requiring the user to read all of them does not scale and transfers the global
interpretation task back to the person.

### Summary-only output

Rejected because fluent prose can conceal unsupported claims or skipped
records. Overview sections require traceable drill-down and operation-specific
validation.

### Representative or boundary cases only

Rejected because samples cannot prove coverage. Cases remain a high-value
interactive inspection layer below the complete overview and unresolved list.

### One generic semantic provider and persisted session

Rejected because visual similarity does not erase differences in arity,
authority, evidence, mutation, provenance, or completeness. Shared contracts
must not flatten operation-specific semantics.

## Initial adoption

The adoption order is:

1. preserve the existing atomize analysis and workbench artifacts;
2. project atomize's saved overview and findings into the common result view;
3. render atomize through the common information hierarchy while retaining its
   operation-specific issue interaction;
4. prove reuse with an update adapter only after update can honestly supply
   all required sections and traceable cases; and
5. add compare when a semantic compare artifact exists.

An adapter that cannot yet supply a trustworthy section must not fabricate
one merely to satisfy visual consistency. Its adoption remains incomplete and
the limitation must be explicit.

## Implemented first adapter

Atomize now projects its validated saved analysis through
`AtomizeResultWorkbenchAdapter`. The adapter:

- computes counts and the artifact digest locally;
- keeps the recorded understanding, outcome, and unresolved accounts in three
  distinct sections;
- derives only exact structural outcomes from validated items when a legacy
  artifact did not record an aggregate account;
- selects a small deterministic inspection sample rather than repeating the
  complete issue ledger;
- expands each selected case using exact saved source, judgment, result, and
  unresolved references; and
- never calls a provider, changes a Context, or persists review state.

The Atomize shell embeds the common view behind `V` and retains its complete
operation-specific `ACTIONABLE ISSUES` workbench. The non-TTY snapshot uses the
same common hierarchy before the issue ledger.

Loaded legacy Atomize sessions do not retain their original schema version.
The adapter currently recognizes the exact legacy compatibility overview to
mark missing understanding and unresolved scans as `NOT_RECORDED`. This is an
explicit compatibility heuristic; a future artifact revision should persist
overview provenance directly.

Update has not been adapted. Its current saved plan records edits and
additions but cannot distinguish an omitted source as already present,
irrelevant, overlooked, or unresolved. Rendering a clean unresolved section
from that data would be a false claim. Update must first record exhaustive
source disposition, unresolved findings, and source-linked overview evidence.
