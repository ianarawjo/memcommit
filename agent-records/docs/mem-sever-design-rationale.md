# `mem sever` design rationale

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Problem and meaning

`mem sever` deliberately forgets or rewrites selected content from an existing
Source scope. It is a content transformation, not a Share preparation step. It
has no recipient, delivery, consent, transmission, or user-selectable Result
semantics. New console sessions always update each selected Source owner at its
existing Context location.

One pass has two roles:

```text
SOURCE ordinary local Context scope × one readable CRITERIA Context scope
    → each selected SOURCE owner updated in place
```

The whole Source frame and whole Criteria frame use the shared
[selective-curation batch contract](selective-curation-design-rationale.md).
Inference is one contextual provider turn, while the returned artifact retains
exactly one independently reviewable decision per Source Memory. Sever keeps
its own durable schema, authority checks, in-place publication, and
translation from reviewed choices to exact Update operations. The ordinary
detached Context post-image is produced by the shared Update application
boundary; Update does not own Sever's review, checkpoint, receipt, or Undo.

The positional-first forms are:

```text
mem sever SOURCE CRITERIA
# optional: --source-root-only / --source-descendants
#           --criteria-root-only / --criteria-descendants
```

Exactly two positional operands are accepted. `--source`/`--from` and
`--criteria`/`--against` are equivalent role aliases and may fill a role not
already supplied positionally. The console does not expose a third Result
operand, `--save-as`, or `--to`; Source ownership determines every write
location. Older Result-bearing sessions remain readable and resumable through
their retained application contract, but new console setup cannot create one.
`mem share` remains the independent delivery operation.

SOURCE and CRITERIA are existing-Context locators resolved from one captured
current-name snapshot. The canonical Source name is retained internally as the
in-place post-image identity; it is not a third endpoint.
Supplying one role twice—including two aliases such as `--source` plus
`--from`—or more than two positional operands fails before provider or Store
access.

The common `-d/-r` preset applies to both input roles; either canonical
role-qualified pair can then override one role. The older `--source-only` and
`--criteria-only` spellings remain input-compatible aliases, while restoration
output uses the canonical `--*-root-only` form.

## Semantic contract

The provider returns exactly one decision for every Source Memory:

- `KEEP_AS_WRITTEN`: retain the exact source text;
- `KEEP_REDACTED`: retain a redacted standalone Memory;
- `KEEP_SUMMARY`: retain a standalone summary;
- `KEEP_PREFERENCE_OR_POLICY`: retain a condition-preserving preference or
  policy; or
- `FORGET`: remove the Memory from its Source owner on Apply.

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

With no operands in a TTY, Sever opens the shared compact Endpoint Setup with
directly editable Source and Criteria role rows. `mem sever --sessions`
opens the shared saved-session launcher, whose New action delegates to that
same setup. Source and Criteria expose the ordinary readable Context namespace
through adjacent Browse controls and independently select `THIS CONTEXT ONLY`
or `INCLUDE DESCENDANTS`. Query-only rows remain visible in Browse but
unavailable. Both input rows reuse the common lazy Memory controller in
explicit read-only mode. Source is selectable only from ordinary local
Contexts because every
selected Source owner is an in-place mutation target. Their `MEMORY · READ ONLY`
controls open the selected exact readable
Context's direct Memories as viewport stops; Enter keeps the whole Context and
cannot place a Memory UID in the typed setup receipt. Query-only rows remain
name-only, and preview loading neither changes the frozen Sever scope nor
starts provider analysis. No Result or Save Location control is rendered. The
command-local 684-line screen was retired in
favor of the shared component. Sever's typed role specification, validation,
and reviewed setup receipt now live in
`memcommit.adapters.console.commands.sever.endpoint_setup`; no operation-specific TUI
facade remains under `adapters.interfaces`.

The ordered 180×52 color trace under
[`screenshots/sever-shared-endpoint-setup-20260823/`](screenshots/sever-shared-endpoint-setup-20260823/README.md)
records entry, independent Source range, read-only Memory evidence, Criteria
Browse, the exact two-operand START review, in-place Apply, and read-only proof
that every selected Source owner stayed at its original Context location.

An explicit local TTY invocation whose provider recommendations already answer
every required item follows the shared decision-free `AUTO_ACCEPT` policy and
applies the selected in-place change immediately; `mem undo`
remains its recovery.
Redirected/non-TTY execution still retains the saved REVIEWING session unless
`--accept` is supplied, so scripts do not cross an implicit write boundary
merely because their output is redirected.

Apply preserves every selected Source Context UID and every retained Memory
UID, removes reviewed `FORGET` Memories, and updates transformed Memories under
their existing UID. If Source descendants are included, each direct owner is
projected separately and saved at the same name under one grouped command
receipt. This makes Sever the selective-removal counterpart to Meld's additive
target update without borrowing Meld's relation mode vocabulary. The related
self-target audit is:

| Operation shape | Self-target contract | Reason |
| --- | --- | --- |
| Forget | Source is the in-place target | The instruction curates that exact writable Source and records its checkpoint. |
| Atomize | `INPUT=OUTPUT` is supported | Its saved Output plan explicitly distinguishes in-place Apply from require-new Save As. |
| Translate | Only explicit `--in-place` | The flag chooses bilingual sibling materialization; `--save-as` remains derived output. |
| Meld existing-target form | The receiving target is updated; incoming must differ | Meld adds or reconciles reviewed content into that existing target. |
| Compare / structural Merge | The two inputs must differ | A self-comparison or self-union has no second evidence/transfer role. |
| Meld new-result form | Both peers and Result differ | Equal peers stay read-only while a new combined Result is created. |
| Distill | Result must be new | Its derived knowledge is published separately. |
| Sever | Every selected Source owner is updated in place | Source ownership, not a Result selector, determines the mutation location. |

