# Save Context from selection design rationale

## Problem

Search allowed checked result rows to become a new Context, but that write was
owned by Search modules named `materialization_application` and
`materialization_runtime`. The boundary mixed a reusable selected-result save
with Search response validation, offered only COPY and REFERENCE, and called
the live Embed primitive for the mode labelled REFERENCE. It also retained a
local-only REFERENCE restriction from the retired derived-use Grant model.

Find and Search can both produce ordered rows bound to exact Source Memories.
Their matching or ranking remains operation-specific, while saving those rows
has the same authority, ownership, relationship, locking, and require-new
publication semantics. A Search-owned persistence path would force Find to
import Search or reproduce the write.

## Decision

`memcommit.application.capabilities.save_context_from_selection` is the
canonical owner of the shared write. Its application contract receives:

- one nonempty ordered tuple of `SelectedMemory` values;
- each row's displayed position, kind, public Source Context name and UID,
  Source Memory UID, exact displayed content, and optional relevance;
- one typed `SelectionOrigin` naming the Source operation and its string input;
- one exact `COPY`, `REFERENCE`, or `EMBED` mode; and
- one require-new local destination name.

The selecting operation owns conversion to that contract. Search uses
`application.operations.search_explain.retrieve_answer.search.save_context` to reject non-Memory evidence,
map an authority-private MemoryRef target back to its public Grant name, and
retain the search query as origin evidence. The shared capability imports no
Search type and can therefore accept an equivalent Find adapter later.

The application runner uses a prepare-then-save port. The Store runtime
resolves every public Source from the selecting operation's frozen readable
catalog, checks exact Context UID, direct Memory UID, and content, constructs
the complete output in memory, and publishes the new Context only while all
Source and Grant bindings remain stable. A stale Source, revoked READ use,
destination collision, or write failure publishes neither a partial Context
nor a checkpoint.

New checkpoints retain `save_context_from_selection.version = 1`, Source
operation and arguments, mode, output name, and every selected Source/output
identity. Historical `search_materialization` records remain readable and are
not rewritten.

## Relationship modes

The three modes are distinct durable meanings:

| Mode | Durable item | Later Source change | Identity/authority behavior |
| --- | --- | --- | --- |
| COPY | directly owned `Memory` with a fresh UID | no effect | independent local value |
| REFERENCE | snapshot `MemoryRef` with content digest | no effect | read-only retained value with Source provenance |
| EMBED | live `MemoryRef` without retained content | reflected when readable | re-resolves the exact Source; a granted link reauthorizes READ |

The runtime uses `ops.reference_memory` only for REFERENCE and
`ops.embed_memory` only for EMBED. For a granted Source it persists the public
name and typed `GrantedMemorySource`; authority-private storage locators never
enter the local Context. COPY and REFERENCE remain locally readable after the
Source changes. A live granted EMBED can become unresolved after revocation,
which is its intended relationship semantics rather than a save failure.

## Authorization and ownership

The runtime calls `authorize_context_use(access, ContextUse.READ)` before
using every resolved Source. READ covers provider use, combination, local
retention, snapshot Reference, and live Embed creation. DERIVE, COMBINE,
EXPORT, SAVE_ANALYSIS, and EMBED are not permissions and are not reconstructed
as mode-specific gates.

The destination is always a new Context in the active Profile's local Store,
so no granted Target permission is involved. A future adapter that writes into
an existing granted Target must remain a different request shape and require
its exact CREATE, UPDATE, or DELETE use. Save Location does not accept an
existing Context locator and never switches Current.

The lower-level Grant snapshot lock still receives READ as an infrastructure
atom so it can re-resolve the same binding and prevent a Grant revision race
through publication. That lock is not an alternative authorization policy:
the application-visible decision is `authorize_context_use`.

## Alternatives considered

Keeping two modes and renaming the old REFERENCE to EMBED would preserve the
existing bytes but omit the already implemented immutable Memory Reference
semantics. Treating REFERENCE and EMBED as one generic LINK would hide the most
important future-read difference from review. Both were rejected in favor of
three explicit modes.

Keeping the write under Search would require a parallel implementation or an
inverted Find-to-Search dependency. Moving all Search result types into the
capability would instead make matching and ranking generic when they are not.
The selected-Memory request is the narrower reusable seam.

Calling only the infrastructure `authorized_context_operation` lock would
enforce READ but leave the gradual `ContextUse` migration invisible at the
application boundary. The runtime deliberately performs the typed
authorization decision first and retains the lower-level lock only for race
closure.

## Limitations and non-goals

- The capability saves directly owned Source Memories. Query-only rows,
  retained artifacts, and rows without an exact Source Memory identity cannot
  enter it.
- Search is the first caller. Provider-free Find can adopt the capability when
  its result workbench gains a reviewed Save As surface; this change does not
  add that separate presentation workflow.
- Move is not a Save As mode. Moving changes Source ownership and requires a
  different multi-Context transaction and inbound-link policy.
- A checkpoint records why and how rows were saved; it does not turn semantic
  ranking into proof that the Source operation answered its input correctly.

## Verification record

`tests/test_save_context_from_selection.py` covers typed request/plan/receipt
matching, exact three-mode construction, local snapshot-versus-live behavior,
explicit `ContextUse.READ` authorization, Source and destination race closure,
rollback, READ-granted Sources in every mode, and Search adapter composition.
`tests/test_search_workbench.py` covers keyboard selection of all three visible
Save As choices.

`agent-records/docs/screenshots/search-save-context-from-selection-20260830/`
records the actual Search command workbench and shared Store runtime in
isolated 180×52 color PTYs. Its ordered log includes common Search input and
result selection plus exact Save Location, reviewed action, successful receipt,
and read-only output verification for COPY, REFERENCE, and EMBED.
