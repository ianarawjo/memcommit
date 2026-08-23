# Terminal UI integration roadmap

## Goal

Make Mem's durable semantic operations feel like one terminal system without
turning them into one semantic session. Meld, Compare, Update, Ground, and
Sever should share appropriate launcher and workbench surfaces. Impact and
Review must remain useful as standalone commands while also becoming reusable
operation functions that an owning TUI can present in place.

Atomize is intentionally deferred from the first rollout. Its existing use of
the common workbench remains a compatibility constraint and a later migration
target, not a reason to make the first integration slice larger.

## Current implementation audit

There are already two different common terminal layers. They must not be
described as one TUI:

| Operation | Bare entry / saved-work route | Active work surface |
| --- | --- | --- |
| Ground | Shared `SessionPicker` when saved Grounds exist; otherwise the new-Ground flow | Dedicated blank and named Ground shells |
| Meld | Bare role-based setup; shared `SessionPicker` only with `--sessions` | Shared `ResolutionWorkbench` through the Meld adapter |
| Compare | Bare A/B setup; shared `SessionPicker` only with `--sessions` | Dedicated read-only Compare workbench |
| Update | Bare Source/Target setup; shared singleton `SessionPicker` only with `--sessions` | Update adapter and shared `ResolutionWorkbench`; saved receipt rendering is currently snapshot-oriented |
| Sever | Bare dedicated setup; shared `SessionPicker` with `--sessions` in a TTY and stable plain listing outside one | Shared `ResolutionWorkbench` through the Sever adapter |
| Atomize | Shared picker only with `--sessions`; bare invocation is current-Context create/resume | Shared `ResolutionWorkbench`, plus operation-specific result and grounding surfaces |

The shared picker is a read-only launcher, not an active-session pointer. The
shared Resolution Workbench is a presentation and UID-addressed action
boundary, not a shared provider schema, persistence format, or mutation
transaction.

The active workbenches now additionally share `SessionWorkbenchNavigation`.
It owns Items/Viewer/Composer focus, selected row, and stable semantic Viewer
section identity. Standalone Compare retains its relation-specific renderer
and follow-up actions but no longer carries a separate focus and scroll state
machine. The exact contract is recorded in
`session-workbench-navigation-design-rationale.md`.

New-session endpoint collection now has a shared presentation boundary.
Compare, Update, and Meld compose independent instances of the shared Context
namespace tree inside one role-based setup shell. Meld adds a common horizontal
selector for its directional/symmetric authority mode, and Sever's
exact/subtree scope rows reuse that same small selector inside Sever's existing
three-role shell. The common setup returns process-local role state only,
while operation adapters retain typed receipts and every authority, freshness,
and mutation check. The detailed contract and remaining Sever-shell rollout
are recorded in
`session-endpoint-setup-design-rationale.md`.

Interactive entry surfaces also share one narrow interrupt binding. Both the
literal `Ctrl-C` key sequence and prompt-toolkit's translated `SIGINT` event
delegate to the operation-owned safe-close callback; the shared helper does
not decide whether a draft, request, or result exists. Add, Edit, Embed,
Reference, and endpoint setup use this path so an interrupt before explicit
execution returns no typed request and performs no durable write. The ordered
180×52 evidence in
[`docs/screenshots/tui-interrupt-cancel-20260822/`](screenshots/tui-interrupt-cancel-20260822/)
records that boundary and the Help close-key guidance.

Impact and Review are already partially composable:

- directional `mem impact` projects an Update plan into the shared Resolution
  Workbench in a TTY;
- `mem impact atomize` and the current Atomize review path use the Atomize
  adapter over the same common workbench;
- the older singleton ambiguity Review still uses its dedicated Review shell;
- the command modules still own too much loading, provider, persistence, and
  terminal dispatch logic to serve as clean embedded-operation APIs.

## Intended composition boundary

Standalone commands and host TUIs should call the same operation controller,
not invoke each other through a shell command or recursively enter Typer. A
reusable operation flow should separate:

1. **prepare** — resolve and freeze operands, load authoritative state, and
   produce or reload the operation artifact;
2. **project** — adapt that artifact to `SessionPicker`, `ResultWorkbench`, or
   `ResolutionWorkbench` data without performing a provider call or mutation;
3. **act** — accept one UID-bound navigation or review action and return an
   operation-owned outcome;
4. **commit** — perform the operation's existing CAS, locks, approval,
   checkpoint, provenance, and persistence checks.

The CLI may render these phases as a standalone command. A host TUI may embed
the projection and feed actions back to the same controller. Neither caller
may bypass the operation-owned commit boundary.

## Invariants

- Common terminal presentation must not imply a common durable session.
- Impact remains preview-only; embedding it cannot authorize application.
- Review remains non-applying; a reviewed answer is not acceptance of a later
  mutation.
- One user response produces at most one operation-owned semantic turn or one
  state-changing command at the established boundary.
- Session selection, browsing, expansion, and closing are read-only.
- Every selected durable artifact is reloaded and revalidated before use.
- Provider calls, exact-command approval, CAS, locks, checkpoints, rollback,
  grants, publication, and provenance remain owned by the operation.
- Ground's frozen exact-command receipt and one-command approval protocol must
  not be weakened to fit a generic workbench API.
- Existing non-TTY snapshots remain deterministic and usable.

## Rollout order

