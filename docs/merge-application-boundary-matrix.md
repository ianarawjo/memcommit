# Merge application-boundary matrix

## Status

The conflict-aware direct and path-aligned recursive Merge contracts are
implemented and verified through one terminal-independent typed
Application/Runtime boundary. The public CLI exposes explicit `--direct` and
`--recursive` reach, positional `SOURCE [TARGET]`, compatibility
`--from SOURCE`, equivalent `--into TARGET`/`--to TARGET`, and complete per-item or bulk
deterministic decisions. Bare `mem merge` opens the Source/Target setup. A decision-free local
plan applies immediately through the normal checkpointed application boundary;
a decision-free granted-authority plan retains final review, and a
conflict-bearing plan opens the shared Resolution workbench. Every path applies
the same frozen typed plan. Conflict review now presents every complete Source
and Target value inline, stages `KEEP TARGET` for every row at entry, and keeps
Apply visibly ready while allowing row-level or whole-set arrow selection.

## Motivating distinction

`mem merge SOURCE [TARGET]` remains deterministic, provider-free, and distinct from a
Git-style three-way merge or semantic reconciliation. It now classifies every
frozen Source item as `NEW`, `UNCHANGED`, or required `CONFLICT`. Conflicts are
limited to exact structural choices: keep the Target member or take the Source
member. It still does not invent combined content or propagate Source absence.

The descendant form is a path-aligned recursive union. Because that behavior
requires multi-Context authority, planning, and persistence, the existing
single-Context contract remains independently reproducible through the same
application boundary.

## Characterized direct contract

| Concern | Current owner | Frozen behavior |
| --- | --- | --- |
| CLI input | `commands.merge` | One existing Source locator and optional positional Target locator; `--from` aliases positional Source, `--into` and `--to` alias Target, and omitting Target uses the command-start current Context. Supplying a role more than once fails before Store access or current-Context capture. |
| Locator meaning | `MemoryStoreMergePort` and authority access | Source and Target are resolved from one captured current-name snapshot. |
| Authority | Grant-aware access and derived-transfer policy | Source requires `READ`; Target additions require `CREATE`; `TAKE SOURCE` replacement also requires `UPDATE`; cross-domain transfer enforces its derived permissions. |
| Write protection | Store policy frozen during planning and revalidated during persistence | A protected Target Memory or Context removes `TAKE SOURCE` before the decision UI; a protected Context blocks unconditional additions before review; concurrent policy changes still fail closed at Store save. |
| Source projection | Store runtime | A cross-Profile Source exposes direct Memory values only; pointers are not copied across Profiles. |
| Domain planning | `merge_planning` | Classify every direct Source item without mutation and materialize only a complete validated decision set. No descendant traversal occurs here. |
| Existing occurrence or lineage | `merge_planning` plus checkpoint lineage | An equal UID or one-to-one validated same-Store Branch/Merge lineage selects the existing Target occurrence. Equal type/value is `UNCHANGED`; different Memory content is `CONTENT_DIVERGENCE`; unlike types are `TYPE_COLLISION`. A genuinely new Memory is added under a fresh Target UID. Target no longer wins silently. |
| Source absence | `ops.merge` | Never removes a Target item. Deletions are not propagated. |
| Pointer collisions | `merge_planning` | Duplicate/incompatible logical references become `REFERENCE_COLLISION`; incompatible Context-like names become `PLACEMENT_COLLISION`. |
| Freshness | Store runtime and Store transaction | Source name, UID, and direct-record digest are revalidated; Target save uses UID/digest compare-and-set. |
| Persistence | `save_context_with_sources` | One Target Context and one automatic checkpoint are published under the Source/Target lock set. Same-Store ordinary transfers also record exact Source-to-result Memory lineage under the Merge operation UID. |
| Result | typed application receipt and adapters | Separately reports `NEW`, `ALREADY PRESENT`, `KEPT TARGET`, `TOOK SOURCE`, created Contexts, whether the Target changed, and checkpoint boundaries; verified no-ops still record a receipt. |

## Extracted ownership

