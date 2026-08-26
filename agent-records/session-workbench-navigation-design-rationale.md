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
open nested detail content.
Callers perform arrow movement through the controller's combined
`move_and_preview_row` transition so the Items cursor and Viewer projection
cannot drift apart between two command-local state updates. The transition is
presentation-only: it neither changes pane focus nor persists, calls a
provider, or interprets the row. Operation adapters still own projection-side
cleanup such as closing transient detail, loading a response draft, or
constructing an exact mutation receipt.
History Log, Trace, Diff, and Revert use the same cursor/preview transition.
Log-style Enter opens the aligned Viewer. Revert instead stages the displayed
exact checkpoint UID and moves directly from Items to its editable
`PROPOSED COMMAND`; the visible `HISTORY` policy remains available through
ordinary traversal. Its complete screen order is
`VIEWER → ITEMS → HISTORY → PROPOSED COMMAND`; Tab follows that order and
boundary-aware Up/Down crosses read-only adjacent frames without wrapping.
The History control reuses the common checked-choice grammar for
`DISCARD NEWER` versus the default `KEEP ALL`, without a redundant description
line below those self-contained labels. History changes rewrite the command,
and a valid command edit—including a unique checkpoint UID prefix—moves the
checked Items row and History choice. Previewing or checking a Revert row
therefore does not weaken or bypass
its later exact mutation boundary; only Enter on the valid command applies.

Resolution sessions use three visible frames with separate responsibilities:

- `VIEWER` explains the report or the currently opened item;
- `ITEMS` contains only selectable review targets; and
- `TO DO` contains one state-derived next action.

The complete report begins with a non-focusable `CONTEXT LOCATIONS` block
whenever the adapter supplies typed endpoints. This sits before
the adapter's operation-owned overview sections because source, criteria,
target, and result locations describe the operation frame, not the semantic
interpretation of its contents. The navigation shell does not manufacture a
generic comprehension group. One-source, two-source, and
source/criteria/result operations share the same row shape; role labels remain
operation-owned so the navigation shell never guesses semantics from an arrow
string.

`TO DO` first points to the earliest unresolved required conflict or item, and
Enter opens that target in Viewer. Once every REQUIRED item has a staged
resolution, an applying session changes to `REVIEW AND APPLY`; Enter opens a
non-mutating final-review surface rather than applying immediately. That
surface derives exactly one final action: `APPLY` for a fully reviewed exact
proposal, `APPLY AS IS` when the adapter declares open findings or reviews,
or an incorporation action when saved responses are not yet part of the
proposal. OPTIONAL reviews remain selectable in Items but do not gate this
transition, and the final review reports how many remain open.
When a non-applying session has operation-authored whole-set strategies, both
the Report `RESOLVE ALL` stop and the `TO DO · RESOLVE ALL` control enter the
same non-mutating final-review surface directly. They must not use the former
two-step behavior in which To Do only refocused Report and Report Enter then
redrew itself. The `RESOLVE ALL` review shows the shared summary, the selectable
strategy policy, and one final action; only Enter on that final action returns
the selected operation-authored action.
Because this is a confirmation boundary rather than another report/detail
view, its outer frame omits the `VIEWER` label. It opens at the top
`REVIEW AND APPLY` summary inside Viewer so the viewport and keyboard focus do
not remain on the lower `TO DO` handoff. Down moves through any policy card to
the exact final action; the next Down crosses into Items without closing or
applying the review, and Enter on the action runs only that disclosed action.
Each of the summary, policy, and final-action cards is one semantic stop, and
focus fills the complete card rather than only its first border row. Enter on
the summary is the explicit non-applying return action. The shell snapshots the
entry pane, Viewer kind, row, and stable section UID before opening review, so
that Enter, Escape, and Backspace all restore the same exact origin rather than
guessing that Items or the start of Report was intended. If an old process-local
state has no origin snapshot, the stable Report action is the compatibility
fallback.
Forward Tab follows `Viewer → Items → To Do` and Shift-Tab reverses it; merely
passing through Items must not close the final review.
Selecting or opening an Items row intentionally returns to ordinary report or
item content. Escape or Backspace returns without applying.
Non-applying resolution sessions expose their whole-set resolution there
instead. Read-only sessions explicitly show that no action is available. The
frame derives this projection from the current view and process-local drafts;
it neither persists a new state nor bypasses the adapter's semantic action
validation.

