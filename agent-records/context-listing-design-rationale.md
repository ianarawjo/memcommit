# Static Context listing and interactive switching

Last reviewed: 2026-08-20.

## Decision

`mem list` / `mem ls` and `mem contexts` are terminal-independent reporting
commands. They print their result immediately whether stdout is a terminal or
a pipe. Top-level interactive Context navigation belongs to bare `mem switch`.

- Bare `mem list` / `mem ls` lists the current Context. An explicit operand
  lists that resolved Context. Direct scope is the default and `-r` / `-R`
  expands the resolved recursive scope.
- `mem contexts` lists the readable Profile catalog and marks the current
  Context. It does not open Context contents for exploratory preview.
- Bare `mem switch` opens the interactive namespace picker. An explicit
  operand keeps Switch scriptable and applies its existing validation and CAS
  boundary.

Operation-owned setup screens may still compose the shared Context tree when
they need a visible selection. This decision concerns the top-level reporting
commands, not the reusable picker component.

## Motivation

The browser experiment made `list` expose two competing scopes. Its executable
and copied result was rooted at one Context, while its terminal presentation
also exposed parents, siblings, and unrelated Profile roots. A person asking
for the current Context's list could therefore appear to have entered a
different navigation operation. `contexts` likewise duplicated much of bare
Switch without performing a switch.

Making unrelated rows grayscale would change emphasis but preserve the same
ambiguity: rows outside List's requested result would remain navigable inside
List. Cropping the browser to the target subtree would instead duplicate the
static listing with keyboard overhead. Stable output makes the command name,
visible range, clipboard snapshot, and automation contract agree.

## Invariants

- `list` and `contexts` never wait for terminal input and do not import the
  Context TUI.
- TTY and non-TTY invocations use the same semantic scope and line-oriented
  renderer. ANSI styling may still mark the current Context when supported.
- List continues to resolve and authorize its exact operand before freezing
  direct or recursive output. This change does not broaden Grant authority or
  alter `--copy`, `--paste`, MemoryRef, cycle, or query-view handling.
- Contexts continues to show ordinary local names and valid visible Grant
  routes with the current marker. It remains read-only and never changes the
  current pointer.
- Switch remains the only command in this trio whose accepted Context can
  continue to the global current-pointer mutation.

## Compatibility and retained history

Scripts already received the static format, so the output schema is unchanged.
The compatibility break is intentional for interactive terminals: bare List
and Contexts no longer launch a full-screen application. The earlier terminal
captures remain in the repository as prototype history, labelled superseded;
they are not current behavioral evidence.

No new navigation flag is introduced. A person who wants to move around the
Profile tree uses `mem switch`; a person who wants a broader List result asks
for it explicitly with the recursive scope flag.

The current terminal evidence is recorded under
[`screenshots/mem-static-list-contexts-20260820/`](screenshots/mem-static-list-contexts-20260820/README.md).
It runs the exact commands in a verified `180×52` color PTY and records both
the visible output and the unchanged current Context.