| Callable | Layer | Responsibility |
| --- | --- | --- |
| `MergeRequest`, `FrozenMergePlan`, `MergeConflict`, `MergeResolution`, `MergeResult` | Application contract | Typed locator/reach input, mapping-qualified conflict identity, deterministic decision, reviewed binding, and durable result without Store or terminal objects. |
| `merge_resolution_case`, `prepare_merge`, `resolve_merge_conflicts`, `run_merge` | Application | Project the frozen structural requirements through the operation-neutral Resolution contract, validate before Store access, require complete exact decisions, and require the final receipt to match the frozen plan. |
| `MemoryStoreMergePort` | Infrastructure/runtime | Capture current once; resolve authority; project cross-Profile input; freeze Source/Target digests; revalidate and checkpoint atomically. |
| `execute_merge` | Internal Python runtime | Invoke the same use case with no stdout, stderr, prompt-toolkit, or provider dependency. |
| `render_merge_plain` | Plain CLI adapter | Use the same disposition counts as the TUI receipt, so a retained equal/conflicting identity is not misreported as merely “added nothing new.” |
| Merge endpoint setup | Interactive adapter | Select a readable Source, a local or CREATE-authorized Target, and one coupled direct/recursive shape from separate frozen catalogs. The command-start current Context is only the initial Target. Either endpoint may temporarily select the same row; Continue rejects that completed draft. Returns only a typed request. |
| Merge frozen-plan review | Interactive adapter | Project a decision-free granted-authority plan and apply only that exact plan after explicit approval. Local decision-free plans skip this duplicate approval because the complete command checkpoint supports Undo/Redo. |
| Shared inline deterministic Resolution workbench | Interactive adapter | For conflict-bearing plans only, render complete Source/Target values in frozen order, stage Target defaults, compose row and bulk arrows with one always-visible Apply action, retain exact final review, and show a typed receipt without a Viewer or `commands.*` import. |
| `commands.merge.cmd` | Typer composition boundary | Parse argv or route a bare TTY invocation, compose Store runtime, translate expected failures to CLI exits, and invoke the presenter. |

`MergeReach.DESCENDANTS` uses the same typed request and result. Its result
contains one ordered `MergeContextResult` and one checkpoint UID for every
Source-relative Target path, while direct contains exactly one of each.

## Inline conflict review and decision provenance

The visible conflict list is the complete decision surface. Each row contains
the stable abbreviated item UID, the full Source value, the full Target value,
and exactly one checked disposition. Memory content is never shortened with an
ellipsis. Values taller than the viewport use the shared cursor-backed wrapped
read pane, so `PageUp` and `PageDown` traverse from the first Source byte
through the last Target byte. A forbidden `TAKE SOURCE` remains visible as
unavailable evidence rather than disappearing; authority still determines the
selectable vocabulary.

Every row begins at `KEEP TARGET`. This is a real staged outcome, not only
initial keyboard focus, so Apply is ready from the first frame. The independently
scrollable `CONFLICTS` frame and fixed `CONTROLS` frame are separate shared focus
Surfaces: one `Tab` reaches Apply regardless of conflict count, `Shift-Tab`
returns to the retained conflict cursor, and vertical boundary traversal still
crosses naturally between the last conflict and the first control. The Controls
cursor starts on Apply; `Up` reaches the adjacent `BULK DECISION` row containing
`KEEP ALL TARGET / TAKE ALL SOURCE`. `Left`/`Right` immediately stages the
visible side for one conflict or selects the focused bulk strategy, and Enter
on Bulk applies that strategy to the frozen rows before returning to Apply.
The bulk check is derived from all visible row decisions: uniform Target or
Source choices automatically light the matching side and select the compact
whole-set command, while a mixed set lights neither. It therefore summarizes
the same staged state instead of introducing a second hidden selection.
Enter on Apply opens one exact whole-set command review; a second Enter crosses
the existing mutation approval boundary. Closing or stale-plan failure
publishes no Target change.

The process-local checked state is disposable, but the reviewed outcome is
not. Every Merge checkpoint stores a version-1 `merge_decisions` record with
the conflict UID, conflict kind, decision, Source/Target names, Source UID, and
Target UIDs. Memory bodies are not duplicated in checkpoint arguments because
the checkpoint already binds the operation images. This makes a no-delta
`KEEP TARGET` merge explainable later while keeping the normal Merge
checkpoint and Undo/Redo contract intact.

## Conflict-aware verification gate

The implementation preserves and verifies all of the following:

- local Memory, MemoryRef, QueryContextRef, and embedded-Context union;
- exact equality as `UNCHANGED` and explicit resolution for divergent equal or
  checkpoint-related occurrence UIDs;
- non-propagation of Source deletion and lexical descendants;
- idempotent repeated execution with one checkpoint per successful command;
- required reference/placement conflicts without partial mutation;
- same-Context rejection at reviewed-result and runtime boundaries rather than
  by hiding the Target in the Source picker; relative-locator behavior, Source
  freshness, and Target compare-and-set;
