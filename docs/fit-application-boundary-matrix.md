# Fit application boundary matrix

## Purpose

Fit evaluates every active Ground Example against the active Rules of one
exact saved Ground revision. It changes no Ground content. A successful new
run publishes one immutable derived receipt; reopening a receipt performs no
provider call and reports whether that exact receipt is still current.

This matrix records the boundary while Fit is added to the repository-wide
operation and shared-TUI ledgers. The intent is to share mechanics without
moving Fit's meaning into a terminal component.

## Boundary matrix

| Layer | Owns | Must not own |
| --- | --- | --- |
| Domain/application | Fit Rules, Examples, judgments, statuses, report digest, Ground revision/digest, strict provider decoding | Terminal detection, ANSI styling, keybindings, clipboard state |
| Runtime/infrastructure | Ground load/freeze, provider construction, exact-revision publication, immutable receipt store, current/stale lookup | CLI prose or TUI section layout |
| Plain CLI adapter | Stable line-oriented projection of one typed `FitReport` plus explicit current/stale state | Provider calls, Ground loading, receipt freshness decisions |
| TUI operation adapter | Typed semantic Viewer document, stable section identities, focused and whole-document clipboard projections | Re-parsing plain output or changing Fit judgments |
| Shared semantic Viewer | Focus, scrolling, read-only close, copy-key dispatch, copy status | Which Fit fields compose an Example section or what a status means |
| Ground shell adapter | When its Cases surface requests Fit and how the returned report refreshes Ground-local state | Thread/executor lifecycle or a second Fit implementation |
| Shared background turn | Mutual exclusion, animation, ContextVar propagation, non-abandoning executor shutdown, deferred close | Ground refresh, Fit success text, provider selection, receipt semantics |

## Request and result contracts

The executable request is one exact saved Ground name and either:

- no receipt selector, meaning freeze, evaluate, and atomically save a new Fit
  receipt; or
- one exact receipt UID, meaning reopen that immutable report and compare it
  with the current Ground-derived receipt state.

Both plain and interactive adapters consume the same typed `FitReport` and an
explicit `current: bool`. Neither adapter may infer freshness from rendered
text. The TUI projection assigns stable identities to title, status, overview,
each Example judgment, totals, and receipt evidence. Lowercase `y` copies the
focused semantic section; uppercase `Y` copies the complete typed report.

## Invariants

1. Forced TUI availability is validated before opening storage or connecting a
   provider.
2. A receipt reopen never connects to a provider or writes another receipt.
3. A new run publishes no receipt unless every active Example receives exactly
   one valid judgment for the frozen Rule/Example frame.
4. Publication fails if the Ground revision or digest changed after freezing.
5. Plain output remains the automatic non-TTY behavior and is available
   explicitly with `--plain`.
6. TUI projection consumes typed fields directly; it never parses the plain
   renderer.
7. Ground's embedded run and standalone Fit use the same application/runtime
   execution, even though their presentations differ.

## Shared components and intentional limits

This slice reuses `interfaces.tui.viewers.semantic`,
`components.plain_text_clipboard`, the console router, and
`components.background_turn`. Fit-specific aliases, statuses, reasons,
observations, totals, and receipt evidence remain in the Fit adapter.

The Ground Case table and cards are intentionally not relocated. Their current
legacy table owner has more than one consumer, so moving them requires a
separate inventory and parity pass. Fit also does not join hidden Study
prewarming in this slice: an immutable Fit receipt is an explicit derived
artifact tied to a Ground revision, not evidence that the operation satisfies
the prepared-analysis cache contract.

## Verification gate

The slice is complete only when tests cover application execution without a
terminal, stable plain rendering, automatic and forced console routing,
current and stale receipt reopening, typed Viewer projection, focused and
whole-document copy, duplicate embedded runs, close during a running turn, and
ordered 180x52 color PTY evidence.
