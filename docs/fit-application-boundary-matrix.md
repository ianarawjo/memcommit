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
| Plain CLI adapter | One stable summary line derived from a typed `FitResult` | Provider calls, Ground loading, receipt freshness decisions, full receipt expansion |
| TUI operation adapter | Compact summary and Example sections, issue-only reasons, focused and whole-document clipboard projections | Re-parsing plain output, session state, or changing Fit judgments |
| Shared semantic Viewer | Focus, scrolling, read-only close, copy-key dispatch, copy status | Which Fit fields compose an Example section or what a status means |
| Ground shell adapter | When its Memories surface requests Fit and how `·`, `✓`, `!`, and `◷` project the returned state | Thread/executor lifecycle, Fit detail prose, or a second Fit implementation |
| Shared background turn | Mutual exclusion, animation, ContextVar propagation, non-abandoning executor shutdown, deferred close | Ground refresh, Fit success text, provider selection, receipt semantics |

## Request and result contracts

The executable request is one exact saved Ground name and either:

- no receipt selector, meaning freeze, evaluate, and atomically save a new Fit
  receipt; or
- one exact receipt UID, meaning reopen that immutable report and compare it
  with the current Ground-derived receipt state.

Both plain and interactive adapters consume the same typed `FitReport` and an
explicit `current: bool`. Neither adapter may infer freshness from rendered
text. Fit is not a workbench session: the only durable result is the immutable
receipt. That receipt retains the provider overview, exact statuses, reasons,
observations, identities, and digests even though ordinary presentation omits
them.

The shared compact marks are:

- `·`: no judgment has been run for the Ground Memory;
- `✓`: the current receipt judges the Example `FIT`;
- `!`: the current receipt reports any non-`FIT` status; and
- `◷`: a receipt exists but no longer describes the current Ground revision.

Non-interactive output is exactly one summary line. The TUI assigns stable
identities only to the summary and Example rows; it shows a classification and
one reason only for a current `!`. It deliberately omits `WHAT MEM UNDERSTOOD`,
provider, totals, digest, and receipt chrome. Lowercase `y` copies the focused
compact section; uppercase `Y` copies the complete compact Viewer projection.

## Invariants

1. Forced TUI availability is validated before opening storage or connecting a
   provider.
2. A receipt reopen never connects to a provider or writes another receipt.
3. A new run publishes no receipt unless every active Example receives exactly
   one valid judgment for the frozen Rule/Example frame.
4. Publication fails if the Ground revision or digest changed after freezing.
5. Plain output remains the automatic non-TTY behavior, is exactly one line,
   and is available explicitly with `--plain`.
6. TUI projection consumes typed fields directly; it never parses the plain
   renderer.
7. Ground's embedded run and standalone Fit use the same application/runtime
   execution, even though their presentations differ.
8. Compact presentation never removes evidence from the persisted receipt or
   weakens exhaustive one-judgment-per-Example validation.

## Shared components and intentional limits

This slice reuses `interfaces.tui.viewers.semantic`,
`components.plain_text_clipboard`, the console router, and
`components.background_turn`. Fit-specific aliases and issue reasons remain in
the Fit adapter; full observations and receipt evidence stay below the
presentation boundary.

The named Ground keeps its saved-Memory list and Enter detail in the Ground
adapter; a later presentation pass removed its redundant `V` table without
moving Fit meaning into shared UI. The blank first-turn draft flow still owns a
separate table projection and remains a separately characterized migration.
Fit also does not join hidden Study prewarming in this slice: an immutable Fit
receipt is an explicit derived artifact tied to a Ground revision, not evidence
that the operation satisfies the prepared-analysis cache contract.

## Verification gate

The slice is complete only when tests cover application execution without a
terminal, stable plain rendering, automatic and forced console routing,
current and stale receipt reopening, typed Viewer projection, focused and
whole-document copy, duplicate embedded runs, close during a running turn, and
ordered 180x52 color PTY evidence.

## Verification evidence

Completed 2026-08-15:

- application/runtime and CLI tests preserve new-run and receipt-reopen
  behavior, stable non-TTY output, `--plain`, and pre-storage `--tui` failure;
- typed adapter tests cover compact section identities, all-fit/issue/stale
  marks, focused Example copy, complete compact copy, and one-line plain text;
- shared Viewer interaction tests exercise lowercase `y` and uppercase `Y` in
  a real prompt-toolkit pipe;
- named-Ground tests cover all four marks, prove one executor call during
  repeated `F`, and require a requested close to wait for the receipt callback;
- `docs/screenshots/mem-fit-shared-viewer-20260815` retains the ordered
  `180 × 52` true-color PTY stream, native PNGs, plain canvases, exact inputs,
  and read-only verification.