### 1. Normalize the durable-operation launcher — completed

Bring Sever's saved-session discovery into the shared `SessionPicker` contract
while retaining its dedicated new-session setup receipt. Confirm that Ground,
Meld, Compare, Update, and Sever all distinguish read-only open from explicit
new work and revalidate the selected artifact after the picker closes.

Every adapter-supplied new-session receipt now also appears as a pinned,
operation-labelled Add-new row above nonempty as well as empty catalogs. Enter
on that row and the retained `N` shortcut return the same receipt; the row is
not sorted, grouped, filtered, or represented as saved work.

This is the first implementation slice because it is presentation-only and
does not require changing provider or mutation semantics.

The completed slice also extracted the switch namespace tree into public
`ContextTree` and `ContextTreeState` components. The full-screen
`choose_context()` wrapper remains compatible, while Sever embeds two
independent tree states for Source and Criteria without importing private
picker helpers.

The shared tree now also accepts optional read-only `ContextMemoryRow`
projections and owns process-local per-Context `m` and global `M` visibility
toggles. Switch opts in
for local and READ-granted Contexts. Interactive `mem ls` reuses the same tree
in browse-only mode, rooted at its resolved operand; `ls -R` begins fully
expanded. Its adapter uses frozen occurrence IDs so namespace rows, embedded
duplicates, and cycles retain the established list semantics rather than
being flattened into a name-only catalog.

### 2. Extract a reusable Impact controller — projection completed

`ImpactController` now re-projects an owning operation's frozen artifact into
an immutable `ImpactView`. It is provider-free, performs no mutation, and
refuses to render when the operation, artifact UID, or revision differs from
the active workbench. It can project exact Resolution Workbench results or
wrap an already-saved report such as Compare. Standalone `mem impact` and
embedded hosts therefore share the projection boundary without recursively
invoking Typer or nesting a terminal application.

Directional Update preparation remains Update-owned. Extracting its endpoint
resolution and provider-backed planning into a reusable prepare API is a later
controller refinement; it is not required for embedding an already-frozen
Impact safely.

### 3. Extract adaptive Review reports — completed

`ReviewReportController` now accepts operation-owned Compare, Meld, Sever,
Atomize, and Update reports while refusing an Apply capability. `mem review`
can open each explicit report kind; operation session catalogs provide only an
identity receipt and reload the selected artifact before projection. Existing
ambiguity and Atomize responses remain resumable, while Meld and Sever reuse
their operation-owned semantic response loops with application disabled.

The detailed contract and deliberate Ground/Impact exclusions are recorded in
`adaptive-review-report-design-rationale.md`.

The presentation-normalization follow-up is also complete for these five
adaptive reports. Compare, Meld, Sever, Update, and Atomize now open through
the same Viewer-first, screen-order Tab host. Enter from Items opens the
selected row in Viewer. Report sections share one heading grammar while
operation-owned row kinds and exact evidence remain adaptive. Atomize's
immutable result account is retained ahead of its common clarification rows
rather than flattened or discarded.

The follow-up now covers standalone Compare as well as adaptive Review.
Compare and the Resolution-based session screens start in Viewer, share frame
focus styling, move through semantic section IDs, and use the same
page/Home/End grammar. Stable IDs replace positional
`len(items) + N` action targeting, so inserting Review or Impact sections does
not retarget a later Apply or whole-set action.

### 4. Embed Impact incrementally — Update, Meld, and Sever completed

The shared workbench renders the revision-bound Impact card immediately above
its operation-aware Apply card. In a TTY, Update now stops after staging,
shows Impact, and requires explicit Apply; closing leaves the exact session
staged. Sever labels its proposed local Result `SELF-SAVE` or `OTHER-SAVE` and
states the corresponding Source effect. Symmetric Meld uses
its saved equal-authority Compare report as Impact, while directional Meld
shows its exact proposed baseline effects and does not mislabel them Compare.

Review extraction remains the next independent phase. Ground is deliberately
excluded: its consequential proposals must continue through frozen exact
commands and separate approvals. Atomize remains deferred.

### 5. Revisit Atomize persistence and application

The Review presentation has moved to the common host. A later change may
consolidate Atomize's newer workbench with its legacy `ReviewSession` path and
then design its separate Impact/Apply integration without collapsing analysis,
result, clarification, and grounding artifacts or compatibility tokens.

## Deliberate non-goals

- A universal semantic provider request or response schema.
- One global active operation session analogous to the current Context.
- Calling CLI commands from inside TUIs as the integration mechanism.
- Migrating or deleting existing durable session formats merely for visual
  consistency.
- Folding Ground's conversational and approval model into the generic
  Resolution Workbench.
- Implementing the deferred Atomize integration in the first slice.

## First completion criterion

The first slice is complete: Sever has the same explicit `--sessions`
saved-work grammar as Meld, Compare, and Update, while bare entry goes straight
to new setup. Opening a saved Sever session is provider-free and
freshness-checked; the existing Sever Resolution Workbench and non-TTY behavior
remain unchanged. Ground retains its separate conversational entry contract.

## Impact completion criterion

The requested Impact slice is complete when one reusable, provider-free
controller supplies standalone or embedded views; every embedded view is
revision-bound; Update, Meld, and Sever place it directly before Apply; Meld
preserves the symmetric-versus-directional authority distinction; and neither
Ground nor Atomize is pulled into the rollout.
