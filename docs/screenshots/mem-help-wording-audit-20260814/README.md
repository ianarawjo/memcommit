# `mem help` wording and category audit

This read-only capture set exposes every current Help category, every compact
operation summary, and every expanded operation record so category placement
and wording can be reviewed independently from implementation behavior.

All captures run the installed `mem help` entry point against this source
checkout in a color-capable `180x52` PTY. The capture process removes
`NO_COLOR`, sets `TERM=xterm-256color` and `COLORTERM=truecolor`, verifies the
live `52 180` size and foreground/background ANSI styles, and disables only the
otherwise unrelated Help command-attempt log. Help loads no Profile or Context
and performs no durable mutation.

## Category overview sequence

The eight `category-NN-*.png` files follow the visible BY KIND order. The exact
command is `mem help`; initial focus is the first Contexts row, and each capture
after Contexts is preceded by one `Tab` to advance to the next category:

1. Contexts
2. Memories
3. Search & Explain
4. Analyze & Transform
5. History & Recovery
6. Ground & Evaluation
7. Profile & Sharing
8. System

Each category image has matching raw `.typescript` and terminal-text `.txt`
artifacts. The selected first row is only the keyboard target; it does not mean
that operation was invoked.

The collapsed command rows use the same one-column reading order at wide and
compact widths: the operation summary is followed by an explicit `USE WHEN:`
row and its use case. This avoids changing the semantic reading order merely
because the terminal becomes wider and avoids repeating a `DESCRIPTION` label
on every operation.

## Expanded operation sequence

The 58 `detail-NN-*.png` files follow A–Z command order. After `mem help`, the
capture presses `Shift-Tab` to reach `VIEW`, selects `A–Z`, enters the command
surface, presses `Home`, and repeats this read-only sequence for each operation:

1. `Right` expands the selected operation and focuses `FORM 1`.
2. Capture the visible Summary plus Flow, Execution, Effect, optional Range,
   and exact Forms.
3. `Left`, `Left` leaves the form and collapses the operation.
4. `Down` selects the next operation.

Every expanded image has matching raw and terminal-text artifacts. Some
operations own more Forms than fit in one 52-row viewport; this set audits the
meaning fields and visible leading Forms, while the Forms remain fully covered
by the existing Help inventory tests.

`wording-matrix.md` contains the same 58 interface-neutral records in one table
for line-by-line editing. Neither the matrix nor these images add a second Help
source; both are generated from the current registered catalog.
