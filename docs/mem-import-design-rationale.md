# Resource import design rationale

## Motivation and vocabulary

Study preparation needs more than whole-store duplication. A researcher may
want a clean Profile, one ordinary Context or lexical subtree, or one directly
owned Memory from a registered source Profile. The command therefore borrows
Python's package/module/object shape while retaining memcommit's own semantics:

```bash
mem import profile pilot-copy --from-profile canonical-baseline
mem import context campus-wiki --from-profile canonical-baseline --recursive
mem import memory 2e9a18c3 --from-profile canonical-baseline \
  --context campus-wiki/routes --into participant/notes
```

Python import binds an object into a namespace. Memcommit cannot create a live
cross-Profile binding without defeating Profile isolation, so resource import
is an identity-preserving value transfer. It copies the selected durable
record, preserves Context and Memory UUIDs, records the local import operation,
and never establishes synchronization with its source. `branch`, grants, and
references remain separate lineage or live-access mechanisms.

## Command grammar

The explicit forms are:

```text
mem import profile NEW --from PATH
mem import profile NEW --from-profile SOURCE_PROFILE
mem import context SOURCE_CONTEXT --from-profile SOURCE_PROFILE
    [--as TARGET_CONTEXT] [--recursive]
mem import memory MEMORY --from-profile SOURCE_PROFILE
    --context SOURCE_CONTEXT [--into TARGET_CONTEXT]
```

`mem import NAME --from PATH` remains a compatibility spelling of `mem import
profile NAME --from PATH`. Options are type-specific and fail rather than being
silently ignored. Profile names are registry names. Existing source Context
operands support the shared `.`, `..`, `./...`, and `../...` lexical resolver,
using one source-current snapshot. `--as` names a new Context and is therefore
not passed through the existing-Context resolver. A Memory `--into` operand is
resolved once against the active Profile's captured current Context.

## Interactive setup

In a terminal, flagless `mem import` composes the shared flat-choice dialog,
Context/Memory tree picker, Context reach control, exact-name editor, and
exact-command review surface. Fully specified commands retain their stable
non-interactive behavior. Outside a terminal, flagless import fails with an
instruction to pass the resource kind and operands; it never guesses from
stdin or the active Context.

The setup first chooses `PROFILE`, `CONTEXT`, or `MEMORY`, then freezes a
name-only catalog of registered source Profiles. The active Profile is omitted
from that catalog rather than rendered as an unavailable row, and no candidate
store is opened merely to build the Profile list. Only after one non-active
source identity is selected may its ordinary Context names and Memory previews
be loaded. This keeps source discovery from mixing the active destination into
the same visible Profile namespace. Removed Profiles are omitted as well.

The TUI intentionally supports registered `--from-profile` sources only.
External filesystem intake remains the explicit `mem import profile ... --from
PATH` form: adding path completion or a terminal filesystem browser would be a
separate host-disclosure and portability decision. Cross-Profile export is also
not implied by this setup. Grants remain the live readable-access mechanism,
and `mem share` remains the bounded sender-to-receiver transfer mechanism.

Context setup reuses the source tree and the common exact-versus-descendant
control, then composes the shared Save Location parent browser with direct
exact-name input. Memory setup selects one directly owned Memory in the source
tree and one existing ordinary destination Context in the active Profile. A
Profile import edits one fresh exact Profile name. Every branch ends at an
`ExactCommandReview`. The completed review uses the repository-wide
final-action contract:
`Enter` approves, while `A` remains a compatibility alias. Because the
standalone review contains no other focusable action, Enter cannot be confused
with setup navigation; Escape or Q still cancels without applying the plan.

Interactive browsing holds no store or registry lock while waiting for input.
Immediately before review, Context and Memory setup creates a typed import plan
containing the selected source and destination Profile UIDs, canonical Context
names and UIDs, record digests, Memory content digest, mapped destination set,
and displayed counts. Apply reacquires the existing registry, graph, record,
and CAS boundaries and requires the newly prepared plan to equal the reviewed
plan before publishing anything. A Profile import similarly revalidates the
selected source Profile UID under the registry lock. This rejects an active
Profile switch, source edit, target edit, rename, removal, or identity change
that occurs while the person is reviewing the command; the TUI must be reopened
instead of silently applying to newer state.