These are operation meanings, not parser accidents. Forget still takes a
process-local instruction, while Sever evaluates a complete frozen Criteria
Memory frame and retains a per-Memory review session. Source descendants are
supported for ordinary local Sources; granted Source roots fail before provider
construction because READ does not confer UPDATE or DELETE authority.

The provider turn creates only a retained review session. The shared Resolution
Workbench then shows:

```text
classification → Source/Criteria evidence → rationale → Sever question
→ treatment choices → proposed after-state Memory → response
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

The Profile command-attempt ledger freezes the selected Source/Criteria
names, scopes, ordinary Memory counts, provider, and effective timeout before
inference. A timeout or invalid response is therefore inspectable later with
`mem log --operations` even though no valid Sever review session was created.
New in-place attempts do not store or render an Output endpoint; the operation
log labels their route `IN PLACE`. Legacy `OTHER_SAVE` attempts may retain their
historical Output field. Attempt evidence contains no Memory text, candidate
output, rationale, or query-only Context name.

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

When Impact is present it is the only full per-Memory after-state list; the
report does not print the same potentially large list above it. Impact shows
the exact local changes that Apply would make and states that each Source owner
stays at its existing location. Compact display labels (`KEEP`, `REDACT`, `SUMMARIZE`, `REFRAME`,
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
`custom`. Custom content is the exact retained Memory text. `--accept` applies
the reviewed edits and removals to the frozen Source owners in place.

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
forgotten by an earlier pass.

A granted Criteria retains its exact READ authority binding and is revalidated
before Apply. A granted Source is rejected because new console Sever requires
ordinary local UPDATE/DELETE ownership. Query-only authority never becomes
ordinary Memory input.

### Study prewarm subset projection

The declared Task 3 `300 × 75` Sever artifact is also a basis for unchanged
subsets. Runtime lookup compares ordered `(Memory UID, owner name, content)`
ledgers, not raw root depth or descendant flags. Additions, edits, reordered
identities, cross-task inputs, in-place Source identity changes, and
configuration drift remain misses.

A projected review still contains exactly one candidate for every selected
Source Memory. If all Criteria cited by the prepared candidate survive, the
candidate is rebound unchanged. If cited support was removed, the projection
uses `KEEP_AS_WRITTEN`, exact Source content, and no criterion citation. This
is the conservative consequence of deleting a filtering rule; it avoids both
applying an absent rule and making an ungrounded replacement transformation.
The fresh review and candidate UIDs, `PROJECTED PREWARM` label, complete
coverage validation, authority checks, exact Source identity, and application
CAS remain mandatory.

## Persistence and application

A version-4 Sever session retains exact Source and Criteria frames, Context
identities and digests, granted bindings, one decision per Source Memory,
current manual selections, exact custom content, the grounded applied-summary
references, names of excluded query-only Context references, and per-owner
checkpoint receipts. Writes use a record-digest compare-and-swap. Versions 1
through 3 remain readable; new serialization emits version 4.

The terminal-independent application boundary owns that complete private
session lifecycle through `SeverSessionRepository`. Create and open return a
`SeverSessionSnapshot` with an opaque version token; candidate decisions and
persisted Apply consume that exact token. The Store
adapter alone interprets it as a record digest. CLI and TUI adapters therefore
cannot bypass CAS by directly saving a session or recomputing its digest.

New in-place workbenches omit `SAVE LOCATION`; visible topology proceeds from
Items to To Do because Source ownership already fixes every mutation location.
The destination-revision port remains only for reopening an older retained
other-save session.

Apply revalidates every local contributing Context under the save lock. For a
granted Criteria it also revalidates the frozen Profile and Grant identity,
revision, permissions, public/resource mapping, and complete projected frame
while the Grant registry is frozen. Sever groups decisions by their frozen
direct Source owner, maps them to exact EDIT/REMOVE operations, and asks
`application.operations.update.apply_update` for each detached post-image.
One Store batch then compare-and-sets every owner digest, preserves Context and
retained Memory identities, creates one checkpoint per owner, and records a
shared `command_contexts` membership list. A Source-subtree membership race or
stale Criteria leaves no partial Source update. Forgotten content and rationale
remain only in the Sever session. Because
provider dispositions already give every Source Memory one
complete treatment, the owning TTY skips the redundant review/approval
workbench when no user response remains and applies the in-place change
directly. An all-KEEP disposition is still a reviewed Sever application and
records the grouped command, including zero-change owner checkpoints.

The multi-Context Source batch and the private APPLIED session receipt are two atomic file
operations rather than one shared transaction. A synchronous receipt-save
failure re-reads the session before compensating. If the receipt actually
committed, Apply reports success; if the session is still the exact REVIEWING
snapshot, compensation restores every exact owner pre-image and removes only
the provisional Sever checkpoints. It refuses compensation when either durable
side changed. After a process interruption in the gap, retrying Apply recovers
the receipt only when every live Source owner, exact Sever checkpoint,
pre-image, grouped membership, and accepted session match.

Command Undo returns the saved session to `REVIEWING` and restores every Source
owner pre-image as one logical command unit. Redo reapplies every exact
post-image and restores the complete per-owner application receipt. The Context
and Sever-session halves are written with exception rollback and append the
ordinary undo/redo receipts. Older other-save sessions retain their exact
creation/archive Undo behavior for compatibility.

`mem review sever` reuses the same evidence and proposed after-state with Apply
removed. It cannot mutate a Source.

## Alternatives and limitations

- Granted-Source in-place mutation remains a deliberate non-goal until the
  operation has exact UPDATE/DELETE grant receipts for every affected owner.
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
