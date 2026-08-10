# Command-wait destination browser design rationale

## Problem

The interactive provider-wait footer previously used `C` as a toggle between
the report and frozen inputs. Its meaning therefore depended on the currently
visible surface, lower-case input was not part of the displayed contract, and
there was no safe way to inspect the Context namespace while a semantic turn
was still running.

## Destination contract

The wait shell now assigns one stable destination to each case-insensitive
key:

- `C/c` opens a switch-shaped Context browser.
- `I/i` opens the operation's exact frozen confirmed inputs, when supplied.
- `R/r` opens the report or honest report-building skeleton, when supplied.
- `H/h/?` opens the shared read-only Help inventory.

The footer and bindings are derived from the same available surfaces. `I/i`
is absent and unbound without a confirmed-input view. `R/r` is absent and
unbound when the command has no report surface. This keeps a shortcut from
advertising a destination that the operation cannot show.

## Context and Memory safety boundary

The `C/c` surface freezes the readable Profile Context-name catalog and the
current marker before background work begins. It reuses the shared Context
tree renderer and navigation state used by `mem switch`. `m` expands or hides
the selected Context's direct Memory previews; `M` does the same for all
visible Contexts. Up and Down then traverse Context and Memory rows as one
viewport sequence.

This resemblance to `mem switch` is presentational only. The embedded browser
has no accept action, selection receipt, current-Context setter, provider-input
path, or persistence callback. Enter on a Memory is explicitly preview-only;
Enter on a Context only expands or collapses its process-local tree or Memory
layer. Query-only grant routes are excluded because their hidden content is
not ordinary readable Memory input. A failed or concurrently changed preview
is rendered as unavailable inside the browser instead of widening authority or
restarting the frozen turn.

Direct Memory/MemoryRef projection lives in the common Context picker module
so `mem switch` and this browse-only surface cannot drift into two different
Memory grammars. The operation still owns all semantic inputs and every later
review, approval, CAS, and materialization boundary.

## Alternatives and limitations

- Reusing the actual `mem switch` accept path was rejected because a wait-time
  current-Context mutation would be unrelated to the already frozen semantic
  request and could falsely imply that the request followed the new current.
- Keeping `C` as a toggle was rejected because its result depended on prior UI
  state and left no stable key for the namespace browser.
- Memory rows remain previews, not selectors. Supporting selection here would
  require a new operation-owned receipt and is intentionally out of scope.
- The Context-name catalog is frozen, while Memory content is loaded lazily
  when a person asks to view it. Concurrent disappearance therefore produces
  an unavailable preview without changing the catalog or durable state.

## Verification record

Pipe-input tests exercise upper- and lower-case destinations, conditional
input/report bindings, interleaved Memory navigation, and a guard that fails if
`MemoryStore.set_current()` is reached from the browser. The real Update path
is recorded at 180 columns × 52 rows under
`docs/screenshots/mem-update-command-wait-20260810`: report entry, `c` Context
entry, `m` plus Down Memory focus, `i` inputs, `h` Help and return, `r` report,
review, and read-only verification. The symmetric Meld capture under
`docs/screenshots/meld-auto-compare-basis-20260810` separately verifies that
the default/R surface is the report and I is the frozen A/B/C input surface
while an unrelated current Context stays unchanged.
