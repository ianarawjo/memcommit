# Atomize one-shot execution design rationale

## Decision

`mem atomize [TARGET]` is a target-driven, one-shot, in-place operation. It
freezes one ordinary local Context and an optional direct Memory, obtains or
creates the exact semantic analysis, applies it immediately to the owning
Context, and records one Atomize checkpoint. It does not open an Endpoint
Setup, select an Output, or maintain an executable workbench session.

The accepted target spellings are:

- no target: the current Context;
- `CONTEXT`: every directly owned Memory in that Context;
- `UID_OR_PREFIX`: one uniquely owned direct Memory;
- `CONTEXT:UID_OR_PREFIX`: one direct Memory with an explicit owner;
- `-c/--context` and `--memory`: explicit aliases for the same contract.

A focused Memory is the only actionable source. Other direct Memories in its
Context may be exposed as interpretation evidence, but they are never added to
the replacement set. The active Context name is captured once at command
start, and relative Context operands are resolved against that snapshot.

## Analysis, application, and records

Application code owns the complete analysis-to-checkpoint use case through
`AtomizeInPlaceRequest` and `execute_atomize_in_place`. A compatible unapplied
analysis is reused; `--refresh` forces a new provider analysis before the same
immediate application. An exact already-applied target is recovered without a
provider call or a second checkpoint unless refresh explicitly requests a new
analysis.

Atomize keeps durable analysis and application evidence so Trace, Impact, and
Review can explain what happened. These are records, not resumable execution
sessions. `mem impact atomize` owns non-applying analysis presentation and
keeps cursor/sort changes process-local. `mem review atomize` owns the
read-only completed report. Neither route changes Memories or chooses a future
Atomize destination.

The historical workbench JSON schema remains readable because existing
profiles and Python API callers may contain its cursor, sort, response, and
Output-plan fields. New console execution does not write those interaction
choices. The physical legacy storage names are therefore a compatibility
boundary, not the conceptual owner of current execution.

## Removed console routes

The Atomize command no longer exposes `--sessions`, `--save`, `--save-as`,
`--output`, or `--all`. Saved analysis discovery belongs to the generic
Impact/Review record browsers. New Context creation remains an explicit
operation such as Branch followed by Atomize, rather than a hidden Atomize
destination mode.

The old role-based `endpoint_setup/flows.py` and `endpoint_setup/session.py`
existed chiefly to launch that multi-stage Atomize workflow. After Update and
the other commands acquired command-owned setup adapters, Atomize was their
last production consumer, so the two legacy modules were removed. The compact
Endpoint Setup model, screen, command binding, and Memory-focus components
remain shared by Branch, Meld, Sever, and Update.

## Safety invariants

- Context freshness, selected Memory identity, source order, and content are
  revalidated before materialization.
- Every provider result covers the complete frozen actionable set before any
  partial result is published.
- In-place split and Dedun effects publish as one checkpoint or are
  compensated when the terminal application record cannot be committed.
- Retry recognizes only the exact analysis/checkpoint/audit combination; it
  never adopts an unrelated Atomize checkpoint.
- An all-preserved result is still a deliberate Atomize completion and records
  a checkpoint.
- Impact and Review are evidence routes and cannot acquire mutation authority
  from persisted UI fields.

## Alternatives rejected

Keeping the multi-stage workbench was rejected because it made a structural
transformation look like a destination-planning workflow and distributed one
console component across command, workbench, and shared Endpoint Setup
packages. Moving that workbench wholesale under a new shared package was also
rejected: the reusable part is the analysis/application boundary, while the
two visible projections have different owners and mutation promises.

Removing durable evidence entirely was rejected because exact retry, Trace,
read-only Review, and post-application explanation require stable analysis and
checkpoint identities. The retained evidence is intentionally narrower than
an executable session.

## Remaining compatibility boundary

The public Python/agent Atomize APIs still expose historical Output-plan and
Save As shapes for compatibility. They are not CLI authority and must not be
used to reintroduce destination selection into `mem atomize`. A later public
API version may remove those shapes with an explicit migration; this change
does not rewrite existing profile records or checkpoint history.
