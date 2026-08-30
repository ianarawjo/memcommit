# Read Report lifecycle design rationale

## Motivation

Summarize, Trace, Rationale, the three quality Find operations, and Dedun's
shared discovery phase all produce read-only reports before any later action,
but their interactive entry paths had diverged. Trace and
Rationale reused the saved-session picker for content-free navigation history,
Summarize opened its Context workbench directly, and the finders always opened
fresh target setup. That made visually similar operations imply different
lifecycle concepts and made the session-shaped recent adapter carry executable
argv even though a recent report is not a durable session.

## Shared lifecycle

The common lifecycle is now:

```text
optional content-free Recent or Select Target
  -> operation-owned Context/Memory/range selection
  -> freeze and authorize the exact source
  -> operation-owned cache/provider/read execution
  -> read-only Viewer, compact receipt, or Resolution-style report
  -> content-free completed-attempt metadata
  -> close without Context mutation
```

That launcher is optional navigation, not the default meaning of every
operand-free command. Summarize has a complete current-Context/direct request
even when no Context operand is written, so its ordinary invocation executes
immediately. Its former presentation-mode workbench launcher is retired; a
future target-selection route would need its own explicit operation contract.
This matches the broader rule that executable argv does not open full-screen
setup implicitly.

`ReadReportTarget` is the interface-independent identity joining those steps.
It records only the canonical operation name, effective readable Context names,
explicit target roots, one-versus-many selection mode, direct/recursive range,
Profile selection, and an optional Memory UID for Trace/Rationale. It cannot
contain report prose, Memory content, provider output, cache artifacts, argv,
callbacks, or mutation receipts.

## Recents are navigation, not sessions or cache

Completed command attempts retain `read_report` metadata. A launcher row is a
content-free route back to the operation-owned execution path; opening it
reloads the attempt and requires the exact metadata to remain unchanged before
the operation revalidates current readable targets and permissions. It does not
reopen a report snapshot, restore reviewer responses, or prove that current
Context content matches the previous run.

Hidden semantic caches remain separate. A rerun may obtain an exact,
equivalent, or operation-approved projected cache hit only after its normal
authority and frozen-evidence checks. The recent record neither contains a
cache key nor grants cache eligibility. Quality Find reports do not own
response drafts at all, so Recents reconstruct only their target identity.

Legacy Trace/Rationale `memory_report` metadata remains readable. New Memory
report attempts also publish the generic shape so both operations use the same
launcher as Summarize and Find without breaking existing attempt ledgers.

## Presentation ownership

`interfaces.tui.workbenches.read_report` projects content-free recents through
the neutral Operation Launcher and returns only a `ReadReportTarget` or a
Select-Target action. It does not own target trees or result documents:

- Summarize executes one direct/recursive request and prints one result; its
  former Context Summary workbench remains component-level code.
- Trace prints its bounded temporal lineage directly; its former receipt/detail
  indirection and Viewer switch are retired.
- Rationale retains its whole-Trace, example-calibrated natural-provenance
  synthesis and compact terminal receipt; its legacy current-purpose inference
  fields remain JSON compatibility data only.
- Ambiguity and Conflict retain explicit `--select` multi-target/Profile setup
  and compact process-local read-only finding browsers. Their questions and
  possible readings remain evidence rather than answer controls. Exact
  Duplicate and complete-DUN
  Redundancy are direct one-Context reports in both TTY and non-TTY execution;
  neither exposes an initial selector. Dedun is an applying command rather
  than a report viewer.

Find Redundancies and Dedun intentionally have distinct execution identities
even though they share one analyzer. The finder closes with read-only evidence.
Dedun treats invocation as new Apply intent, uses one exact current or explicit
Context, and writes detailed evidence into the resulting checkpoint. It never
replays a recent report target, so report navigation cannot broaden into
mutation authority.

Find Duplicates is likewise an independent read-only operation, not a spelling
of Find Redundancies. Its attempt and report metadata use `find-duplicates`
exactly and describe a provider-free exact-DUP frame. Cross-annotation between
the two operations is rejected so history cannot reopen broader semantic
analysis under an exact-only label, or vice versa.

This is composition rather than one universal report model. The operations
share launch and lifecycle identity while preserving different evidence,
viewer, clipboard, authority, cache, and handoff semantics.

Trace and Rationale interpret their launcher's `Select Target` action as the
command-start current Context, not as a request for a second Profile-wide
location picker. Their operation-owned target tree immediately shows that
Context's Memories with exact reach and keeps `INCLUDE DESCENDANTS` available.
Another root remains available through explicit `--context`; Recents continue
to reopen their exact recorded target.

The Profile/Store orientation above the launcher is also operation-neutral.
Its command adapter matches the frozen Store root against the Profile registry
rather than importing an operation-owned saved-session catalog or trusting a
separately mutable active-Profile pointer. The location formatter is now owned
directly by the shared operation launcher component.

## Safety and compatibility boundaries

- Failed, interrupted, or still-running attempts never appear in Recents.
- Repeated identical targets collapse to the latest completed attempt.
- A selected recent is reloaded before use; replacement or removal fails
  closed and returns the person to a fresh invocation.
- Effective Context names remain explicit. Find execution does not apply a
  second hidden descendant expansion that could restore an unchecked row.
- `PROFILE` is one exclusive virtual target, not an ordinary root plus a
  marker. Replaying it expands the newly frozen readable catalog at request
  construction, so newly readable or removed Contexts follow current
  authority. Non-Profile recents retain their exact previously checked set and
  never acquire a newly created lexical descendant implicitly.
- No recent selection mutates global current Context or creates a saved
  analysis/session record.
- Ordinary current-Context and explicitly targeted Summarize routes execute in
  the primary terminal flow; no presentation-mode launcher remains.

## Intentional limitations

The command-attempt ledger currently provides process/Profile-local navigation
history rather than a versioned public recent-report API. Recents do not retain
the old source digest and therefore cannot render an old report without rerun.
Audit remains a durable review operation rather than joining this sessionless
family. Compare remains a saved latest-analysis lifecycle. These distinctions
are intentional and should not be erased merely because all three can display
read-only documents.
