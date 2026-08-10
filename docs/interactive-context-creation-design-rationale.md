# Interactive Context creation

- Status: Implemented
- Scope: compact no-name entry routes for Context initialization and branching

## Problem

The explicit creation routes are concise and scriptable:

```text
mem init NAME
mem branch NEW_NAME
mem checkout -b NEW_NAME
```

They are less discoverable during exploratory editing because the person must
commit to an exact name before seeing any interaction surface. `switch` and
`checkout` now share a no-name Context picker, so creation should have an
equally small no-name path without turning `init` or `branch` into a session
workbench.

## Command contract

Explicit operands retain their current noninteractive behavior. The interactive
entry routes are:

```text
mem init                 # edit a suggested fresh name, then create and switch
mem init --parents       # same editor; ensure lexical parents on submission
mem branch               # choose a local Source and parent-assisted exact new
                         # target, then branch and switch
mem checkout -b          # delegate to the same bare Branch creation surface
```

Cancellation creates nothing and does not change the current Context. A name
shown in either editor remains `NOT CREATED` until Enter submits the validated
receipt to the normal command implementation.

## Interactive UI

Bare Init needs only the existing compact name-dialog shape:

```text
 MEM INIT
 NEW CONTEXT NAME · NOT CREATED
╭──────────────────────────────────────────────╮
│ new-context                                  │
╰──────────────────────────────────────────────╯
 Edit directly · Ctrl-U clear · Enter create · Esc cancel
```

When a frozen catalog exists, Init shows the common `PARENT CONTEXT` locator
above that field. Choosing a parent reparents the untouched suggestion. After
the first direct edit, the complete exact input becomes authoritative: parent
browsing may change the locator selection but cannot rewrite the edited name.

Bare Branch uses the same full-screen endpoint composition as Atomize. Its B
frame treats the tree only as a parent locator and keeps the exact new name in
the field below it:

```text
 MEM BRANCH · FROM A → TO B
╭─ A · FROM CONTEXT ──────────────────────────╮
│ ✓ * project/main                            │
╰──────────────────────────────────────────────╯
╭─ B · TO · NEW CONTEXT ──────────────────────╮
│ ✓   project/main/                           │
│ ──────────────────────────────────────────── │
│ NEW · [ EXACT NEW CONTEXT NAME ]             │
│ › project/main/branch                       │
╰──────────────────────────────────────────────╯
╭─ APPLY ─────────────────────────────────────╮
│ [ PRESS ENTER TO APPLY ]                    │
╰──────────────────────────────────────────────╯
```

This is not a visual approximation of Atomize: Branch delegates to the same
`choose_session_endpoints` shell. A and B therefore share its tree cursor,
checked selection, separator, new-name confirmation, Surface traversal, Apply
stop, and key grammar. Branch supplies only its role availability and receipt
validation. Every B tree row is an existing parent location, displayed with a
trailing slash; no row is itself a Branch target. Branch still does not need
Switch's Memory preview or a separate Memory surface. The current
ordinary local Context is the initial Source. If the current pointer is a
granted view or is unset, the first frozen local Context is used for orientation
instead; grant attachments are not branchable local Sources.

## Suggested names

An editable, collision-free suggestion is preferable to a blank field:

- Init starts with `new-context`, then `new-context-2`, and so on.
- Branch starts with `<source>/branch`, then adds a numeric suffix when
  occupied. For example, `project/main` suggests `project/main/branch`.

The `/branch` suffix is an editable lexical placement suggestion, not durable
lineage metadata. The suggestion is process-local and does not become a
preference.

The selected Source determines the suggestion while the field remains
untouched. Choosing another Source changes `old-source/branch` to
`new-source/branch`. Before a direct edit, choosing another parent similarly
replaces the inferred parent prefix. The first person-authored text change
makes the complete exact path authoritative: `/` remains valid, any prefix can
be deleted, and later Source or parent choices preserve the edited value even
if it is edited back to the earlier spelling. Programmatic suggestion refresh
is explicitly kept separate from this dirty state.

An exact target that already exists is never repurposed, even when its direct
frame is empty. The editor reports the collision and Apply remains blocked.
This protects deliberately empty namespace/container Contexts and keeps Branch
equivalent to Init plus a copied Source frame, rather than introducing an
implicit fill-or-overwrite variant.

## Shared component boundary

`Save Location` is one operation label, not the identity of the reusable
control. The existing `SaveLocationView` already contains a more general
compound Context-name editor:

- one exact, directly editable Context name;
- caller-owned label, visible state, detail, and validation;
- an optional frozen existing-Context catalog and current annotation;
- a parent-locator tree that preserves the exact final name segment; and
- compact-row, expanded-tree, and review-card projections.

