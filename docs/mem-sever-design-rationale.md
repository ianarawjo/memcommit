# `mem sever` design rationale

## Problem and meaning

`mem sever` creates a new local Context that deliberately forgets selected
content from an existing Source. It is a content transformation, not a Share
preparation step. It has no recipient, destination, delivery, consent, or
transmission semantics. The Source is immutable throughout the operation.

One pass has three roles:

```text
SOURCE ordinary Context × one CRITERIA ordinary Context
    → new local RESULT Context
```

The whole Source frame and whole Criteria frame use the shared
[selective-curation batch contract](selective-curation-design-rationale.md).
Inference is one contextual provider turn, while the returned artifact retains
exactly one independently reviewable decision per Source Memory. Sever keeps
its own durable schema, authority checks, and require-new materializer.

The explicit form is:

```text
mem sever --source SOURCE --criteria CRITERIA --save-as RESULT
# optional: --source-only / --source-descendants
#           --criteria-only / --criteria-descendants
```

`--against` aliases `--criteria`. `--to` is absent because Sever names no
destination. `mem share` is an independent operation that can separately
review any eligible ordinary Context.

## Semantic contract

The provider returns exactly one decision for every Source Memory:

- `KEEP_AS_WRITTEN`: retain the exact source text;
- `KEEP_REDACTED`: retain a redacted standalone Memory;
- `KEEP_SUMMARY`: retain a standalone summary;
- `KEEP_PREFERENCE_OR_POLICY`: retain a condition-preserving preference or
  policy; or
- `FORGET`: omit the Memory from the Result.

The provider may use only the supplied Source and the one Criteria frame. It
must not infer an audience, destination, or later use. Any retained rewrite
must preserve material conditions, exceptions, time bounds, and uncertainty
without inventing facts. `KEEP_AS_WRITTEN` is checked byte-for-byte and
`FORGET` must return empty result content. Criteria citations are bounded to
the supplied opaque aliases and checked for uniqueness locally.

Older saved sessions may contain `SEND_*`, `DO_NOT_SEND`, or `EXCLUDE`
compatibility tokens. Loading maps those values to the neutral version-2
decision vocabulary; new provider turns and newly serialized records never
emit the legacy Share-oriented terms.

## Setup and review

With no operands in a TTY, Sever opens the shared saved-session launcher.
Starting a new session uses the three-pane Source–Criteria–Result setup. Source
and Criteria reuse the ordinary Context namespace tree and independently select
`THIS CONTEXT ONLY` or `INCLUDE DESCENDANTS`. Query-only rows remain visible
but unavailable. Result is a fresh editable Context name and never overwrites
an existing Context. Its initial suggestion is derived from Source and
Criteria, not from the first local catalog row: Mem finds their deepest shared
path that is also an ordinary local Context and proposes `ANCESTOR/severed`.
If they share no local ancestor, it proposes the top-level `severed`; occupied
suggestions receive a numeric suffix. This keeps a granted
`task-3/remote/...` Source and local `task-3/local/...` Criteria oriented under
`task-3/severed` without pretending the granted path is locally writable.

The provider turn creates only a retained review session. The shared Resolution
Workbench then shows:

```text
classification → Source/Criteria evidence → rationale → Sever question
→ result choices → proposed Result Memory → response
```

Creating that session uses the shared transient TTY progress line. It reports
only host-observable stages—freezing Source and Criteria, connecting the
provider, and analyzing the complete frames—plus the frozen Source and
Criteria Memory counts and elapsed time; it does not invent provider-side
percentages. A provider failure repeats those counts and the effective timeout
so an unsaved failed attempt remains diagnosable without retaining its Memory
content. Because the selective-curation invariant requires one complete Source
× Criteria turn, Sever uses the configured semantic timeout exactly. It does
not silently fall back to the Codex adapter's shorter transport default or
extend the wait beyond the timeout shown by `mem provider status`.

The Profile command-attempt ledger freezes the selected Source/Criteria/Result
names, scopes, ordinary Memory counts, provider, and effective timeout before
inference. A timeout or invalid response is therefore inspectable later with
`mem log --operations` even though no valid Sever review session was created.
This attempt evidence contains no Memory text, candidate output, rationale, or
query-only Context name.