`INCORPORATE RESPONSES` names the semantic boundary rather than the storage
mechanism: it creates a revised complete proposal from saved responses and
does not alter a Context or Memory. `APPLY` names the later exact mutation
boundary. An adapter may explicitly authorize `INCORPORATE AND APPLY` as one
compound final action; the label must disclose that the revised proposal will
not receive a second visual approval. Report and To Do both project
`REVIEW AND APPLY`, while the final surface alone exposes the state-dependent
mutation action.

For an operation with an editable materialization target, `SAVE LOCATION` is a
shared compact frame between `ITEMS` and `TO DO`, not a Viewer section or Items
row. Its resting line shows the current exact name and state. Enter replaces
that line with a one-line exact-name editor and returns a destination-change
action to the owning controller; Escape cancels locally. The operation
validates and persists the change, while the shell neither creates nor renames
a Context. Review and Apply remains the only route to the final mutation
choice. Visible Tab order conditionally becomes
`VIEWER → RESPONSES → ITEMS → SAVE LOCATION → TO DO` for an answerable opened
item, and omits Responses when no response target is visible.

`INCORPORATE RESPONSES` remains a whole-session To Do/final-review action. It
is not duplicated inside Viewer or Responses: the frame collects staged input,
while the owning operation decides whether that input requires a new provider
turn before Apply.

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

- Viewer receives initial focus on the complete report;
- `Tab` moves from Viewer to Items, while `Shift-Tab` moves from Viewer to To
  Do, following the visible frame order from the first interaction;
- `Up` and `Down` in Items select and immediately preview the corresponding
  report or item in Viewer;
- `Enter` moves from the selected Items row into its aligned Viewer;
- Forward Tab follows screen order `Viewer → Items → To Do → Viewer`, with
  Shift-Tab reversing that cycle. In particular, leaving an opened Viewer
  never skips the adjacent Items frame;
- `Up` and `Down` move one row or semantic Viewer section in the focused frame;
  while Viewer has focus, held-arrow repeats use the shared navigation
  accelerator and still visit every intermediate semantic section;
- at the first or last internal stop, another `Up` or `Down` crosses to the
  adjacent visible frame through the shared Surface controller; unlike Tab,
  arrow traversal does not wrap at the top or bottom of the screen;
- `PageUp` and `PageDown` move eight semantic stops in the focused frame;
- `Home` and `End` move to the first or last stop;
- `B`, `Escape`, or `Backspace` unwinds a detail to the report/Items state; and
- `H` or `h` opens the shared read-only Help inventory from a navigation
  surface and the same key hides it back to the exact retained session focus;
  and
- `q` or `Q` closes without implying a semantic response or application.

Escape and Backspace are equivalent back-navigation keys throughout session
reading surfaces. When no shallower presentation layer remains, they follow
that surface's existing Escape close behavior. Backspace remains ordinary text
deletion while a composer or another writable input has focus.
The close shortcut is deliberately case-insensitive across terminal screens so
Shift and Caps Lock cannot change its meaning. Existing focus filters remain
authoritative, so neither form is intercepted inside writable input.

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
shared Resolution Viewer orders its outer stops as Classification, each
criterion, each complete source Memory, and Why. One Memory remains one stop
regardless of terminal wrapping. Enter opens the shared process-local nested
reading layer; Up/Down then scrolls its visual rows without replacing the
stable outer Memory UID with width-dependent line identities. Enter,
Escape, or Backspace returns to section navigation. A source-frame/claim
heading remains attached to the first Memory in that group. The item kind,
ordinal, title, status, and review-set counts remain visible as non-focusable
report chrome, so opening an actionable detail starts on Classification.