- Grant permissions and cross-Profile Memory-only projection; and
- existing exit status and stable line-oriented terminal structure, including
  complete conflict bodies outside a TTY.

Focused characterization lives in `tests/test_merge_characterization.py` and
is supplemented by the existing operation, CLI, integration, Grant, reference,
order, query-only, and concurrency suites.

## Descendant contract

The descendant form aligns lexical descendants by their complete relative path
from the two selected roots. Matching paths receive the same complete
classification/resolution rule, Source-only paths become fresh Target-owned Contexts,
and Target-only paths remain unchanged. A leaf name alone is never sufficient
to match Contexts under different parents.

The complete Source and Target lexical membership, every Source record, every
existing Target identity/digest, every require-new Target path, and every
write-protection decision are checked before publication. All Target writes
share the Store command lock, exclusive graph lock, and deterministic Context
lock set. An exception restores prior Context bytes, removes new checkpoints,
and deletes only the fresh Context identities created by the transaction.

Source-only Contexts receive fresh Context identities, and their direct Memory
additions receive fresh Target occurrence UIDs. Same-Store internal Context and
MemoryRef pointers are remapped to corresponding Target identities;
cross-Profile recursive Merge copies direct Memory values only, matching the
existing direct transfer boundary. A granted Target may update existing
CREATE-authorized descendants but cannot create a missing authority Context.

The internal `execute_merge()` callable verifies local matching,
Source-only creation, Target-only preservation, complete-relative-path
alignment, granted recursive Source projection, membership freshness, and
exception rollback. `mem merge SOURCE TARGET --recursive` exposes that
behavior non-interactively. Bare `mem merge` starts with Source focused,
exposes direct and recursive as coupled operation shapes, and starts selectable
Target B at the command-start current Context. Continuing from setup does not mutate state:
`prepare_merge()` first freezes the complete plan, and a second screen shows
every Context mapping, creation decision, addition identity, and checkpoint
count. Only Enter on that exact frozen-plan review invokes `run_merge()` with
the same plan. Outside a TTY, omitting Source fails with a stable instruction
instead of attempting a full-screen UI.

## Interface verification

The focused automated gate covers direct and recursive typed results,
explicit `--from`/`--to` including a relative Source, `--into` without a current Context, recursive CLI path creation,
conflicting reach flags, non-TTY routing, independently frozen readable Source
and CREATE-authorized Target catalogs, selectable Target return, coupled reach
traversal, setup-only continuation, complete frozen-plan projection, exact-plan
application, cancellation, authority, freshness, rollback, checkpoints, and
operation-unit Undo/Redo.
The earlier decision-free terminal evidence is recorded under
`docs/screenshots/mem-merge-recursive-tui-20260814/` at 180×52 with color ANSI
verified. It demonstrates typed Help, direct root-only mutation, recursive
Source-only path creation, Target-only descendant preservation, durable
receipts, a zero-mutation cancellation path, and a pre-persistence failure
that remains reviewable without publishing a receipt or partial state.

The conflict-aware evidence is recorded under
`docs/screenshots/mem-merge-conflict-resolution-20260815/`, also as verified
180×52 color PTY streams and rendered canvases. Its ordered log covers
item-level selection and clearing, exact individual and fused bulk reviews,
recursive multi-mapping replacement and creation, operation-unit Undo/Redo,
cancellation, stale-plan rejection with no partial Target publication, and a
verified no-op receipt/checkpoint. It also records a protected Memory exposing
only `KEEP TARGET` and a protected Context rejecting an unconditional addition
before review.

The focused picker-boundary evidence under
`docs/screenshots/revert-inline-version-selection-20260820/` shows the current
Target selected as Source A, the completed same-Context draft rejected at
Continue, and read-only verification that neither Context nor checkpoint
history changed.

The selectable-Target evidence under
`docs/screenshots/mem-merge-target-selection-20260820/` records the initial
current Target, alternate B selection, selected-target conflict review,
reproducible `--into target-selected` approval, successful application without
switching global current, and same-endpoint rejection with no partial state.
The refreshed inline conflict evidence under
`docs/screenshots/mem-merge-compact-conflict-resolution-20260820/` records the
default-ready Target state, individual and bulk arrow choices across multiple
conflicts, exact approval, disposition-aware receipts, read-only verification,
stale-plan atomic failure, protected-Memory choice narrowing, cancellation,
and complete traversal of two 60-line Memory values in a real 180×52 color
PTY.