Every Source Memory is a REQUIRED review item because each needs an explicit
keep, rewrite, or forget treatment. The report-level `WHAT APPLIED` paragraph
explains the main material transformation or preservation pattern rather than
leading with classification totals. Like Atomize's `WHAT CHANGED`, the text is
a concise provider-authored paragraph grounded by bounded references. Sever
then names up to three representative affected Source Memories and the three
most frequently cited Criteria Memories; exact Source-to-Criteria mappings and
rationale remain in Items. Version-2 sessions without the grounded paragraph
fall back to the same locally derived affected-Source and influential-Criteria
view rather than being reanalyzed.

When Impact is present it is the only full per-Memory result list; the report
does not print the same potentially large list above it. Impact shows the exact
local Result that Apply would create and explicitly says the Source remains
unchanged. Compact display labels (`KEEP`, `REDACT`, `SUMMARIZE`, `REFRAME`,
and `FORGET`) keep large lists scannable while persisted/provider decision
tokens remain unchanged.

Each Sever Impact row follows the `mem ls` hanging layout: `[TREATMENT]`, the
short UID, and result content begin on one line, with continuation text aligned
to the content column and no blank separator between rows. The treatment field
uses the widest visible treatment as its display width, so every UID and result
begins in the same column. Exact cited Criteria
Memories and candidate rationale are both hidden in the resting list. Every
Impact Memory is a semantic navigation stop, and Enter toggles that one
Memory's indented `RULE` and `WHY` detail without changing the review or
leaving the report.
The marker and treatment tag use distinct semantic colors for `KEEP`, `REDACT`,
`SUMMARIZE`, `REFRAME`, `FORGET`, and `CUSTOM`; the rest of the Memory remains
under the common Memory-object color contract while resting. When focused, one
Impact row—including UID, content, Rule, and Why—follows its treatment color
instead of the shared blue focus; this exception is scoped to Impact. Impact
and Items both reflow to the live Viewer/Items frame width instead of retaining
a report-specific fixed column count.

Scripted review uses `--choice recommended`, `as-written`, `forget`, or
`custom`. Custom content is exact Result Memory text. `--accept` creates the
new local Result Context; it does not edit or delete anything in Source.

## Context and authority boundaries

Both Source and Criteria resolve through ordinary `READ` access. An
`INCLUDE DESCENDANTS` frame freezes embedded ordinary children and readable
ordinary lexical descendants. `THIS CONTEXT ONLY` loads direct items only.
Both projections skip `QueryContextRef` and fail on live `MemoryRef` rather
than copying through a pointer.

The session retains only the public names of query-only Context references
encountered and excluded while capturing either frame. The report says nothing
about query-only access when that set is empty. When it is nonempty, it names
those Contexts once and explains that query-only authority does not grant
readable Memory access; their routing metadata and hidden content never enter
provider input.

One Criteria root keeps precedence, provenance, and authority intersection
explicit. When multiple criteria need equal authority, they can first be
reviewed into one Criteria Context. Running Sever repeatedly is allowed and is
intentionally order-dependent because a later pass cannot reconsider content
forgotten by an earlier Result.

Granted inputs retain the existing derived-work checks: `READ`, the required
`DERIVE`/`COMBINE` authority, transfer authority into the local Result, and
`SAVE_ANALYSIS` for retained exact frames. Query-only authority never becomes
ordinary Memory input.

### Study prewarm subset projection

The declared Task 3 `300 × 75` Sever artifact is also a basis for unchanged
subsets. Runtime lookup compares ordered `(Memory UID, owner name, content)`
ledgers, not raw root depth or descendant flags. Additions, edits, reordered
identities, cross-task inputs, output-name changes, and configuration drift
remain misses.

