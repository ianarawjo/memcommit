# Adaptive Review reports

## Goal

`mem review` is the common host for inspecting an operation's already-created
semantic report and, when that operation supports it, recording review
responses. Review does not plan an Update, compute Impact, approve an exact
Ground command, or apply any target mutation.

The motivating Update report already contains useful exact material:
operation, owner, Memory UID, before/after content, reason, and source
references. The first rollout preserves that format instead of blocking the
common contract on a report redesign.

## Contract

An operation supplies a revision-bound `ReviewReport` with:

- operation, artifact UID, and revision identity;
- one adaptive report kind;
- title and summary;
- an optional existing `ResolutionWorkbenchView`; and
- optional exact report text, used by saved Compare and symmetric Meld.

`ReviewReportController` reloads or re-projects this report. When adapting a
Resolution Workbench view it removes `ACCEPT` and clears `accept_enabled`, but
retains semantic response capabilities such as item or whole-set comments.
Constructing a report that still exposes Accept fails closed.

## Adaptive operation reports

| Operation | Kind | Report and response behavior |
| --- | --- | --- |
| Compare | `READ_ONLY` | Exact saved equal-authority Compare prose; browse and close only. |
| Meld | `RESOLUTION` | Compare or directional assessment, issues, and proposed Memories; existing Meld turns may be recorded, but target application is unavailable. |
| Sever | `CONTENT SEVERING` | Source/Criteria evidence and the proposed local Result; existing item decisions may be saved, but Result materialization is unavailable. |
| Atomize | `CLARIFICATION` | Findings and saved clarifications; the existing Atomize workbench remains its response controller. |
| Update | `CHANGE_PLAN` | Existing exact ADD/EDIT/REMOVE blocks, reasons, owners, and source references; read-only. |

## Common terminal grammar

Adaptive Review reports now use one shared two-frame host even though their
rows remain operation-specific. The lower `Items` frame receives initial
focus. Its first row is the complete report, followed by adaptive rows such as
`CONFLICT`, `DISCLOSURE`, `ATOMIZE UNCERTAINTY`, or `ADD`; token underscores
are rendered as spaces rather than leaking persistence notation into the UI.

`Enter` opens the selected row in the upper `Viewer`. `Tab` moves between
`Items`, `Viewer`, and an item composer when one exists. `Up` and `Down` move
only the currently focused surface, and closing the view never implies a
response or application. The report reading surface consistently presents
the operation title and identity, `WHAT MEM UNDERSTOOD`, `REVIEW ITEMS` and its
count, individual adaptive item summaries, and the operation-owned result
heading. Item details retain their operation-owned evidence blocks. The
`REVIEW ITEMS` label is applied only by the Review projection; adapters keep
their native list labels for owning-operation screens.

The host and standalone Compare now share the same process-local
`SessionWorkbenchNavigation`. Viewer stops are addressed by stable semantic
section IDs rather than report offsets, so an operation-specific result or
Impact section can be inserted without changing which section is focused.

Atomize previously combined a separate result browser with a separate
clarification workbench. Review now preserves the immutable
`WHAT HAPPENED`, unresolved, and representative/boundary-case report verbatim,
then uses the common host for its durable clarification choices and comments.
This avoids losing analysis evidence merely to normalize navigation.

Ground is deliberately absent. Its dialogue and exact-command receipt are not
semantic report review. Impact is also separate: Review explains the saved
artifact, while Impact shows the exact effect adjacent to a later Apply
boundary.

## Session boundary

A picker returns only an operation kind and exact artifact receipt. It does
not carry a trusted report body. After selection, the operation catalog reloads
and revalidates the authoritative Compare, Meld, or Sever artifact before its
adapter constructs a report. Update uses its validated singleton staged or
Impact record. Atomize remains Context-bound and revalidates its analysis and
workbench through the existing path.

Outside a TTY, multiple saved artifacts require `--session UID`; a sole
artifact may be rendered directly. In a TTY, the shared SessionPicker chooses
the operation artifact before Review opens.

## Invariants

- No Review report exposes `ACCEPT` or `APPLY`.
- Closing or finishing Review never applies a Context mutation.
- Review may save operation-owned responses and may request operation-owned
  reassessment, but the resulting artifact still requires a separate Impact
  and Apply boundary where that operation supports application.
- Report identities are revision-bound and adapter views must match them.
- Existing provider schemas, response persistence, CAS, locks, provenance,
  checkpoints, and application remain operation-owned.
- Update's detailed report is preserved before attempting presentation
  normalization.
- Review ends at close or at an operation-owned saved response. It does not
  automatically transition into Impact; that remains an explicit standalone
  or owning-operation surface.

## Alternatives rejected

Treating Impact as Review was rejected because an effect receipt answers a
different question and is adjacent to application. Reusing Apply as a Review
action was rejected because it would make a non-applying report host an
authorization boundary. One universal durable Review session was rejected
because Compare, Meld, Sever, Atomize, and Update retain incompatible artifact
and response lifecycles.

## Current limitation

The five adaptive reports now share focus and report-section grammar, while
their semantic row kinds, exact evidence blocks, and response lifecycles remain
operation-owned. Atomize still retains its newer workbench and legacy
`ReviewSession` compatibility path. Consolidating those persistence paths is a
later change and is intentionally separate from visual normalization.
