# Fit application boundary matrix

## Purpose

General Fit judges whether at least two already-stated propositions can jointly
hold under materially ordinary readings of one optional frozen background. It
changes and saves nothing. The existing Ground Rule–Example workflow is now an
explicit adapter: a successful Ground run publishes one immutable derived
receipt, while reopening that receipt performs no provider call and reports
whether it is still current.

This matrix records the boundary while Fit is added to the repository-wide
operation and shared-TUI ledgers. The intent is to share mechanics without
moving Fit's meaning into a terminal component.

## Boundary matrix

| Layer | Owns | Must not own |
| --- | --- | --- |
| Domain/application | Role-neutral propositions, frozen background, YES/MAY/NO, complete-coverage decoding; Ground report projection, digest, and revision identity | Terminal detection, ANSI styling, keybindings, clipboard state |
| Runtime/infrastructure | Whole-frame Fit planning before provider construction; Ground load/freeze, exact-revision publication, immutable receipt store, current/stale lookup | CLI prose or TUI section layout |
| Plain CLI adapter | One stable line derived from typed general or Ground Fit results | Provider calls, Ground loading, receipt freshness decisions, full receipt expansion |
| TUI operation adapter | General Judgment/Input/Readings sections and Ground summary/Example sections, plus focused and whole-document clipboard projections | Re-parsing plain output, session state, or changing Fit judgments |
| Shared semantic Viewer | Focus, scrolling, read-only close, copy-key dispatch, copy status | Which Fit fields compose an Example section or what a status means |
| Ground shell adapter | When its Memories surface requests Fit and how `·`, `✓`, `!`, and `◷` project the returned state | Thread/executor lifecycle, Fit detail prose, or a second Fit implementation |
| Shared background turn | Mutual exclusion, animation, ContextVar propagation, non-abandoning executor shutdown, deferred close | Ground refresh, Fit success text, provider selection, receipt semantics |

## Request and result contracts

The ordinary executable request is one complete proposition set and optional
background. It creates no receipt. The explicit Ground request is one exact
saved Ground name and either:

- no receipt selector, meaning freeze, evaluate, and atomically save a new Fit
  receipt; or
- one exact receipt UID, meaning reopen that immutable report and compare it
  with the current Ground-derived receipt state.

General plain and interactive adapters consume the same typed
`FitPropositionsResult`. Ground adapters consume the same typed `FitReport`
and explicit `current: bool`; neither infers freshness from rendered text.
General Fit is not a workbench session and has no durable result. The Ground
adapter's immutable receipt retains the provider overview, exact statuses,
reasons, observations, identities, and digests even when ordinary presentation
omits them.

The general compact marks are `✓` for `YES`, `?` for `MAY`, and `!` for `NO`.
The compatibility Ground marks remain:

- `·`: no judgment has been run for the Ground Memory;
- `✓`: the current receipt judges the Example `FIT`;
- `!`: the current receipt reports any non-`FIT` status; and
- `◷`: a receipt exists but no longer describes the current Ground revision.

Non-interactive output is exactly one summary line. General TUI sections expose
the judgment, complete frozen input, and both ordinary outcomes for `MAY`.
Ground TUI sections retain their compact summary and Example rows. Both omit
provider machinery and use lowercase `y` for the focused section and uppercase
`Y` for the complete typed Viewer projection.

## Invariants

1. Forced TUI availability is validated before opening storage or connecting a
   provider.
2. General Fit validates and budgets one complete set before provider
   construction, acknowledges every frozen input exactly once in order, and
   never creates a receipt.
3. A receipt reopen never connects to a provider or writes another receipt.
4. A new Ground run publishes no receipt unless every active Example receives exactly
   one valid judgment for the frozen Rule/Example frame.
5. Publication fails if the Ground revision or digest changed after freezing.
6. Plain output remains the automatic non-TTY behavior, is exactly one line,
   and is available explicitly with `--plain`.
7. TUI projection consumes typed fields directly; it never parses the plain
   renderer.
8. Ground's embedded run and standalone Fit use the same application/runtime
   execution, even though their presentations differ.
9. Compact presentation never removes evidence from the persisted receipt or
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

- the configured live provider returned `YES`, `NO`, and `MAY` for the
  controlled entrance contrast, including both ordinary readings for `MAY`;
- `docs/screenshots/mem-general-fit-20260815` retains seven ordered `180 x 52`
  true-color states from provider progress through zero-write verification;
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