The complete Report follows the same reviewability rule. One actionable
finding is one stable stop containing its title, priority/summary paragraph,
and clarification question. Focus fills all three parts together while the
title keeps the bold report-label treatment and the explanatory paragraphs use
the non-bold Viewer-body treatment. Up/Down therefore advances by problem, not
by the visual paragraphs that explain one problem, and Enter opens the one
corresponding Items target. A report-level action likewise keeps its heading
and explanatory paragraph in one stop because they jointly describe a single
transition; both lines receive focus so the available action is not represented
by an isolated highlighted heading.

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

The common Responses frame presents every proposed choice and Response as one
linear navigation sequence. Its clarification or resolution question is
explanatory chrome rather than a separate stop. Entering the frame focuses the
checked choice, or the first choice when none is checked. Up/Down moves through
the supplied readings and then the separate Response box without a preliminary
Enter or a nested-layer Escape; moving up from Response restores the checked
choice when one exists and otherwise retains the last exploratory row.
Enter selects or clears the focused reading, while Enter on Response focuses
its framed multiline field.

The choice cursor is exploratory state, not the staged answer. Crossing from
choices into Response or leaving the frame restores that cursor to the checked
choice when one exists; returning to the frame must not preserve a stale hover
over a different reading.

Choices reuse the shared flat selection state but render as unboxed stacked
rows in Responses. The focused label and description receive the blue fill,
only the label becomes bold, and a durable staged selection carries `✓` and
the retained fill. The hidden viewport anchor follows the complete row group.
Reopening a durable draft restores the option cursor to that checked row;
otherwise the screen would advertise one selection while Enter acts on another. This
interaction belongs to the common Resolution Session Responses frame, so Meld,
Sever, Update, Atomize, and adaptive Review do not define divergent controls.

The same session topology is the default for live resolution review in Meld,
Sever, and Atomize, and for the Update and adaptive Review projections. Sever
classifies each outbound treatment as REQUIRED because every source Memory
needs one inspectable disclosure decision, even though its provider
recommendation is already staged. Atomize uses the shared two-stage terminal
path only when review input exists. To Do always enters `REVIEW AND APPLY`
after required work is complete. Without new input, its final action is
`APPLY` or `APPLY AS IS`. With an incorporable Atomize response, the adapter
offers `INCORPORATE AND APPLY`: one explicit approval reanalyzes the complete
reviewed response set and then enters the normal validated application path.
The final surface states this compound behavior and Escape/Backspace returns
without either step. Responses itself never incorporates or applies.
When a ready final proposal has no reviewable issues, the review summary says
that no open responses remain and omits a meaningless `0/0 ANSWERED` count.
This describes the current proposal only; it does not invent a historical count
of responses that an operation adapter did not preserve.

Opening an item's Response keeps the current item visible. The writable field
is a persistent inner box within the independent Responses frame rather than a
fabricated final choice, a Viewer replacement, or a sibling Message frame.
Enter saves and returns focus to Responses; `Ctrl-J` inserts
a newline. When the adapter owns durable drafts, saving does not close the
workbench. An operation that needs a provider response still receives the
normal explicit submitted action at its semantic boundary.

`RESPONSE` is the final navigation stop after the visible choices inside the
common Responses frame. Its resting state says only `Enter to write a response`; it
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

Compare, Result, Share, and Resolution also use the shared semantic Viewer
block presenter in addition to the same palette and focused-frame primitive.
They now route section movement through the shared `SemanticViewerController`,
which owns stable-UID clamping, paging, rendering, and nested reading state.
Operations still declare the section order and meaning. The controller owns
focus styling and viewport anchors without rewriting report text.
Compare additionally derives navigation and rendering from one
`SemanticViewerDocument`; Resolution retains operation-adaptive block builders
while delegating their presentation to the same policy. This is a family of
Viewer variants, not a claim that Compare relations, Result cases, Resolution
choices, and Share delivery sections share one state model.

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
by this session-workbench action grammar. Ground does reuse the lower-level
Session Help handoff on read panes; Help cannot approve a command or intercept
its writable Message and edit fields. SessionPicker also remains a launcher
rather than an active workbench. Composer behavior is operation-dependent even
though its focus identity is represented by the common controller. The full
Help lifecycle and rollout boundary are recorded in
[`session-help-design-rationale.md`](session-help-design-rationale.md).
