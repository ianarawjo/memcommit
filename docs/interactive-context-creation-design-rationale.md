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
mem branch               # choose a local Source, edit a suggested fresh name,
                         # then branch and switch
mem checkout -b          # delegate to the same bare Branch creation surface
```

Cancellation creates nothing and does not change the current Context. A name
shown in either editor remains `NOT CREATED` until Enter submits the validated
receipt to the normal command implementation.

## Compact UI

Bare Init needs only the existing compact name-dialog shape:

```text
 MEM INIT
 NEW CONTEXT NAME · NOT CREATED
╭──────────────────────────────────────────────╮
│ new-context                                  │
╰──────────────────────────────────────────────╯
 Edit directly · Ctrl-U clear · Enter create · Esc cancel
```

Bare Branch composes the same field with one local Context selector above it:

```text
 MEM BRANCH · SOURCE UNCHANGED
╭─ FROM CONTEXT → NEW CONTEXT ────────────────╮
│ ✓ * project/main                            │
│ ─────────────────────────────────────────── │
│ NEW · [ NEW CONTEXT NAME ] · NOT CREATED    │
│ › project/main-branch                       │
╰──────────────────────────────────────────────╯
 ↑/↓ move · Tab/Shift-Tab section · Enter choose/create · Esc cancel
```

The Source frame may expose a bounded, scrollable namespace tree when focused;
the Source rows and exact new-name input remain sections of one compound
Branch frame, matching the existing-or-new endpoint composition used by
Atomize without importing Atomize semantics. Branch does not render a separate
destination-parent tree: slash-delimited placement remains directly editable
inside the exact name. It also does not need Switch's Memory preview or a
full-screen shell. The current
ordinary local Context is the initial Source. If the current pointer is a
granted view or is unset, the first frozen local Context is used for orientation
instead; grant attachments are not branchable local Sources.

## Suggested names

An editable, collision-free suggestion is preferable to a blank field:

- Init starts with `new-context`, then `new-context-2`, and so on.
- Branch starts with a sibling-style `<source>-branch`, then adds a numeric
  suffix when occupied. For example, `project/main` suggests
  `project/main-branch`.

Branch must not suggest `project/main/branch`: slash ancestry is a lexical
namespace, not durable branch lineage. The suggestion is process-local and
does not become a preference.

When the Source selection changes, Branch updates the suggested name only if
the field still equals the previous suggestion. Once the person edits the
field, later Source navigation preserves that exact draft. This is the same
non-destructive suggestion rule already used by Sever output naming.

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
renderers. `ContextNameEditorState` remains a compatibility alias. The smaller exact-name
input and focused-frame mechanics live with the operation-neutral terminal
primitives. Generic defaults and validation failures say `CONTEXT NAME` rather
than `SAVE LOCATION`. The Resolution adapter supplies `SAVE LOCATION`; Init
supplies `NEW CONTEXT NAME`; Branch supplies the same new-Context label; each remains free
to provide `NOT CREATED`, `CURRENT TARGET`, or another operation-owned state.

The current `commands/save_location_control.py` remains a thin compatibility
facade for existing callers. It supplies Save Location defaults but owns no
interaction mechanics. Init imports the generic Context-name composition;
Branch imports the generic Context selector and operation-neutral exact-name
primitive directly. Neither names its field after Save Location.

`ExactNameInputControl` is the smallest unframed, one-line input. Branch uses
that same primitive as Atomize's new-Output row so its Source tree and new name
can share one outer frame without gaining a parent-locator role.
`ExactNameFieldControl` composes it with the common focused Frame, and
`ContextParentLocatorControl` independently owns the optional frozen parent
tree. `ContextNameControl` composes the framed field and locator;
`choose_context_name` supplies its compact standalone host for Init.
Branch instead composes `ExactNameInputControl` with `ContextSelectorControl`
inside one Source-to-new compound frame. Resolution
retains its workbench-specific dynamic frame and action return, but imports the
same generic value, parent state, validation, and render mechanics through its
Save Location compatibility adapter. The non-workbench `save_location_review`
uses the same data contract with a Typer prompt. The Profile-specific
`study_name_dialog` shares the operation-neutral exact-name field but not the
Context parent locator or Context validation contract.

The new presentation should compose existing operation-neutral controls:

- the generic exact-name validation and input presentation;
- `ContextNameEditorState` and its direct-input-first parent browser where a
  destination parent catalog is useful;
- `ContextTreeState` for cursor, expansion, and scrolling;
- SINGLE `ContextSelectionState` for the exact Branch Source;
- the common Context-tree row renderer and selection marker/style projection.

A narrow Context-creation dialog owns layout, focus traversal, cancellation,
and the editable suggestion. It returns only a process-local receipt
containing the exact new name and optional exact Source name. Init and Branch
retain semantic validation and persistence:

- Init applies `--parents`, creatability checks, checkpoints, and selection.
- Branch restricts Source to ordinary local Contexts, freezes the command-start
  current pointer, loads the selected Source, validates its UID/content/history,
  creates the require-new copy, inherits checkpoints, and selects the result.

Branch Source selection and its exact new name are the only two semantic inputs.
They share one visual frame but retain separate cursor/input state. Branch does
not compose the Context-name parent's locator at all: choosing a Source changes
which Context is copied, while slash-delimited destination placement remains
ordinary direct name editing.

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

## Atomicity and compatibility boundary

Selecting a non-current Source must not first persist an intermediate
`switch`. Branch can pass the chosen Source and the separately frozen current
pointer into the existing atomic branch transaction. A concurrent change to
the Source, its checkpoint history, the target identity, or the current pointer
therefore aborts rather than branching from a stale screen or overwriting a
later switch.

No existing explicit command changes meaning. Bare interactive routes require
a TTY and should fail with a direct instruction to pass a name outside one.
The help inventory advertises the bare forms alongside their explicit forms.
