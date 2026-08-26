# Interactive command wait design rationale

## Problem and scope

Meld and Update can own an intentionally indivisible replacement turn for
several minutes after a person has reviewed a complete report and submitted
guidance. Replacing that report with an empty loading screen discards useful
review context, while blocking on only a progress line prevents the person from
rechecking the exact report and comment that are being incorporated.

The shared interactive wait therefore has one narrow purpose: keep the
previously completed review report visible and read-only while its submitted
Meld or Update revision runs in the background. Initial Compare, Meld, Forget,
Sever, and Update analysis has no completed report to preserve and uses the
shared transient one-line `CommandProgress` instead. Audit's ordinary initial
route already uses the same line across its ordered checks. This avoids
presenting report-shaped chrome before a semantic result exists and avoids a
full-screen interruption for work that may immediately complete or auto-apply.

## Interaction contract

When `run_command_wait` receives no prior review view, it runs the frozen work
synchronously behind `CommandProgress`, including in an interactive terminal.
The transient line reports only real host-owned stages and elapsed time; it
does not invent a provider percentage. The line is erased before the completed
result, review, receipt, or error is rendered.

When a caller supplies a previous completed review, `run_command_wait` starts
the replacement turn in an executor and gives the foreground to the shared
read-only waiting TUI. `C` opens a frozen Context browser, `I` opens the exact
submitted inputs, and `R` returns to the previous report. Repeating an active
destination key returns to the surface that opened it. `H` or `?` opens the
same command inventory, category order, descriptions, and audited forms used
by `mem help`; `H` inside Help restores the originating surface. None of these
switches restarts or alters the frozen worker. The progress header remains
above every review surface and reports only host-owned stages and elapsed time.

The prior-report and submitted-input views are supplied by the operation as
frozen values. The common shell independently freezes the Profile navigation
catalog and owns only switching, wrapping, scrolling, and read-only Context
previews. Meld follow-up turns restore the immediately preceding complete
report and show the submitted turn separately as not yet incorporated. Update
comment revisions likewise retain the complete reviewed staged report and
show the submitted comment as not yet incorporated.

A first analysis never supplies these views. Source, target, authority, cache,
and output facts are still frozen by the operation before provider work; they
are simply not projected as an interactive screen while no review exists.
The completed operation then chooses its normal review, auto-apply, read-only
result, or receipt path. This presentation decision does not widen authority
or bypass post-analysis validation.

`C` exposes the Profile's command-start Context namespace using the shared
switch-shaped tree. Ordinary local and READ-granted Contexts may reveal their
read-only direct-Memory previews. Opaque public Grant roots, including QUERY
grants, are also visible with their exact permission annotation and
`UNAVAILABLE`, but are not materialized Context rows: Enter, expansion, and
all-Memory browsing never send them to the ordinary Context loader. The browser
cannot switch the current Context or produce a selection receipt.

`I` exposes the exact frozen setup facts instead: selected Contexts and scope,
frozen counts where already available, the Forget instruction, submitted Meld
turn, the Update Source→Target route and submitted revision comment, and any
not-yet-created output name. All three host surfaces are read-only because
changing a source or response while the provider owns the turn would invalidate
the frozen request.

The nested Help application runs in `EXPLORE` mode:

- Up/Down, category/A–Z selection, expansion, scrolling, and form inspection
  remain available.
- Enter and Right may reveal descriptions and forms, but cannot return a shell
  template, execute a command, or mutate storage.
- `H` hides Help; `Q` or Escape also returns to the waiting operation. From the
  report, Context browser, or confirmed-input view, `H` reopens the same frozen
  inventory.
- If work finishes while Help is open, the Help header changes to
  `RESULT READY` (or `ERROR READY`) and remains open. The participant chooses
  when to return; completion never yanks focus away from what they are reading.

The `HELP OPEN` interaction boundary is emitted only after the nested Help
application owns terminal input. Scheduling the handoff is not sufficient: a
fast key sequence or pipe-driven Study replay could otherwise send its first
Help key back to the waiting application during the transition.

If Help closes before work completes, the previously visible operation view
remains live, scrollable, and able to reopen it. Once work is complete, closing Help returns
the completed value or error to the original command, which continues through
its unchanged review, revalidation, save, and apply boundaries. Help does not
receive provider input, Memory content, result data, or a writable command
composer.

Outside an interactive stdin/stdout terminal, every turn executes synchronously
through `CommandProgress`. Stable stdout and redirected command behavior remain
unchanged.

## Execution and consistency invariants

Moving host execution to an executor does not authorize semantic
decomposition. Compare and Meld still analyze their complete frozen relation
frame, and Forget and Sever still preserve their whole-frame selective
curation contract. The worker returns no partial result to the command.