Context-specific composition lives under `memcommit.context_targeting.tui` as
`ContextNameView`, `ContextParentLocatorState`,
`ContextParentLocatorControl`, `ContextNameControl`, and `context_name_*`
renderers. `ContextNameDraftState` in `tui/name_draft.py` owns the shared
untouched-to-edited transition, nearest-parent inference, suggestion
inheritance, and conditional reparenting used by both Init and Branch.
`ContextNameEditorState` remains a compatibility alias. The smaller exact-name
input and focused-frame mechanics live with the operation-neutral terminal
primitives. Generic defaults and validation failures say `CONTEXT NAME` rather
than `SAVE LOCATION`. The Resolution adapter supplies `SAVE LOCATION`; Init
supplies `NEW CONTEXT NAME`; Branch supplies the same new-Context label; each remains free
to provide `NOT CREATED`, `CURRENT TARGET`, or another operation-owned state.

The current `commands/save_location_control.py` remains a thin compatibility
facade for existing callers. It supplies Save Location defaults but owns no
interaction mechanics. Init imports the generic Context-name composition;
Branch configures the common endpoint shell used by Atomize. Neither names its
field after Save Location.

`ExactNameInputControl` is the smallest unframed, one-line input. Branch and
Atomize reach that same primitive through the common endpoint frame. Branch
opts its B role into the operation-neutral new-parent-locator mode; Atomize
retains its existing-or-new output meaning.
`ExactNameFieldControl` composes it with the common focused Frame, and
`ContextParentLocatorControl` independently owns the optional frozen parent
tree. `ContextNameControl` composes the framed field and locator;
`choose_context_name` supplies its compact standalone host for Init.
Branch instead supplies A/B role specs to `choose_session_endpoints`. Resolution
retains its workbench-specific dynamic frame and action return, but imports the
same generic value, parent state, validation, and render mechanics through its
Save Location compatibility adapter. The non-workbench `save_location_review`
uses the same data contract with a Typer prompt. The Profile-specific
`study_name_dialog` shares the operation-neutral exact-name field but not the
Context parent locator or Context validation contract.

The controls do not infer edit ownership from string equality. A person may
edit a value back to its original spelling and it still remains directly
owned; programmatic suggestion and parent updates are explicitly guarded so
they do not mark the draft edited. This prevents both Init and Branch from
silently resuming automatic inheritance after a deliberate edit.

The new presentation should compose existing operation-neutral controls:

- the generic exact-name validation and input presentation;
- `ContextNameEditorState` and its direct-input-first parent browser where a
  destination parent catalog is useful;
- `ContextTreeState` for cursor, expansion, and scrolling;
- SINGLE `ContextSelectionState` for the exact Branch Source;
- the common Context-tree row renderer and selection marker/style projection.

A narrow Context-creation adapter owns the editable suggestion and translates
the common endpoint draft into a process-local receipt. Init and Branch retain
semantic validation and persistence:

- Init applies `--parents`, creatability checks, checkpoints, and selection.
- Branch restricts Source and parent browsing to ordinary local Contexts,
  freezes the command-start current pointer, and revalidates the selected Source
  and exact require-new TO under one atomic write boundary. The target receives
  a new identity and inherited Source checkpoints.

Branch's two semantic endpoints are FROM and TO. TO always materializes one
exact new name. Its tree selection is a placement aid only; after direct input
begins, the exact field wins and parent browsing cannot rewrite it.

The same separation supports future cardinalities without inventing another
selector. `ContextSelectionState` already owns both SINGLE and MULTIPLE checked
sets while the composing operation owns minimum cardinality, availability,
role labels, and receipts. A framed selector is therefore common interaction
chrome plus shared tree/selection mechanics; `SOURCE`, `CRITERIA`, or another
role is supplied by its adapter rather than embedded in the selector itself.

The existing Switch picker should not be called as a nested operation. It
offers granted navigation and Memory previews that Branch does not authorize or
need. Reusing its lower-level Context tree controls preserves interaction
grammar without importing Switch semantics.

An explicit Branch launched while the current pointer names a granted view must
fail as a local-Source eligibility error, not leak the storage-layer `Context
not found` wording. The public name exists and remains switchable; it is absent
only from Branch's deliberately local Source catalog.

## Atomicity and compatibility boundary

Selecting a non-current Source must not first persist an intermediate
`switch`. Branch passes the chosen Source, exact new target, and separately
frozen current pointer into its atomic branch transaction. A concurrent change
to the Source, new-name availability, or current pointer therefore aborts
rather than branching from a stale screen, replacing an existing Context, or
overwriting a later switch.

No existing explicit command changes meaning. Bare interactive routes require
a TTY and should fail with a direct instruction to pass a name outside one.
The help inventory advertises the bare forms alongside their explicit forms.
