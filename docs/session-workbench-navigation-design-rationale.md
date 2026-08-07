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

- focused pane (`items`, `viewer`, `todo`, or `composer`);
- selected Items row and the Viewer row currently previewing it; and
- stable Viewer section UID.

Every renderer supplies an ordered tuple of `WorkbenchSection` records. A
section has a stable UID, semantic kind, and optional corresponding Items row.
The controller resolves the current numeric index from that UID on every
projection. Inserting `REVIEW_ITEMS` or `IMPACT` therefore does not change the
identity of a report section or an operation item. Apply and whole-set controls
are not synthetic Items rows; their actionable representation belongs only to
To Do.
Moving through Items immediately previews the selected report or item in
Viewer while keyboard focus remains in Items. This prevents a stale detail
from remaining above a newly selected row. `Enter` transfers focus into that
already aligned Viewer so the person can navigate its semantic sections or
open nested choices.

Resolution sessions use three visible frames with separate responsibilities:

- `VIEWER` explains the report or the currently opened item;
- `ITEMS` contains only selectable review targets; and
- `TO DO` contains one state-derived next action.

`TO DO` first points to the earliest unresolved required conflict or item, and
Enter opens that target in Viewer. Once every REQUIRED item has a staged
resolution, an applying session with saved responses that are not yet part of
the exact proposal changes to `INCORPORATE RESPONSES`; after an exact proposal
is ready, it changes to `APPLY CHANGES`. OPTIONAL reviews remain selectable in
Items but do not gate either transition, and To Do reports how many may be
skipped or remain open.
Non-applying resolution sessions expose their whole-set resolution there
instead. Read-only sessions explicitly show that no action is available. The
frame derives this projection from the current view and process-local drafts;
it neither persists a new state nor bypasses the adapter's semantic action
validation.

`INCORPORATE RESPONSES` names the semantic boundary rather than the storage
mechanism: it creates a revised complete proposal from saved responses and
does not alter a Context or Memory. `APPLY CHANGES` is the only label for the
later mutation boundary. Report and To Do must project the same next action so
one surface cannot advertise incorporation while the other still requires a
response.

When saved responses make incorporation the current To Do, the open item also
renders that same `INCORPORATE RESPONSES` section immediately below `RESPONSE`.
It is a second route to the same complete reviewed-response action, not a
per-item provider call or a second semantic boundary. If another REQUIRED item
is still open, the inline action remains hidden because the complete response
frame is not ready to submit.

The shared shell does not infer review semantics from display priority alone.
Each production adapter supplies an item role (`DECISION`, `OPTIONAL_REVIEW`,
or `CHANGE`), a response obligation (`REQUIRED`, `OPTIONAL`, or `NONE`), and a
response state (`OPEN`, `ANSWERED`, or `NOT_APPLICABLE`). This keeps exact
Update changes out of unanswered counts and keeps durable custom Forget and
Sever wording answered when a session is reopened.

The current item's `n/total` is only an ordinal. Actionable detail separately
shows `REQUIRED n · OPTIONAL m` for the complete review set so position cannot
be mistaken for required progress.

The shared interaction grammar is:

- Items receives initial focus;
- `Up` and `Down` in Items select and immediately preview the corresponding
  report or item in Viewer;
- `Enter` moves from the selected Items row into its aligned Viewer;
- Items is the initial hub: its first `Tab` opens Viewer and its first
  `Shift-Tab` reaches To Do. Once a visible-frame cycle begins, forward Tab
  follows screen order `Viewer → Items → To Do → Viewer`, with Shift-Tab
  reversing that established cycle. In particular, leaving an opened Viewer
  never skips the adjacent Items frame;
- `Up` and `Down` move one row or semantic Viewer section in the focused frame;
  while Viewer has focus, held-arrow repeats use the shared navigation
  accelerator and still visit every intermediate semantic section;
- `PageUp` and `PageDown` move eight semantic stops in the focused frame;
- `Home` and `End` move to the first or last stop;
- `B`, `Escape`, or `Backspace` unwinds a detail to the report/Items state; and
- `Q` closes without implying a semantic response or application.

Escape and Backspace are equivalent back-navigation keys throughout session
reading surfaces. When no shallower presentation layer remains, they follow
that surface's existing Escape close behavior. Backspace remains ordinary text
deletion while a composer or another writable input has focus.

Every focused detail card places its hidden viewport anchor after the closing
border rather than at the heading. This prevents a lower card such as Meld's
`PROPOSED RESULT` from appearing as only a top border at the bottom of the
Viewer. When the card fits, navigation exposes the complete box; when it is
taller than the viewport, the lower portion and closing boundary remain
reachable instead of falsely implying that the card is empty.

Resolution Viewer bodies use the shared wrapped-row scrollbar margin. Source
Memories, evidence, and proposed results often wrap one logical line across
many terminal rows; scrollbar arrows and thumb position therefore follow the
rendered visual rows rather than reporting a misleading logical-line offset.
This is a shared Viewer property and must not be reimplemented by Atomize or
another operation adapter.

