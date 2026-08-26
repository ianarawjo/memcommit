# Adaptive terminal text layout design rationale

## Motivation

Several terminal surfaces independently implemented `_compact`, `_line`, or
`_preview` helpers. Some measured Python code points while others measured
terminal cells, and several interactive rows truncated at fixed widths before
prompt-toolkit knew the actual viewport width. A wide Session Picker could
therefore leave unused space while its Summary still ended in `…`; widening a
Compare or Result viewport could not recover text already discarded while the
row model was constructed.

The service needs one geometry policy without imposing one universal column
size. A Session row, history row, compact trace receipt, and horizontally
scrollable table have different information priorities and disclosure paths.

## Decision

`memcommit.commands.tui_text_layout` is the shared terminal text geometry
boundary. It owns:

- terminal-cell measurement for ASCII, CJK, and other wide characters;
- end and middle elision within an exact cell budget;
- terminal-cell padding and single-logical-line whitespace folding;
- live `WindowRenderInfo.window_width` lookup with an explicit first-render
  terminal fallback; and
- adaptive allocation of one available width across caller-declared columns.

Each surface declares its own `AdaptiveColumn` minima, preferred content width,
shrink order, growth order, and whether it may consume remaining space. These
values express semantic priority, not terminal geometry. The common allocator
recomputes the resulting widths from the current viewport on every render.

Session rows preserve state first, then the session title, and give remaining
space to Summary. History rows preserve the command before their description.
Both omit the timestamp only on genuinely narrow screens because the complete
selected record remains visible in Detail. Compare retains complete relation
labels in its row model and performs any necessary elision only at render time.
Result case rows retain complete one-line text and let their wrapped Window own
visual reflow.

## Invariants

1. `…` means content was actually omitted from that projection. Text that fits
   the current cell budget is never marked as truncated.
2. A row rendered for a declared width never exceeds that width in terminal
   cells.
3. Persistent models, semantic projections, provider input, and command
   receipts never receive viewport-truncated text.
4. Terminal resize is presentation-only. Re-rendering may reveal more or less
   of the same complete value without mutating the artifact or selection.
5. Display escaping remains the caller's trust-boundary responsibility. Layout
   operates on the already escaped or sanitized presentation string.

## Intentional exceptions

This policy does not remove every numeric limit:

- provider and parser size limits reject invalid or oversized data and are not
  presentation widths;
- compact non-TTY receipts such as Trace retain operation-owned summary budgets,
  but their cell measurement and ellipsis use the shared geometry policy;
- `TuiTableColumn` widths define a horizontally navigable grid whose selected
  cell is also rendered in full, so the grid schema remains caller-owned; and
- compact orientation panels may retain a bounded preview when a complete
  pane or detail surface is available.

Treating those cases as one global maximum would erase semantic distinctions
and make compact automation output depend on the invoking terminal.

## Rollout and limitations

Session, History, Compare, and Result interactive rows are the first adaptive
consumers. Existing Ground, Meld, Atomize, table, Memory Picker, Compare CLI,
and Trace elision helpers now delegate terminal-cell fitting to the shared
module while retaining their operation-specific preview policies.

The first render uses the terminal width minus caller-declared chrome because
prompt-toolkit has not produced `WindowRenderInfo` yet. Subsequent renders and
terminal resizes use the exact content width excluding margins. Split panes
must pass their own Window rather than infer a fraction of the whole terminal.
