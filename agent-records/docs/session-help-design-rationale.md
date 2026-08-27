# Shared session Help design rationale

## Problem and scope

The blocking command-wait screen already allowed `H` or `h` to open the
read-only `mem help` inventory and the same key to hide it. Long-lived Query,
Find, Compare, Result, Resolution, and Ground sessions each owned independent
prompt-toolkit `Application` and `KeyBindings` objects, so none inherited that
behavior. Adding a Query-only binding would have repeated the same nested
Application lifecycle in every later session.

Session Help is therefore one operation-neutral handoff implemented by
`memcommit.adapters.console.commands.shared.session_help`. It is adopted by Query, Find search and
chat, Compare, Result, the shared Resolution workbench, and both blank and
named Ground shells. Resolution covers Meld, Sever, Update, Atomize, Forget,
Impact, and adaptive Review without operation-specific bindings. The common
command-wait screen now uses the same controller while retaining its special
result-ready behavior.

SessionPicker, setup screens, Context/Profile/history pickers, exact-name
dialogs, and paste controls remain outside this rollout. They are launchers or
short-lived modal controls rather than an active semantic session. Legacy
Atomize, Meld, and Review shell implementations are not patched when their
production entry points already route through the shared Resolution shell.

## Interaction contract

On a read-only or navigation surface, `H` and `h` open one nested Help browser
in `EXPLORE` mode. The root command inventory is frozen before the handoff.
Help can inspect categories, descriptions, and audited Forms, but cannot
return a shell template, execute a command, call a provider, or mutate
operation state. `H` or `h` inside Help hides it; `Q`, `q`, or Escape also
returns to the parent session.

The parent Application remains alive and retains its layout, exact focus,
buffers, selections, background turn, and operation-owned state. The nested
Help Application alone owns terminal input during the handoff. An `OPEN`
boundary is emitted only after Help has acquired that input, and an `_open`
guard prevents two concurrent nested Applications when keys arrive quickly.
Closing Help invalidates the parent for repaint. Command-wait instead exits
the parent after Help closes when its frozen worker has already reached
result-ready or error-ready.

Help receives only the public command inventory and an optional display-only
status supplier. It does not receive Context names, Memory content, response
drafts, provider payloads, or executable receipts. Session Help lifecycle and
public command-expansion actions use content-free Study action records under
the owning session surface.

## Writable-input boundary

Plain alphabetic shortcuts cannot be global while a person is composing text.
Every caller must filter Session Help out of its writable Question, Search,
Message, Response, Comment, direct-edit, and exact-name fields. In those fields
both `h` and `H` remain ordinary text. Query therefore exposes Help from
Sources, Scope, and Answer; its initially focused Question remains writable.
Find and Ground follow the same read-pane boundary, and Resolution excludes
both Response and Save Location input.

This deliberate asymmetry matches the existing case-insensitive `Q` close
shortcut: Shift or Caps Lock does not change navigation meaning, while
operation text is never made impossible to type. Session footers advertise
`H Help` only where the shortcut is active.

## Verification

Focused regression coverage exercises the real nested prompt-toolkit handoff
with pipe input, including uppercase open, lowercase hide, exact parent-focus
restoration, duplicate-open prevention, and ordinary `hH` input in a writable
field. Query coverage separately proves that `hH` remains part of a submitted
question and that Help is bound after focus leaves the Question.

The interaction was also replayed in a color-capable 180-column by 52-row PTY:
Query opened on Question, Tab moved to Sources, `H` opened
`mem help · session guide`, and `H` returned to the same selected Sources row.
The raw stream contained the shared blue focused frame and selected-row ANSI
styles before and after the handoff. No provider was connected and no Context
or session record was created or changed.

The focused shell suite passed 426 tests. A full repository run passed 2,699
tests; its remaining failures were an already-divergent Atomize text capture
and the unrelated frozen Task 2 discovery-corpus lock mismatch. Neither
failure touches the Help controller, its callers, or their focused suites.

## Limitations

`H` is intentionally unavailable while a writable field owns focus. A person
in Query's initial Question moves to a read-only surface with Tab before
opening Help; reserving `H` globally would make normal questions impossible to
type. The Help inventory is frozen for one parent session, so commands added by
dynamic external mutation do not appear until a new session starts. Help is a
full-screen terminal handoff rather than a floating overlay because nested
prompt-toolkit input ownership is explicit and already proven by the
command-wait workflow.
