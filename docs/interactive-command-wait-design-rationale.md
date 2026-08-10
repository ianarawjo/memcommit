# Interactive command wait design rationale

## Problem and scope

Compare, Meld, Forget, and Sever can each own one intentionally indivisible
semantic turn for several minutes. The existing `CommandProgress` heartbeat
proved liveness and elapsed time, but the foreground command remained blocked.
In a Study run this made the participant wait without being able to learn the
available command vocabulary, even though `mem help` already contains the
audited command descriptions and forms.

The shared interactive wait keeps that semantic work whole while allowing a
read-only Help session in the same process and terminal. It is currently used
for the initial aggregate analysis in Compare, Meld, Forget, and Sever. Other
call sites that still use `CommandProgress` retain the one-line heartbeat until
their operation adapters are migrated deliberately.

## Interaction contract

In an interactive terminal, `run_command_wait` starts the frozen operation in
an executor and gives the foreground to one operation-neutral waiting TUI. The
screen reports only real host-owned stages and elapsed time; it does not invent
a provider percentage. `H` or `?` suspends that screen and opens the same
command inventory, category order, descriptions, and audited forms used by
`mem help`.

The nested Help application runs in `EXPLORE` mode:

- Up/Down, category/A–Z selection, expansion, scrolling, and form inspection
  remain available.
- Enter, Right, and `H` may reveal descriptions and forms, but cannot return a
  shell template, execute a command, or mutate storage.
- `Q` or Escape returns to the waiting operation.
- If work finishes while Help is open, the Help header changes to
  `RESULT READY` (or `ERROR READY`) and remains open. The participant chooses
  when to return; completion never yanks focus away from what they are reading.

After Help closes, the original command receives the completed value or error
and continues through its unchanged review, revalidation, save, and apply
boundaries. Help does not receive provider input, Memory content, result data,
or a writable command composer.

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

The wait surface emits content-free `TUI_ACTION` records for opening and
closing Help, expanding a command, inspecting a form or detail, and result/error
readiness. Command names are public inventory identifiers; raw arguments,
Memory text, provider payloads, and output remain excluded.

The worker inherits the command's `ContextVar` state so provider and command
attempt telemetry is not lost merely because the TUI became responsive. Help
navigation and provider events can be produced concurrently, so the active
Study recorder serializes durable appends under one lock and preserves one
gap-free attempt sequence.

## Verification

On 2026-08-10 the shared helper was exercised in a real color-capable
180-column by 52-row PTY with the complete root inventory (54 visible
commands) and a deterministic three-stage background worker. No Profile or
Context was opened or changed. The ordered keys were `H`, `Down`, `Down`,
`Right`, a further `Down` after completion, and `Q`.

The initial wait screen continued advancing its honest stages while Help was
open. The arrows reached `mem list`, Right expanded all seven audited forms,
and completion changed the Help header to `RESULT READY · Q RETURN` without
closing the browser. Navigation remained active after readiness; `Q` then
returned the worker's exact result. Automated pipe-input tests reproduce the
same ordering and additionally verify that Study Help and executor events keep
one gap-free sequence.

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
- The provider primitive remains non-cancellable. The UI can defer closing but
  cannot truthfully claim that a remote request was stopped.
- Only migrated operations receive interactive Help today. The shared helper
  is operation-neutral, but each remaining blocking adapter must preserve its
  cache, staging, validation, and mutation boundaries before migration.
