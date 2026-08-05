# Shared session workbench navigation

## Goal

Saved-operation workbenches should not merely copy Meld's colors. Compare,
Meld, Sever, Update, Atomize, and their adaptive Review surfaces should use one
focus and semantic-scrolling state machine while retaining operation-owned
artifacts, rows, evidence, actions, and persistence.

The motivating failure was positional coupling. Adding the common
`REVIEW ITEMS` report section shifted every later numeric index, so code that
located a final action with `len(items) + N` could focus the wrong report
section. A visually similar dedicated Compare workbench also started in a
different pane and used a different page size.

## Contract

`SessionWorkbenchNavigation` owns only process-local presentation state:

- focused pane (`items`, `viewer`, or `composer`);
- selected Items row and the separately opened Viewer row; and
- stable Viewer section UID.

Every renderer supplies an ordered tuple of `WorkbenchSection` records. A
section has a stable UID, semantic kind, and optional corresponding Items row.
The controller resolves the current numeric index from that UID on every
projection. Inserting `REVIEW_ITEMS` or `IMPACT` therefore does not change the
identity of `APPLY`, `RESOLVE_ALL`, or an operation item.
Moving through Items does not replace the open Viewer merely because the
selection changed; `Enter` is the explicit transition that copies the selected
row into the Viewer identity.

The shared interaction grammar is:

- Items receives initial focus;
- `Enter` opens the selected row in Viewer;
- `Tab` and `Shift-Tab` switch the durable frames;
- `Up` and `Down` move one row or semantic Viewer section in the focused frame;
- `PageUp` and `PageDown` move eight semantic stops in the focused frame;
- `Home` and `End` move to the first or last stop;
- `B` or `Escape` unwinds a detail to the report/Items state; and
- `Q` closes without implying a semantic response or application.

The shared style continues to color the focused frame border/label and active
Viewer section light blue. The active Items row uses the shared reverse-bold
selection style.

## Operation boundaries

Resolution-based Meld, Sever, Update, Atomize, Impact, and Review surfaces use
the controller inside `run_resolution_workbench_shell`. Standalone Compare
retains its operation-specific report renderer, source-member navigation, and
`R`ationale/`L`edger/`M`eld actions, but now delegates pane, row, and semantic
section navigation to the same controller and follows the same initial-focus,
Enter, paging, Home/End, and back behavior.

This is presentation reuse, not a universal durable session. Provider calls,
revision checks, responses, Apply, publication, checkpoints, and provenance
remain operation-owned. The controller never validates or executes a semantic
action.

## Alternatives rejected

Copying the key bindings and blue styles into each shell was rejected because
the implementations had already drifted despite looking similar. Forcing
Compare into the Resolution Workbench data model was also rejected: its
relation ledger, source-member cursor, and read-only follow-up actions are not
resolution choices. A small shared navigation controller preserves those
semantics without creating a giant universal operation schema.

## Boundaries and limitations

Ground keeps its exact-command approval and conversational navigation rules.
It may reuse low-level frame and scrolling primitives, but it is not governed
by this session-workbench action grammar. SessionPicker also remains a launcher
rather than an active workbench. Composer behavior is operation-dependent even
though its focus identity is represented by the common controller.