The ordered 180×52 color PTY evidence for all three branches, cancellation,
receipts, and read-only verification is recorded under
[`screenshots/mem-import-tui-20260813/`](screenshots/mem-import-tui-20260813/).

## Profile import

Profile import creates a fresh managed Profile around a clean content baseline.
The active Profile and source remain unchanged. Import from another registered
Profile records its Profile UUID and name, not its internal filesystem path.
External import records no source path.

The baseline allowlist contains only:

- `state.json`, including the template-selected current Context;
- every ordinary `contexts/**/context.json` record;
- supported `query-sources/` records; and
- declared `translation-views/` records.

It excludes Context checkpoints; undo/redo receipts; query, Ground, Meld, or
Atomize sessions; caches; staged updates; locks; lifecycle ledgers; and
write-protection state. The admitted files are digested before and after copy
and at the staged destination. An allowlist was selected so a newly introduced
runtime artifact cannot silently enter a participant baseline.

`mem profile import` remains the explicit archival whole-store copy, including
history. `mem profile import-study` first composes the generated task packages
into one editable `study-baseline`; `mem init-study` then snapshots that live
Profile through the same clean Profile-level primitive, publishing one ordinary
Profile with the complete baseline topology in one atomic registry update.

## Context import

Context import writes into the active Profile without switching either Profile
or current Context. The default imports exactly the named Context record.
`--recursive` freezes and imports the source's lexical root and descendants.
`--as` replaces that root name and applies the same suffix mapping to every
selected descendant. Context and Memory UUIDs are not regenerated.

The selected set must be closed under persisted Context and Memory references.
Internal reference names are rewritten through the same root mapping. A
reference outside the set fails before any destination write, as does a
query-only reference. This prevents a copied record from accidentally resolving
against a different Profile and prevents ordinary import from bypassing an
authority grant or copying concealed query material. Importing the encompassing
Profile or using the existing grant boundary remains explicit.

Every destination name must be new, and no selected Context UUID may already
exist under another destination name. The store creates the batch under its
command, graph, Context, and write-protection boundaries with exception
rollback. Each new Context receives a local automatic checkpoint whose arguments
identify the source Profile, Context UUID, source digest, mapping, and recursive
choice. Source checkpoint history itself is never copied.

## Memory import

Memory import accepts an exact UUID or unambiguous prefix for a directly owned
Memory in the named source Context. It appends an exact UID/content copy to the
existing `--into` Context, or to the active current Context when `--into` is
omitted. A same-UID direct item in the target fails without replacement. The
destination save uses normal optimistic concurrency, write-protection, and
automatic-checkpoint behavior, with source identity and digest in the receipt.

Context and Memory resource import currently require a different registered
source Profile. Same-Profile duplication is deliberately left to Context
branching and ordinary Memory operations, avoiding a command whose identity
semantics would change depending on whether two names happened to share a
store.

## Concurrency and atomicity

The Profile registry is frozen during Context and Memory transfer, so Profile
selection and source identity cannot change mid-command and reciprocal imports
cannot deadlock each other. Source Context graph and record locks remain held
from snapshot through destination publication. Recursive membership therefore
cannot change after validation. The destination uses its normal locks and CAS
boundary; multi-Context creation preflights all names and rolls back every newly
created Context on an exception.

Profile import stages outside the registry and publishes the store plus registry
entry atomically. It rechecks the source baseline digest around the copy.

## Rejected alternatives and limitations

- Overloading `--from` with both a path and Profile name was rejected because a
  local path can have the same spelling as a Profile.
- Copying then deleting known runtime directories was rejected because a new
  artifact could be missed.
- Regenerating UUIDs was rejected because repeated study runs need stable
  stimulus identity. A future explicit copy/fork operation may choose new IDs.
- Automatically following arbitrary references was rejected because it makes
  scope and authority transfer invisible.
- Query-only references are not imported at Context granularity; use a clean
  Profile import or an authority grant.
- Import does not provide refresh, merge, upstream synchronization, replacement,
  or removal. A baseline digest proves what was copied, not that its claims are
  correct or appropriate for a study.
