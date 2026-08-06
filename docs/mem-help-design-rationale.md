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

- Up and Down move one command at a time.
- Page Up, Page Down, Home, and End move through the longer list.
- Enter closes the selector, prints `Command: mem <name>`, and renders that
  registered command's syntax help in the ordinary CLI path.
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
parenthesized annotation is reserved for useful exceptional invocation state:
`integrate (legacy)` and `config (legacy)` remain callable but sit outside the
current workflow, while `(bare → TUI)` says that entering the command without
operands in an interactive terminal opens its picker, launcher, browser, or
workbench. It does not promise that the command can proceed when required local
state, such as a current Context or saved session, is absent.

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
Exceptional annotations are explicit because compatibility status and bare-TTY
behavior are design judgments rather than properties that can be inferred
safely from Click registration alone.

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