An actionable evidence card is also not one oversized navigation stop. The
shared Resolution Viewer orders its stops as Classification, each criterion,
each terminal-wrapped line of every source Memory, and Why. Up/Down can
therefore traverse a long quoted Memory one visible line at a time before
moving to the reason or proposed result. Those line stops are presentation
slices only: the typed source remains one Memory, its short UID appears only
on the first line, and a source-frame/claim heading remains attached to the
first line of that group. A terminal resize may rewrap and reclamp the line
index without changing semantic identity or persisted state. The item kind,
ordinal, title, status, and review-set counts remain visible as non-focusable
report chrome, so opening an actionable detail starts on Classification.

Compact technical refs use the shared purple reference style rather than the
blue focus color. When a ref denotes an individual proposed Memory and its
content is available, the adapter renders it as a lavender `[n] content` row
and retains the UID only in the typed model. Raw `kind:key` identities must not
duplicate those visible Memory rows.

A detail block containing several proposed Memories contributes one semantic
Viewer stop per Memory rather than one stop for the whole block. Up/Down
therefore advances exactly one `[n] content` row. Evidence remains collapsed
so the list stays compact; Enter on a Memory shows only that row's evidence,
and Enter again or Escape/Backspace collapses it before any outer back step.
This state is process-local and never enters the artifact or response frame.

An OPTIONS section is a nested navigation layer, not an implicitly active list.
For actionable quality issues, its clarification or resolution question is
the prompt of that same Decision section rather than a separate navigation
stop. One focus state therefore emphasizes both the question and its proposed
answers, and Enter opens the choice rows directly.
Its neutral state says `Enter to choose an option`. Enter activates the layer,
Up/Down moves among supplied readings and Other direction, and Enter selects
the focused reading. Escape or Backspace returns to Viewer section navigation.
Choices are plain rows rather than nested rectangular cards. The focused row
uses the shared light-blue treatment and an underline; that underline is a
cursor signal and disappears whenever the row is not focused. A durable staged
selection carries a `✓` marker without retaining the underline. Reopening a
durable draft restores the option cursor to that checked row; otherwise the
screen would advertise one selection while Enter acts on another. This
interaction belongs to the common Resolution Session Viewer, so Meld, Sever,
Update, Atomize, and adaptive Review do not define divergent option controls.

The same session topology is the default for live resolution review in Meld,
Sever, and Atomize, and for the Update and adaptive Review projections. Sever
classifies each outbound treatment as REQUIRED because every source Memory
needs one inspectable disclosure decision, even though its provider
recommendation is already staged. Atomize uses the shared two-stage terminal
path only when review input exists: after all required responses are saved, To
Do offers `INCORPORATE RESPONSES` to reanalyze the complete reviewed response
set; the resulting unedited exact proposal offers `APPLY CHANGES`. A current
analysis with no unresolved required finding and no unincorporated response is
already exact, so an unanswered optional split may proceed directly to Apply.
A response added to that proposal removes Apply until it is incorporated
again.

Choosing Other direction or opening an item's ordinary Response keeps the
current detail and options visible. The writable field appears inline within
the same Viewer frame rather than replacing the detail or opening a sibling
Message frame. Enter saves and returns focus to that Viewer; `Ctrl-J` inserts
a newline. When the adapter owns durable drafts, saving does not close the
workbench. An operation that needs a provider response still receives the
normal explicit submitted action at its semantic boundary.

`RESPONSE` is a real Viewer navigation section after any operation-specific
result blocks. Its resting state says only `Enter to write a response`; it
does not display adapter-authored editing instructions as report content.
Enter opens a blank field for a new response or restores the current durable
draft for revision.

The shared style continues to color the focused frame border/label and active
Viewer section light blue. When a focused frame contains more than one Tab
target, the whole frame keeps that blue chrome while the exact nested control
adds bold. Persistent selected values retain their blue surface without bold
after focus leaves, and combine blue with bold only while they own input. The
active Items row uses the shared reverse-bold selection style. Unfocused report
cards, explanatory prose, and structural labels are neutral white. Light
lavender is reserved for individual Memory objects, so a Compare report does
not visually present every derived paragraph as though it were itself a
Memory.

## Operation boundaries

Resolution-based Meld, Sever, Update, Atomize, Impact, and Review surfaces use
the controller inside `run_resolution_workbench_shell`. Standalone Compare
retains its operation-specific report renderer, source-member navigation, and
`R`ationale/`L`edger/`M`eld actions, but now delegates pane, row, and semantic
section navigation to the same controller and follows the same initial-focus,
Enter, paging, Home/End, and back behavior.

Compare, Result, and Resolution also use the same semantic Viewer style
palette and focused-frame primitive. This is a family of Viewer variants, not
a claim that Compare relations, Result cases, and Resolution choices share one
state model.

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