The focused Source-only replay under
`docs/screenshots/mem-merge-source-only-actual-20260820/` starts with an empty
Target, runs the explicit real Merge command, and then uses `mem show` to
verify that the Target contains all Source lines with one checkpoint. That
capture predates fresh Target occurrence UIDs and therefore remains UI-flow
evidence, not evidence for the current identity rule. Current automated
coverage verifies that a new addition has a distinct Target UID and a recorded
lineage edge. This distinguishes content copied by Merge from synthetic
scroll-boundary fixture text without treating identity as ancestry.

The scale replay under
`docs/screenshots/mem-merge-150-conflicts-actual-20260820/` lets the real Merge
planner produce 150 content-divergence conflicts from 150 shared identities.
It records one-key Tab traversal from both the first and final conflict
viewports into the separate Controls frame, a 150-row bulk Source decision,
exact review, one atomic checkpoint, and read-only verification of every
resulting Target body.

An isolated Study Task 1 application-policy replay additionally exercised 11
direct additions, a verified no-op, one content conflict, exact `TAKE SOURCE`,
and a seven-Context/75-Memory recursive application with complete Undo/Redo.
After recursive Undo, read-only inspection correctly found the removed local
descendant absent but reported it as a missing `Granted view`. That wording is
a separate Context-locator/presentation defect; the lifecycle archive and
operation-unit restoration were correct, so it does not broaden Merge's Apply
boundary.

The complete in-progress repository state passed 212 focused policy, Merge,
restoration, protection, authority, reference, and adapter tests plus 33 Help
tests. A separate clean checkout of this Merge commit passed all 53
terminal-independent Application, Runtime, operation, and Resolution-adapter
tests. CLI-bearing test collection in that clean checkout remains blocked by
an unrelated parent-commit import mismatch: `quality_audit` imports
`QualityFindSourceFrame`, which the committed `quality_find_workbench` does not
yet export. This Merge did not change either module; the wider in-progress
worktree already contains their pending matching changes. The distinction is
recorded so the broader passing count is not mistaken for a clean-HEAD CLI
gate.

The TUI's `ALL READABLE CONTEXTS` label is a Profile-wide contract, not a
command-local union of Store names and Grant rows. Its setup therefore freezes
the shared Profile readable catalog, retains ordinary local and exact
READ-granted public names, and excludes QUERY-only routes that Merge cannot
materialize. Source selection only establishes readability; operation-owned
DERIVE, EXPORT, and write authority remains enforced when the typed request is
frozen and applied.

## Restoration boundary

Every affected Context retains a normal Merge checkpoint for Diff, History,
and provenance. Version-2 Merge checkpoint metadata binds every direct or
recursive member to one operation UID and records which Target Contexts were
created. Its sibling version-1 `merge_decisions` record retains every reviewed
conflict disposition without duplicating Memory content. For ordinary
same-Store transfer, a sibling version-1 `memory_lineage` record binds each
Source occurrence to its exact Target post-image using Context/Memory UIDs and
content digests. Merge validates retained receipts against their owning
automatic checkpoint and resolves only a one-to-one current mapping; malformed,
copied, one-to-many, or many-to-one evidence fails before Target publication.
Grant-derived and cross-Profile transfers deliberately do not publish this
local lineage because their authority and disclosure boundaries differ. Undo validates the complete post-image, restores every updated
Context, and moves every created Context plus its history into private
validated lifecycle archives under one command/graph/lock boundary. Redo
validates the complete pre-image, restores the archived identities and
histories, and reapplies every update. A failure rolls back the complete
attempt; partial tree recovery is never published. A verified zero-delta local
Merge skips duplicate review but still passes through normal application,
records its command checkpoint, and remains an Undo/Redo boundary so it cannot
permanently conceal an earlier mutation.

## Intentional non-goals

- No common-ancestor or three-way change analysis.
- No automatic propagation of edits or deletions; an edit occurs only through
  an explicit `TAKE SOURCE` conflict decision.
- No semantic duplicate or conflict reconciliation; Meld owns that behavior.
- No provider or Fit call in structural conflict resolution; the shared
  Resolution contract supplies identity, legal-choice, and required-coverage
  mechanics rather than a universal solver.
- No traversal of embedded Context graphs as if they were lexical descendants.
- No partial publication when one descendant fails validation.
- No recursive Merge between overlapping local Source and Target namespaces.
- No persisted cross-launch decision drafts yet; current choices remain
  process-local and are invalidated with their frozen plan.
