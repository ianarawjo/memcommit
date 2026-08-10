# Shared terminal Surface focus control rationale

## Problem

Terminal screens already shared focused-frame styling, tree state, choice
renderers, and a small `focus_in_order` helper, but they did not share one key
grammar. Find hand-indexed its Tab order and consumed Up/Down inside each frame,
so reaching the last TARGET row did not move into SCOPE. Endpoint Setup had the
desired boundary behavior, but implemented its own visible-control indexing and
tree-entry policy. Enter dispatch was likewise repeated per prompt-toolkit
control even though the service-wide grammar is “activate the focused thing.”

A prompt-toolkit `Frame` is presentation chrome, not an interaction controller.
Putting semantic actions into the Frame would conflate border rendering with
search, selection, editing, and application authority.

## Decision

`memcommit.commands.surface_focus` owns the operation-neutral Surface contract:

- `FocusSurface` pairs a stable UI UID and prompt-toolkit control with optional
  vertical movement, activation, back, focus synchronization, and
  vertical-entry adapters;
- `SurfaceFocusController` resolves the currently visible ordered topology,
  routes movement or activation to the focused Surface, and performs a
  non-wrapping cross-Surface move only when an adapter reports `BOUNDARY`;
- `bind_surface_navigation` installs the shared Tab/Shift-Tab, Up/Down, Enter,
  and optional Escape/Backspace grammar only for capabilities declared by the
  active Surface; and
- `focus_in_order` remains a thin compatibility route for screens that need
  only ordered focus movement while they migrate.

Movement adapters return `MOVED`, `BOUNDARY`, or `CONSUMED`. Action adapters
return `HANDLED`, `ENTER_CHILD`, or `IGNORED`. These results describe control
flow, not semantic outcomes. A TARGETS adapter may toggle checked Contexts and
a SEARCH adapter may submit a query, but the common controller never knows
what a Context, query, provider turn, receipt, or durable mutation means.

Tab traversal wraps and preserves the Surface's existing internal cursor.
Vertical boundary traversal does not wrap. A target Surface may declare an
`on_vertical_enter` hook so entering a list from above selects its first
visible row and entering from below selects its last; Tab does not invoke that
hook. Writable inputs opt into only the keys they can safely delegate, so the
controller cannot steal Backspace or ordinary cursor movement merely because
the input is drawn inside a Frame.

Escape follows a separate shared hierarchy policy because moving focus and
leaving an operation are not the same authority. Every interactive surface
must have a path to its operation-owned close or cancel callback. Layered
screens use `dispatch_tui_back`: the first Escape retreats from a detail,
read-only Surface, or nested editor, and Escape at the root closes. Backspace
may mirror that retreat on read-only controls but remains text deletion in a
writable field. A root search/question composer may bind Escape directly to
close. Such a composer uses `Ctrl-J`, not `Alt-Enter`, for multiline input,
because many terminals encode Alt-Enter as Escape followed by Enter.

## Initial adoption

Find declares `SEARCH → TARGETS → SCOPE → RESULTS` once. The same declaration
drives Tab, boundary-aware Up/Down, and Enter. Targets and Results first consume
their internal rows; only their actual edge crosses to the adjacent Surface.
Scope behaves as one two-row Surface. Enter retains its operation-specific
meaning: run Search, toggle a Target, or return from the read-only Scope/Results
surface to Search.

Endpoint Setup uses the same controller for its dynamic vertical topology and
tree edge-entry policy while retaining its special new-name Tab behavior.
Help uses it for VIEW/list traversal while its accelerated command-row movement
remains Help-owned. The old `tui_primitives.focus_in_order` name delegates to
the new module for compatibility, but new internal code imports the owning
module directly.

Resolution workbenches declare their dynamic visible topology through the same
controller: `VIEWER → RESPONSES? → ITEMS → SAVE LOCATION? → TO DO`. Their
adapters retain semantic section, response, item, and final-action behavior,
while the controller owns both cyclic Tab traversal and non-wrapping arrow
transitions at real frame boundaries. A focus callback synchronizes the shared
session pane whenever either traversal mode changes the prompt-toolkit control;
without that callback border styling and key semantics could retain the prior
pane even though keyboard focus had already moved. Crossing from final review
into Items positions its Report row but does not close or apply the review;
moving or activating an Items row remains the explicit content transition.

Log, Diff, and Trace declare the smaller `VIEWER → ITEMS` topology. Their
Viewer uses the common cursor-backed formatted-text pane so semantic diff
styles survive while Up/Down advances actual wrapped visual rows. Its adapter
reports `BOUNDARY` only at the true viewport edge; the controller then crosses
to Items. Items likewise reports its first and last row boundaries instead of
clamping invisibly. Rationale has only the common read-only Viewer, so it reuses
the same wrapped-row movement primitive without fabricating an Items Surface.

Share declares `CONTEXT → MEMORIES → ACTION`. Its Context Surface retains the
two semantic Viewer sections for the selected Source and destination, while its
Memories Surface stores the inspected row in the shared session navigation
state. Arrow movement crosses only at the true first or last section or row,
Tab preserves both internal cursors, and only the Action Surface declares Enter
as the operation-owned send effect. The read-only `SEND UNAVAILABLE` projection
uses the same topology without an activation handler. This migration does not
move Source eligibility, endpoint authority, preview freezing, or delivery into
the Surface controller.

## Boundaries and alternatives

A single universal Frame widget was rejected because multiline composers,
read-only Viewers, trees, and immediate horizontal choices cannot safely share
the same arrow or Enter effects. Repeating only a generic next-focus function
was also insufficient: it left every screen to rediscover whether an internal
cursor had reached its boundary and how the adjacent list should be entered.

The selected controller centralizes key routing, topology, and boundary
mechanics while requiring explicit adapters for meaning. It is process-local
presentation state. It does not enter saved sessions, provider input, command
receipts, Context state, or Profiles.

An audit after Query exposed a root-focus trap: Query and Find could retreat
from read-only panes to their question/search field, but that root field had no
Escape binding. The same audit covered the retained Find chat, semantic Result
Viewer, resumable Review shell, read-only report Viewer, and concealed Paste
capture. Query, Find, Result, Review, and Find chat now delegate hierarchical
Escape to the shared dispatcher; Paste cancels directly, and the existing
read-only report Viewer already closed correctly. This rollout does not make a
shared close result: each operation still decides whether to persist a draft,
wait for an in-flight provider turn, or return a typed cancellation value.
