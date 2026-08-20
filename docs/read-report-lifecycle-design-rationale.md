# Read Report lifecycle design rationale

## Motivation

Summarize, Trace, Rationale, Dedun's discovery phase, and the two quality Find
operations all produce read-only reports before any later action, but their interactive entry paths had diverged. Trace and
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
  -> read-only Viewer or Resolution-style report
  -> content-free completed-attempt metadata
  -> close without Context mutation
```

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
cache key nor grants cache eligibility. Likewise, quality-finder response
drafts remain process-local and are not reconstructed from Recents.

Legacy Trace/Rationale `memory_report` metadata remains readable. New Memory
report attempts also publish the generic shape so both operations use the same
launcher as Summarize and Find without breaking existing attempt ledgers.

## Presentation ownership

`interfaces.tui.workbenches.read_report` projects content-free recents through
the neutral Operation Launcher and returns only a `ReadReportTarget` or a
Select-Target action. It does not own target trees or result documents:

- Summarize retains its Context Summary workbench and direct/recursive/Both
  result contract.
- Trace retains the temporal history explorer and exact Memory lineage.
- Rationale retains its recorded/inferred evidence document and provider rules.
- The quality-analysis family retains its multi-target/Profile setup and
  process-local Resolution report, including typed Resolve and semantic Dedun
  evidence routes.

This is composition rather than one universal report model. The operations
share launch and lifecycle identity while preserving different evidence,
viewer, clipboard, authority, cache, and handoff semantics.

The Profile/Store orientation above the launcher is also operation-neutral.
Its command adapter matches the frozen Store root against the Profile registry
rather than importing Ground's saved-session catalog or trusting a separately
mutable active-Profile pointer. The legacy Ground location helper remains only
as a compatibility projection over that neutral value.

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
- Plain and explicitly targeted CLI routes retain their existing behavior.

## Intentional limitations

The command-attempt ledger currently provides process/Profile-local navigation
history rather than a versioned public recent-report API. Recents do not retain
the old source digest and therefore cannot render an old report without rerun.
Audit remains a durable review operation rather than joining this sessionless
family. Compare remains a saved latest-analysis lifecycle. These distinctions
are intentional and should not be erased merely because all three can display
read-only documents.
