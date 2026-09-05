# Interactive Add input

- Status: Implemented
- Scope: bare `mem add` terminal intake, revised 2026-09-05

## Problem and selected design

The earlier draft list and multi-stage editor obscured the small Add task.
The first simplification kept one multiline Memory with Ctrl-S and immediate
exit. The user then chose a different intake: inspect the selected Context,
use a compact input, press Enter to add it, and continue typing another Memory.
The later clarification keeps screen paste single-line and reserves
line-oriented clipboard batches for `mem add --paste`.

## Interactive contract

The compact screen is `CONTEXT → VIEWER → ADD`, below a neutral `MEM ADD`
heading. The user requested ordinary title text, so the heading does not assign
an action color to `ADD`.
Context is one committed canonical name. Enter opens the shared SINGLE Context
tree in place; Enter on a selectable row commits that choice. Escape dismisses
an open tree before closing the screen. Leaving the tree restores the compact
committed name, so an unselected hover cannot masquerade as the Add Target.

Viewer has exactly ten content rows plus two border rows. It shows complete
readable direct Memory content in order, wrapping long existing Memories.
Up/Down and Page Up/Down scroll inside the shared pane. Checking another
Context refreshes Viewer from the beginning. Successful Add refreshes it at
the end to reveal the new Memory. References and embedded Context contents
are not flattened into this direct-Memory list.

ADD owns initial focus and contains one writable line in the same focused
frame chrome as Init's CONTEXT field. Tab follows the three visible controls.
Enter validates nonblank text and commits one Memory; the input clears only
after success and retains focus for another submission. Leading/trailing
spaces remain exact content. Screen paste accepts one line; a payload containing
CR or LF is rejected as a whole and leaves the previous input intact. The paste
handler owns this input restriction, so submission does not repeat the newline
check. A successful paste only edits the input; Enter performs the Add.
`mem add --paste` is a separate CLI path: read the clipboard, trim each physical
line, omit empty lines, and add the remaining lines as separate Memories.
Backspace remains text deletion in ADD. Escape and Ctrl-C close the screen.

```text
 MEM ADD
 ┌─ CONTEXT ──────────────────────────┐
 │ project/notes         Enter change │
 └───────────────────────────────────┘
 ┌─ VIEWER ───────────────────────────┐
 │ [a13f90c2] Existing Memory         │
 │           (ten content rows)      │
 └───────────────────────────────────┘
 ┌─ ADD ──────────────────────────────┐
 │ ›                                 │
 └───────────────────────────────────┘
 Enter add · Tab Context · Esc close
```

## Component and execution boundaries

The shared `CompactContextSelectorControl` wraps `ContextSelectorControl` and
owns only the compact/browser presentation. The shared scrollable formatted
pane, wrapped navigation, focused frame, and Surface focus controller retain
their common mechanics. The shared `ExactNameFieldControl` supplies the same
one-line input and focused frame used by Init, with an operation-neutral view
labelled Memory and trimming disabled. Add retains its own Memory validation;
Context naming rules are not applied to Memory content.

Add owns its CREATE-selectable catalog, direct Memory projection, Enter action,
and receipt collection. Viewer reads through the existing Show application
READ boundary, including its Grant projection. It never reads through Add's
mutation port. Current Grant policy requires READ with CREATE; the earlier
rationale's assumption that a CREATE-only Grant could be created was incorrect.
Query-only grants must not expose Memory content or become Add Targets.

`command.py` owns the authorized Memory load beside its read/write callback
composition. `workbench/screen.py` owns formatted Memory rows, the shared pane,
refresh timing, and input actions. The screen receives its loader as a callback
and does not depend on storage or the Show runtime. A separate `viewer.py`
module was removed because these two small helpers have clear existing owners;
another presentation module made the screen's responsibilities harder to find.
The load-error test uses a general I/O failure, not a READ denial followed by
a successful write under the same Grant permissions.

Each Enter is an independent existing Add request and checkpoint. A later
failed submission or closing the screen cannot roll back earlier successes.
The command renders every successful Add receipt in submission order on exit,
including submissions made to different Contexts. Empty sessions alone report
cancellation without changes. The global current Context is not switched.

A write failure retains the input and refreshes Viewer. A read failure clears
previous content and displays an unavailable message. After successful save,
the receipt is retained and the input is cleared before refreshing: a failed
refresh cannot falsely imply that retrying the same Memory is necessary.
Explicit positional values and `--paste` keep their existing batch contracts.

## Alternatives and remaining limits

An expanded multiline editor and the multi-draft workbench were rejected
for this input flow. The screen's one-line paste policy is not a restriction on
Memory content in the application or positional CLI inputs.
A Memory insertion position remains out of scope: Add
appends through its existing authority and CAS boundary. Viewer is a snapshot
refreshed on Context selection and submission, not a live monitor. It may
become stale if another process edits the Context while the user is typing.

[Ordered 180×52 PTY evidence](screenshots/add-context-viewer-input-20260905/README.md)
records entry, Context choice, scrolling, submission, retained-input failure,
and read-only verification.
