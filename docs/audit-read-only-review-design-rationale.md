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

`mem review audit` opens one comprehensive full-screen semantic Viewer, but
the saved document is compact rather than a stack of field-sized sections. It
contains, in order:

1. one overview with saved Audit identity, completion state, check counts,
   Source scope, and every frozen direct Source Memory in one wrapping snapshot
   line;
2. one header section per Duplicate, Ambiguity, and Conflict check, followed by
   one independently navigable section for every positive result, represented as the
   same source-linked logical line used by Find;
3. optional Conformance, then provider/ruleset provenance; and
4. the explicit model-assistance and no-effect boundary.

Source bodies remain complete, including Memories with no positive finding,
but they no longer become one focus stop and heading per Memory. A positive
result then repeats only the evidence needed to understand its issue:
Ambiguity folds ordinary readings into `WHY`, Conflict keeps its pair and
`WHY`, and Duplicate keeps its relation and pair without a repeated reason.
Ambiguity and Conflict keep their smallest follow-up question as read-only
evidence; there is no response field or selectable choice. This preserves the
typed historical report while making section
navigation track real Audit concepts rather than serialized fields.
Each finding is deliberately the smallest scroll stop: its source Memory or
pair and rationale remain together, while a category containing many findings
cannot become one indivisible focused block. Splitting a finding again into
field-sized stops was rejected because it would separate one judgment from the
evidence needed to understand it. Each quality header colors its `REDUNDANCIES`,
`AMBIGUITIES`, or `CONFLICTS` token with the same typed semantic role used by
the finding token below it. Counts, `FLAGGED`, Source identity, relation values,
and prose remain neutral, so the color links category to evidence without
tinting report chrome.

Within a focused finding, the leading `=`, `≈`, `?`, or `!` marker temporarily
changes from neutral white to the shared focus blue. The adjacent `DUPLICATE`,
`REDUNDANT`, `AMBIGUOUS`, or `CONFLICT` label deliberately retains its semantic
color. This makes the left edge advertise the active keyboard stop without
erasing the finding category; leaving the row restores the marker to neutral.
Finding labels are non-bold at rest and become bold only with their finding's
keyboard focus. Check headers remain bold, so `CONFLICTS` continues to identify
the category boundary while each subordinate `CONFLICT` is visually quieter
until it is the active reading unit. The same hierarchy applies to Duplicate,
Redundancy, and Ambiguity findings.
The Memory and rationale fragments retain their existing blue focus treatment,
so the marker and evidence identify one active logical paragraph.

The same typed document is used by interactive Review, non-interactive Review,
and `--snapshot`. Arrow keys move among semantic sections; Escape, Backspace,
or Q closes. There is no Items hub, Responses frame, selectable reading,
required/optional answer state, draft save, To Do action, provider rerun, or
Apply route.

This intentionally differs from one-shot Find only in host shape. Find is a
compact inline complete-paragraph browser because it is immediate transient
output. Audit is a durable aggregate report and therefore retains the
full-screen Viewer, but both are read-only and share the same compact
source-linked finding projector.
Answerable `mem review ambiguities` remains a separate operation with its own
review contract.

## Compatibility boundary

Audit schema versions 1 and 2 may contain response records written by the
earlier UI. Version 2 Conflict records also contain the retired
`scope_dimensions` classifier. Removing those fields without a migration would
make saved research artifacts unreadable, so strict legacy decoding remains;
the current version 3 form discards only that unused classifier while retaining
reason and question verbatim. The compact default Viewer does
not show those old dispositions or notes: they are neither current Audit
findings nor instructions for a downstream operation. The new Review route
never creates, edits, or saves one. A future explicit historical-record export
may expose them without putting answer-like annotation back into this report.

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
- Historical notes remain retained verbatim in the stored record but are not
  projected into the default Viewer. There is no migration that interprets
  them as Resolve, Dedun, or clarification guidance.
