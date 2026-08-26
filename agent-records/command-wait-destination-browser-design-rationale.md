# Command-wait destination browser design rationale

## Problem

The review-replacement wait footer previously used `C` as a toggle between the
prior report and frozen submitted inputs. Its meaning therefore depended on
the currently visible surface, lower-case input was not part of the displayed
contract, and there was no safe way to inspect the Context namespace while the
reviewed replacement turn was still running.

## Destination contract

The wait shell now assigns one stable destination to each case-insensitive
key:

- `C/c` opens a switch-shaped Context browser.
- `I/i` opens the operation's exact frozen confirmed inputs, when supplied.
- `R/r` opens the previous completed review report.
- `H/h/?` opens the shared read-only Help inventory.

Each letter remains a stable named destination on its first press. An
immediate repeat of that same letter returns to the surface from which that
destination was opened: `C/c`, `I/i`, and `R/r` use the common wait-shell
handoff, while `H/h` uses Help's existing open/hide lifecycle. Pressing a
different destination establishes a new origin for that key pair. The footer
changes the active key's label to `back` only when such an origin exists.

The footer and bindings are derived from the same available review surfaces.
`I/i` is absent and unbound without a submitted-input view. Initial analysis
has neither surface and uses the one-line progress path instead. This keeps a
shortcut from advertising a destination that the operation cannot show.

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
- The former anonymous `C` toggle between report and inputs was rejected
  because it gave one key two unnamed destinations. Repeat-to-return is kept
  only after a key first reaches its explicitly named Context, input, report,
  or Help surface.
- Memory rows remain previews, not selectors. Supporting selection here would
  require a new operation-owned receipt and is intentionally out of scope.
- The Context-name catalog is frozen, while Memory content is loaded lazily
  when a person asks to view it. Concurrent disappearance therefore produces
  an unavailable preview without changing the catalog or durable state.

## Verification record

Pipe-input tests exercise upper- and lower-case destinations, same-key return
for Contexts, inputs, the previous report, and Help, conditional bindings,
interleaved Memory navigation, and a guard that fails if
`MemoryStore.set_current()` is reached from the browser. The dated Update and
Meld captures under `agent-records/screenshots/mem-update-command-wait-20260810` and
`agent-records/screenshots/meld-auto-compare-basis-20260810` preserve the earlier
first-analysis skeleton rollout as historical evidence; they are not the
current initial-analysis contract. The current 180×52 evidence under
`agent-records/screenshots/inline-semantic-analysis-20260821` shows the one-line initial
path and a separate prior-review replacement path.
