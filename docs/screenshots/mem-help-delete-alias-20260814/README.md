# Delete/Remove Help alias verification

This read-only capture set verifies that `remove` remains an executable exact
spelling of Delete without appearing as a second operation in `mem help`.

All images are produced by `capture.py` from the real installed `mem help`
entry point in a color-capable `180x52` PTY. The capture removes `NO_COLOR`,
sets `TERM=xterm-256color` and `COLORTERM=truecolor`, verifies the live terminal
size and foreground/background ANSI styles, and disables only the unrelated
Help command-attempt log. Help loads no Context content and mutates no durable
state.

1. `01-help-entry` — exact command `mem help`; initial BY KIND entry, with the
   first Contexts command focused.
2. `02-delete-remove-row` — preceding keys `Tab`, then `Down` five times; the
   Memories category exposes one focused `mem delete (remove)` row and no
   separate Remove row.
3. `03-delete-detail` — preceding key `Right`; the same canonical row expands
   its typed Flow, Execution, Effect, Range, and audited Delete forms.

The compatibility route is additionally parser-tested: both
`mem delete --help` and `mem remove --help` expose the same callback contract.