The foreground Help inventory is frozen before the worker starts. It cannot
observe or change the active Context, Profile, command receipt, provider
request, or operation target. Provider completion does not persist an analysis
by itself: the operation's existing post-call validation and save boundaries
remain authoritative.

Blocking provider calls are not safely cancellable. A close request on the
waiting screen is therefore deferred until the frozen work returns, after
which the command discards the result instead of entering review or save. Help
itself can always be closed independently with `Q` or Escape.

## Study recording

The wait surface emits content-free `TUI_ACTION` records for Context-browser
navigation and Memory-preview toggles, confirmed-input open/close, Help
lifecycle transitions, explicit `H` hides, command expansion, form inspection,
report/input scrolling, and result/error readiness. Command names are public
inventory identifiers; raw arguments, Context names, Memory text, provider
payloads, and output remain excluded.

The worker inherits the command's `ContextVar` state so provider and command
attempt telemetry is not lost merely because the TUI became responsive. Help
navigation and provider events can be produced concurrently, so the active
Study recorder serializes durable appends under one lock and preserves one
gap-free attempt sequence.

## Verification

On 2026-08-10 the shared helper was exercised in a real color-capable
180-column by 52-row PTY with the complete root inventory (54 visible
commands) and a deterministic three-stage background worker. No Profile or
Context was opened or changed. The original opt-in run used `H`, `Down`,
`Down`, `Right`, a further `Down` after completion, and `Q`.

Help's header continued advancing the worker's honest stages; hiding and
reopening it did not restart that worker.
The arrows reached `mem list`, Right expanded all seven audited forms, and
completion changed the Help header to `RESULT READY · H / Q RETURN` without
closing the browser. Navigation remained active after readiness; `H` then
returned the worker's exact result. Automated pipe-input tests reproduce the
same toggle ordering and additionally verify that Study Help and executor
events keep one gap-free sequence.

The operation-owned return view was then checked in the same 180×52 PTY with
a frozen Directional Meld follow-up. The previous report plus visibly
unincorporated submitted turn remained read-only and scrollable while `H`
opened and closed Help. The stage advanced from connection to analysis across
these switches, and the deterministic worker returned once without being
restarted.

The first-analysis policy was later tightened: deterministic Compare, Meld,
Update, Forget, Sever, and Audit turns now remain on the same transient progress
line until a complete result exists. Focused tests fail if an initial turn
freezes Help or constructs a return view, while Meld and Update follow-up tests
still require the previous complete report and the submitted guidance to be
present. The current ordered ANSI evidence and reproduction driver are under
[`screenshots/inline-semantic-analysis-20260821/`](screenshots/inline-semantic-analysis-20260821/).

A real Task 2 Directional Meld follow-up then exercised the production
provider boundary with 300 Source Memories. The provider received 122,310
characters, returned 71,419 characters in 459.43 seconds, and required no
repair call. `H` opened Help five seconds into the turn and `Q` returned to the
wait screen at nine seconds while the elapsed counter continued. The result
was saved as a non-applying `READY_TO_APPLY` assessment; the target remained
unchanged.

That first production rerun also exposed a packaging boundary before the
provider connected. Typer 0.27 vendors Click but does not re-export
`get_current_context` from `typer._click`. The wait helper therefore imports
the function from `typer._click.globals`, with external Click as the older
Typer fallback. Keeping this compatibility import at the inventory-freeze seam
prevents Help setup from crashing an otherwise valid semantic turn.

## Alternatives and limitations

- Starting a second `mem help` process was rejected. It would duplicate shell
  ownership, permit unrelated command execution, and allow Context or Profile
  state to change while the original result remained in flight.
- Printing the provider result underneath an active full-screen Help browser
  was rejected because asynchronous terminal output would corrupt the browser
  and could be missed. A visible `RESULT READY` state preserves both outputs.
- Passive rotating tips were rejected as the primary interaction because they
  choose what the participant sees and provide weaker evidence of
  self-directed discovery. They may be added later without replacing Help.
- A full-screen report skeleton was rejected for first analysis. Even an
  honestly labeled empty topology visually claims report space, interrupts the
  command for no review decision, and duplicates the liveness signal already
  carried by the progress line. Initial input facts remain frozen internally
  and appear in the completed operation's normal review or receipt when needed.
- The provider primitive remains non-cancellable. The UI can defer closing but
  cannot truthfully claim that a remote request was stopped.
- Re-entering the exact live setup or workbench `Application` was rejected for
  this boundary. Those applications have already returned a frozen receipt or
  submitted action, and making them writable again would let visible state
  diverge from provider input. The return view therefore reuses their semantic
  state as a read-only snapshot; it is not a second active editor.
- Only migrated operations receive interactive Help today. The shared helper
  is operation-neutral, but each remaining blocking adapter must preserve its
  cache, staging, validation, and mutation boundaries before migration.
