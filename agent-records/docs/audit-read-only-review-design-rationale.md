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

## Console presentation ownership

Audit's console-specific pieces are co-located under
`memcommit.adapters.console.commands.audit`: `command.py` owns CLI operands,
authority checks, progress projection, application invocation, and publication
of the completed Session; `receipt.py` owns the compact saved-result receipt,
`setup.py` owns Source selection, `session_catalog.py` owns the saved-session
catalog, and `review.py` owns the read-only report projection and Viewer launch.
The former
`memcommit.adapters.interfaces.tui.operations.audit` package and the former
`commands.audit.sessions` module are removed rather than retained as facades.
`mem review audit` imports the narrow command-owned modules directly.
This is an ownership-only relocation: setup interaction, catalog reads and
ordering, report content, Viewer behavior, exceptions, and the zero-write
boundary are unchanged. The existing Audit terminal captures therefore remain
behaviorally valid; their reproduction script now imports the command-owned
setup module.

## Application ownership

Audit's application-specific model, execution, and persistence port live under
`memcommit.application.operations.audit`.
`model.py` owns the durable Source, Check, Session, schema validation, and record
digest; `application.py` freezes one Source, runs the three quality finders plus
optional Conformance as one complete operation, and publishes only a validated
record through `repository.py`'s `AuditRecordRepository` port. The concrete
`persistence.operations.audit.record_repository.JsonAuditRecordRepository`
owns private immutable UID-addressed JSON records. The read-only console projector
composes the shared Memory-issue report views directly; Audit has no Resolution
projection, response model, option grammar, or CAS update route. The reusable
finder, report, and workbench contracts remain under
`application.capabilities.reviewing.memory_issue`.

Optional Conformance is preflighted inside the Audit application before any
provider connection. Console progress is supplied through callbacks, but the
console no longer assembles or re-creates the fourth-check Session itself. This
keeps all configured checks over one frozen Source and returns exactly one fully
validated Session; a failed check publishes no partial Audit. The former
`application.capabilities.reviewing.quality.audit` and `audit_store` modules are
removed without compatibility facades because they were provisional internal
owners, not supported import surfaces. The remaining shared capability was
then named `reviewing.memory_issue`: its outputs are model-assisted
issue candidates for review, not proof of a generalized quality judgment.

The response-bearing draft was never distributed. On 2026-08-30 its runtime
compatibility was removed instead of turning an unreleased shape into a durable
contract: the sole read-only schema starts at version 1, strict decoding rejects
the discarded drafts, and no migration or compatibility facade is provided.
`QualityAuditSession` is frozen,
`JsonAuditRecordRepository.create` is create-only, and an existing UID cannot
be replaced. Historical screenshots remain evidence of the
prototype's earlier UI; they do not define a supported record or Python API.

The application contract deliberately exposes `create`, `load`, `list`, and
record modification metadata without exposing a filesystem `Path`. JSON
encoding, private directories, per-UID locks, and atomic replacement remain
physical persistence concerns. Mutable operation sessions remain distinct from
immutable records, receipts, and the cross-operation command ledger.

## Safety and limitations

- Review loads the selected Audit once and does not open its Store for writes.
- Closing or navigating cannot change the Audit record digest, Source,
  Contexts, Memories, checkpoints, or provider state.
- The Viewer reports the saved model judgments; it does not claim that an
  absent finding proves quality.
- Audit records contain no response or disposition fields.