A projected review still contains exactly one candidate for every selected
Source Memory. If all Criteria cited by the prepared candidate survive, the
candidate is rebound unchanged. If cited support was removed, the projection
uses `KEEP_AS_WRITTEN`, exact Source content, and no criterion citation. This
is the conservative consequence of deleting a filtering rule; it avoids both
applying an absent rule and making an ungrounded replacement transformation.
The fresh review and candidate UIDs, `PROJECTED PREWARM` label, complete
coverage validation, authority checks, require-new output, and application CAS
remain mandatory.

## Persistence and application

A version-3 Sever session retains exact Source and Criteria frames, Context identities
and digests, granted bindings, one decision per Source Memory, current manual
selections, exact custom content, the grounded applied-summary references,
names of excluded query-only Context references, and an application receipt.
Writes use a record-digest compare-and-swap. Versions 1 and 2 remain readable;
new serialization emits version 3.

The terminal-independent application boundary owns that complete private
session lifecycle through `SeverSessionRepository`. Create and open return a
`SeverSessionSnapshot` with an opaque version token; candidate decisions,
destination changes, and persisted Apply consume that exact token. The Store
adapter alone interprets it as a record digest. CLI and TUI adapters therefore
cannot bypass CAS by directly saving a session or recomputing its digest.

The workbench shows a compact focusable `SAVE LOCATION` frame between `ITEMS`
and `TO DO`. Enter opens its shared one-line direct editor. Saving a new exact
name updates the REVIEWING session under its record-digest CAS, then returns to
the same workbench; it neither reruns the provider nor creates a Context.
Existing names and invalid ordinary Context identifiers fail before the session
changes. Review-only surfaces omit this control.

Apply revalidates local contributing Contexts under the output creation lock.
For a granted Source or Criteria it also revalidates the frozen Profile and
Grant identity, revision, permissions, public/resource mapping, and complete
projected frame immediately before and after output creation while the Grant
registry is frozen. It then creates one require-new ordinary Context and records
a `sever` checkpoint with the session, Source, Criteria, Result, and
source-to-result mapping. A stale or revoked granted input, including a change
during creation, leaves no partial Result. Forgotten content and rationale
remain only in the Sever session. The Source record and its Memories are never
mutated. An all-KEEP disposition is still a real Sever result and
therefore creates the reviewed Result Context and checkpoint; it is not treated
as a no-op on Source.

Result Context creation and the private APPLIED session receipt are two atomic
file operations rather than one shared transaction. A synchronous receipt-save
failure re-reads the session before compensating. If the receipt actually
committed, Apply reports success; if the session is still the exact REVIEWING
snapshot, Sever deletes only the untouched Result and sole checkpoint created
by that attempt. It refuses compensation when either durable side changed.
After a process interruption in the gap, retrying Apply recovers the receipt
only when the existing Result digest and its sole Sever checkpoint exactly
match the accepted session. An unrelated Context at the output name remains a
normal require-new collision.

Command Undo removes that exact Result Context and returns the saved session to
`REVIEWING`. Because the ordinary Context must be absent while still supporting
Redo, its record and complete checkpoint directory move to a private command
archive. Redo fails closed if the output name was reused or the review changed;
otherwise it restores the same Context UID and application receipt and appends
a `redo` checkpoint after the retained `sever` and `undo` entries. Session-save
failure rolls the Context move and provisional checkpoint back together.

`mem review sever` reuses the same evidence and proposed Result with Apply
removed. It cannot create the Result Context.

## Alternatives and limitations

- Mutating or deleting Source was rejected: “forget” describes the derived
  Result's memory boundary, while Source preservation keeps review and recovery
  possible.
- Treating query-only answers as Criteria was rejected because query authority
  does not imply ordinary read, derivation, or retained-analysis authority.
- Coupling Sever to Share was rejected. Share owns its own source snapshot,
  endpoint, preview, approval, digest, and delivery checks.
- `mem trace` and `mem rationale` do not yet render a dedicated Sever lineage
  view.
- A machine failure can still interrupt filesystem durability below the
  atomic Context/checkpoint or session-file primitives. Sever recovers the
  complete known gap between those primitives, but it does not provide a
  cross-filesystem journal for damaged or only partially durable files.
- Sever Undo/Redo has exception rollback across Context and session writes, but
  a process or machine crash between its file moves is not journal-recovered.
