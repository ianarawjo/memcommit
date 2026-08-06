# `mem help` design rationale

## Intent

The default Typer help output proves that a command is registered, but its
syntax-first layout is harder to scan as a complete command inventory. That
distinction matters while building the study prototype and when preparing its
printed cheat sheet.

`mem help` therefore renders one concise inventory line per visible registered
command:

```text
name [(exception)] - short description
```

It reports capabilities; it does not recommend a command sequence or perform
work for the participant.

## Interactive terminal contract

In an interactive terminal, `mem help` presents the inventory as a
prompt-toolkit selector:

- Up and Down move one command at a time or move among one expanded command's
  forms.
- Page Up, Page Down, Home, and End move through the longer list.
- Right or the first Enter expands one command in place. The second Enter moves
  the focus bar to its first `FORM`; Up and Down then inspect the alternative
  invocations. Left returns from a Form to its command row and then collapses
  the command.
- Enter on a focused Form, or `H` from the command row, closes the selector,
  prints `Command: mem <name>`, and renders that registered command's complete
  syntax help in the ordinary CLI path.
- `q`, Escape, and Ctrl-C cancel without selecting or invoking anything.

The selected command's callback is deliberately never invoked. Some commands
can change local state with no additional arguments, while other commands
require operands or provider work. Treating a single Enter in a help browser
as execution would therefore make inspection unexpectedly mutate state or
produce an avoidable usage error.

The child `mem help` process cannot itself prefill its parent shell's next
editable command line. The opt-in output of `mem shell-init zsh` now supplies
a parent-shell wrapper for zsh: its private selection mode keeps the TUI on
the terminal, returns one validated command name to the wrapper, and uses
zsh's `print -z` to prefill without executing. Bash Readline and Fish still
need their own integrations. Unsafe terminal input injection is not used.
See [`mem-zsh-prefill-design-rationale.md`](mem-zsh-prefill-design-rationale.md)
for that shell-owned boundary.

When stdin or stdout is not a TTY, `mem help` retains the stable plain-text
inventory. This keeps pipes, captured study records, and automated tests
deterministic instead of emitting a terminal-control interface.

## Exceptional annotations

Ordinary commands carry no implementation label. Repeating `implemented` on
nearly every row adds noise without helping a person choose a command. A
parenthesized annotation is reserved for exceptional compatibility state:
`integrate (legacy)` and `config (legacy)` remain callable but sit outside the
current workflow. Ordinary TUI entry is described inside the expanded Forms
instead of repeating a badge across the inventory.

## Invocation forms

Expansion lists complete meaningful entry forms rather than presenting one
generic Click usage line. For example, Meld distinguishes bare saved-work
browsing, symmetric peers, a require-new symmetric Result, canonical
`INCOMING --into BASELINE`, and the current-Baseline `--from` convenience form.
Each form includes a short parenthesized semantic label when the operands alone
would not explain the route.

Simple commands derive one conservative form from their registered positional
operands. Commands with several semantic entry routes keep an explicit bounded
form list. This list intentionally omits action flags such as comments,
responses, snapshots, and acceptance controls; `H` retains the complete
registered syntax reference. Forms are explanatory and are never executed.

A deliberately bounded command needs no exception annotation when its
advertised contract is available. For example, `merge` intentionally performs
structural UID union without semantic reconciliation, and `diff` intentionally
renders the active update rather than comparing arbitrary Contexts. The
inventory describes the contract people can actually invoke, not a broader
operation suggested by the command's name or a production-readiness claim.
Individual commands may still have documented permission, provider,
concurrency, or remote-persistence boundaries.

An implementation can expose two co-equal public spellings through one
internal callback. `mem list` and `mem ls` deliberately have the same
description: participants may learn and use either spelling. A compatibility
alias such as `checkout` identifies its canonical `switch` and `branch`
operations directly in its description instead of adding another status
column.

## Consistency boundary

Descriptions are read from the same Click/Typer command registrations used by
`mem --help`; the inventory does not maintain a second description catalog.
Exceptional annotations and multi-route invocation forms are explicit because
compatibility status and semantic entry routes cannot be inferred safely from
Click registration alone.

The renderer fails closed if an annotated command is no longer registered.
Ordinary new commands need no redundant `implemented` entry.

Only callable visible commands are listed. Proposed but unregistered
operations are omitted rather than shown as commands a participant could try.
Their design state remains in the focused operation rationale documents and
the external function inventory.

## Relationship to `mem --help`

`mem --help` remains Typer's syntax-oriented reference, including global
options. `mem help` is the compact implementation inventory and interactive
syntax browser. Per-command syntax continues to use:

```text
mem <command> --help
```
