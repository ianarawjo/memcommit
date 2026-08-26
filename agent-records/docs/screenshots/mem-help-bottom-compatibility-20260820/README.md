# `mem help` bottom-record and folded-alias captures

These ordered captures record the Help-only regression path at a verified
`180`-column by `52`-row PTY. The capture environment removes `NO_COLOR`, sets
`TERM=xterm-256color` and `COLORTERM=truecolor`, and verifies foreground and
background ANSI styles in the interactive stream. Help does not consult a
Profile or current Context, and no step mutates durable state.

1. `01-by-kind-entry.png`
   - Command: `mem help`
   - Preceding input: none
   - Visible state: initial `BY KIND` inventory entry
   - Durable mutation: no
2. `02-complete-eval-bottom.png`
   - Command: same `mem help` process
   - Preceding keys: `End`
   - Visible state: the final `mem eval (legacy)` summary, complete `WHEN` row,
     category closing border, scrollbar, separator, and footer
   - Durable mutation: no
3. `03-find-redundancies-alias-row.png`
   - Command: fresh `mem help`
   - Preceding keys: `Shift-Tab`, `Right`, `Tab`, `Home`, `Down` × 24
   - Visible state: the canonical read-only
     `find-redundancies (find-duplicates)` row is focused; the hidden old
     spelling is folded as an exact alias
   - Durable mutation: no
4. `04-find-redundancies-expanded.png`
   - Command: same second `mem help` process
   - Preceding keys: `Right`
   - Visible state: canonical Find Redundancies is expanded with its read-only
     effect, range, and first exact Form visible
   - Durable mutation: no
5. `05-plain-read-only-verification.png`
   - Command: `mem help </dev/null | rg '^find-redundancies '`
   - Preceding input: none
   - Visible state: stable non-TTY inventory contains one canonical row with
     the hidden compatibility spelling folded into its label
   - Durable mutation: no

Every PNG is generated from the corresponding color-preserving `.typescript`
PTY stream; the adjacent `.txt` file is the terminal's plain screen projection.
