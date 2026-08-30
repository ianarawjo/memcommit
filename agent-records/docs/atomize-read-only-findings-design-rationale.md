# Atomize read-only findings and receipt boundary

Last reviewed: 2026-08-29.

## Problem

Atomize had gradually acquired a second responsibility after structural
analysis. Its workbench accepted issue responses, a reviewed response could be
sent through another provider turn, and an Atomize-specific Grounding dialogue
could reinterpret an ambiguity or conflict and apply edits. That made an
Atomize finding both evidence about the structural operation and an implicit
input to a later resolution workflow.

Now that the operations are mature enough to have explicit boundaries, this
coupling is undesirable. Atomize should decide whether each Source Memory is
atomic, composite, uncertain, or non-propositional; preserve its exact
structural proposal; and apply that proposal when authorized. Disambiguation,
resolution, and semantic Memory updates are separate future operations. Their
absence must not make Atomize own a provisional version of them.

## Decision

Atomize ends at structural analysis, exact Output planning, structural Apply,
and a durable receipt. Its findings are immutable evidence:

```text
Source Context
    -> Atomize structural analysis
    -> proposed split/preserve result + ambiguity/conflict evidence
    -> exact Apply or Save As
    -> receipt with every unresolved issue on one logical line
    -> provider-free, read-only `mem review atomize`
```

The operation does not collect a response, select a proposed reading,
reanalyze a response, start a Grounding turn, or incorporate issue resolution
into Apply. No automatic handoff artifact or consumer dependency is created.
A later operation may use the ordinary persisted checkpoint and review
evidence under its own contract, but Atomize neither predicts nor coordinates
that workflow.

`ATOMIZE_UNCERTAINTY` remains the durable operation-owned classification. At
the shared review boundary it is presented as `AMBIGUITY`, because that is the
kind of unresolved evidence a person sees; the projection does not rewrite
the saved analysis.

## Receipt contract

The Apply receipt reports the complete unresolved set instead of only a count.
It prints the heading `UNRESOLVED ISSUES · N · APPLIED AS-IS`, followed by one
logical terminal line for every issue in deterministic saved order. A line
contains its semantic kind, exact Source Memory identity and content, reason,
possible readings, and question when those fields exist. The line is not
truncated and internal newlines are normalized so piped and TTY output retain
the same item boundaries.

Atomize uses the shared `issue_one_line_presentation` component through
`issue_one_line_fragments`, `issue_one_line_text`, and `echo_issue_one_line`.
The component owns only the presentation invariant and semantic token styling;
it does not own Atomize classifications, persistence, resolution state, or
Apply policy. Other issue-producing operations may reuse it without sharing an
operation workflow.

## Read-only Review contract

`mem review atomize` opens only terminal applied evidence. It performs no
provider call and exposes no Responses frame, choice selection, free-form
composer, response flag, or Apply action. `--new`, `--respond-to`, and
`--response` are rejected for Atomize Review. Opening, navigating, and closing
the review writes neither the workbench nor the Context.

The active Python and agent surfaces have the same boundary. Their Atomize
contracts expose `open`, Output planning, in-place Apply, and Save As. Response
update, response reanalysis, incorporate-and-apply, and Atomize Grounding
methods/tools are not public routes.

## Legacy record compatibility

Previously persisted Atomize workbenches can still contain response fields,
and the Store can still contain Atomize Grounding sessions, history, and
checkpoint payloads. Their model decoders, history validation, deletion
cleanup, and Undo/Redo restoration remain so retained records can be loaded and
verified. Active commands never author or consume those fields. This is a
read/restore compatibility boundary, not a hidden executable Grounding route.

Legacy data is intentionally not migrated or deleted automatically. Rewriting
it during an unrelated Atomize run would discard provenance and could make an
old checkpoint unverifiable.

## Alternatives considered

A structured handoff from Atomize to a resolution operation was deferred. It
would make Atomize define the consumer's schema, lifecycle, and identity before
that operation has an independent contract. A receipt is sufficient evidence
without introducing that coupling.

Keeping the conversational UI but treating it as optional was rejected because
the UI, response persistence, provider reanalysis, and compound Apply route
would still make resolution part of Atomize's public responsibility.

Deleting legacy Grounding models and Store paths was rejected because old
history and restoration records remain valid research evidence.

## Verification and limits

Focused tests cover the one-line receipt, ambiguity projection, read-only
Review, absent response and Grounding public routes, strict agent schema,
provider-free saved review, legacy Grounding decoding, and checkpoint
restoration. The ordered 180×52 terminal record under
`agent-records/docs/screenshots/atomize-read-only-findings-20260829/` captures
analysis, immutable finding detail, Apply receipt, and post-Apply read-only
review.

There is deliberately no implemented resolution or Memory-update consumer in
this change. The receipt makes the unresolved evidence observable; what later
uses it remains a separate design decision.
