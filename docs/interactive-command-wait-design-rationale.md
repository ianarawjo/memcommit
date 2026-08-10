# Interactive command wait design rationale

## Problem and scope

Compare, Meld, Forget, Sever, and Update can each own one intentionally indivisible
semantic turn for several minutes. The existing `CommandProgress` heartbeat
proved liveness and elapsed time, but the foreground command remained blocked.
In a Study run this made the participant wait without being able to learn the
available command vocabulary, even though `mem help` already contains the
audited command descriptions and forms. A generic progress box also gave no
orientation to the report being constructed or to the exact inputs the person
had just frozen.

The shared interactive wait keeps that semantic work whole while allowing a
read-only Help session in the same process and terminal. It is used for the
aggregate analysis in Compare, Forget, and Sever; every provider-backed
assessment turn in Meld, including issue replies and `INCORPORATE RESPONSES`;
and Update's initial plan and whole-proposal comment revision. Other call sites
that still use `CommandProgress` retain the one-line heartbeat until their
operation adapters are migrated deliberately.

## Interaction contract

In an interactive terminal, `run_command_wait` starts the frozen operation in
an executor and gives the foreground to one operation-neutral waiting TUI. The
screen reports only real host-owned stages and elapsed time; it does not invent
a provider percentage. Its default foreground is the operation-owned report
surface: an existing complete report during a Meld follow-up, or a report-shaped
loading skeleton during first analysis. `C` toggles a separately frozen
`CONFIRMED INPUTS` copy, and `H` or `?` opens the same command inventory,
category order, descriptions, and audited forms used by `mem help`. `H` inside
Help returns to whichever report or input copy was previously visible. None of
these switches restarts or alters the frozen worker. The progress header remains
above every host surface and reports only host-owned stages and elapsed time.

Both views are supplied by the operation as frozen values; the common shell
owns only switching, wrapping, and scrolling. Meld follow-up turns restore the
immediately preceding complete report and show the submitted turn separately
as not yet incorporated. Update comment revisions likewise retain the complete
reviewed staged report and show the submitted comment as not yet incorporated.
A first Compare, Forget, Sever, Meld, or Update analysis has no result report
yet, so the default surface shows only its expected section topology and
one shared busy marker under each section. It is explicitly labeled
`CONTENT PENDING · THIS IS NOT A RESULT`; it contains no inferred prose,
decision, count, or recommendation. The markers reuse the command progress
contract's `.`, `..`, `…` frames and cadence, staggered across sections so a
still screen also communicates the sequence. This keeps the loading grammar
font-independent and uses the same liveness signal in the header and report
body. Flow Circular remains appropriate for placeholders derived from known
text, but a result-free wait has no prose shape to preserve. The markers use a
legible neutral gray: softer than completed report prose, but neither Memory
lavender nor focused-control blue.

`C` exposes the exact frozen setup facts instead: selected Contexts and scope,
frozen counts where already available, the Forget instruction, submitted Meld
turn, the Update Source→Target route and submitted revision comment, and any
not-yet-created output name. `C` returns to the report surface.
Both surfaces are read-only because changing a source or response while the
provider owns the turn would invalidate the frozen request.

The nested Help application runs in `EXPLORE` mode:

- Up/Down, category/A–Z selection, expansion, scrolling, and form inspection
  remain available.
- Enter and Right may reveal descriptions and forms, but cannot return a shell
  template, execute a command, or mutate storage.
- `H` hides Help; `Q` or Escape also returns to the waiting operation. From
  either report or confirmed-input view, `H` reopens the same frozen inventory.
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

Outside an interactive stdin/stdout terminal, `run_command_wait` executes the
same work synchronously through `CommandProgress`. Stable stdout and redirected
command behavior therefore remain unchanged.

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

The wait surface emits content-free `TUI_ACTION` records for confirmed-input
open/close, Help lifecycle transitions, explicit `H` hides, command expansion,
form inspection, report/input scrolling, and result/error readiness. Command
names are public inventory identifiers; raw arguments, Memory text, provider
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

The first-analysis topology was separately replayed with a deterministic
Compare wait: report skeleton, `C` confirmed inputs, `H` Help, `H` back to the
same confirmed inputs, and `C` back to the skeleton. The header advanced from
`CONNECTING PROVIDER` to `ANALYZING RELATIONS`; no switch restarted the worker,
and every skeleton row remained visibly distinct from result prose.

Update's migrated path was then captured through the real Typer command in a
color-capable 180×52 PTY. Its initial report reused the shared `.`, `..`, `…`
cadence under `PLAN`, `WHAT WILL CHANGE`, `PLANNED CHANGES`, and `TO DO`.
`C` exposed the frozen Source→Target route, `H` opened the complete root
inventory, `H` restored those confirmed inputs, and `C` returned to the
animated report while the deterministic provider continued. Closing the
resulting staged review left both Contexts unchanged and retained exactly one
staged receipt. The ordered ANSI evidence, text screens, PNGs, and reproduction
driver are under
[`screenshots/mem-update-command-wait-20260810/`](screenshots/mem-update-command-wait-20260810/).

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
- Fabricated report prose was rejected for first analysis. The skeleton shows
  only stable section shape and explicitly denies result status; exact source
  facts live behind `C` instead.
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
