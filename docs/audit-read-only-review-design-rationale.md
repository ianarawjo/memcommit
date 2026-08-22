# Audit read-only Review design rationale

## Problem

A saved Audit is an historical evidence artifact: it contains one frozen Source
snapshot, three independently typed quality checks, optional Conformance, and
their provenance. Its terminal Review had inherited the common answerable
Resolution Session, which exposed choices, a `RESPONSE` composer, Items, and To
Do even though Audit has no follow-up semantic turn or Apply operation. That
presentation made finding questions look like requests for user decisions and
made a read-only report appear partially executable.

## Decision

`mem review audit` now opens one comprehensive full-screen semantic Viewer.
The Viewer contains, in order:

1. saved Audit identity, completion state, and counts;
2. the complete check summary;
3. every frozen direct Source Memory;
4. optional Conformance and provider/ruleset provenance;
5. each finder group and every source-linked finding detail; and
6. the explicit model-assistance and no-effect boundary.

The same typed document is used by interactive Review, non-interactive Review,
and `--snapshot`. Arrow keys move among semantic sections; Escape, Backspace,
or Q closes. There is no Items hub, Responses frame, selectable reading,
required/optional answer state, draft save, To Do action, provider rerun, or
Apply route.

This intentionally differs from one-shot Find only in host shape. Find is a
compact inline list/detail browser because it is immediate transient output.
Audit is a durable aggregate report and therefore uses the large Viewer, but
both are read-only and share the same source-linked finding document projector.
Answerable `mem review ambiguities` remains a separate operation with its own
review contract.

## Compatibility boundary

Audit schema versions 1 and 2 may contain response records written by the
earlier UI. Removing those fields would make saved research artifacts
unreadable, so decoding and validation remain. A nonempty old response is
shown as `SAVED REVIEW NOTE · HISTORICAL` beside its exact finding. It is not a
focusable control and the new Review route never creates, edits, or saves one.

The legacy `quality_audit_resolution_view` remains as a typed compatibility
projection for stored option validation and callers that still consume its
report shape. It advertises no submit capability and labels itself read-only.
New terminal code must use `quality_audit_review_document` instead.

## Safety and limitations

- Review loads the selected Audit once and does not open its Store for writes.
- Closing or navigating cannot change the Audit record digest, Source,
  Contexts, Memories, checkpoints, or provider state.
- The Viewer reports the saved model judgments; it does not claim that an
  absent finding proves quality.
- Historical notes are retained verbatim as evidence of an earlier review
  lifecycle. There is no migration that interprets them as Resolve, Dedun, or
  clarification guidance.
