# `mem help` command naming verification

These captures verify the canonical List spelling and Git-style Checkout
description with the real `mem` executable. The interactive path runs in a
color-capable `180×52` PTY after removing `NO_COLOR`, setting
`TERM=xterm-256color` and `COLORTERM=truecolor`, and verifying both `stty size`
and foreground/background ANSI styles in the raw stream.

Help does not consult a Profile or current Context. The capture also sets
`MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG=1`, so opening, navigating, and closing the
browser publishes no command-attempt record or other durable state.

## Ordered interaction log

| Capture | Exact command | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|
| `01-by-kind-entry` | `mem help` | not consulted / not consulted | none | `BY KIND` entry shows one `list (ls)` operation row, no separate `ls` row, and the Git-style Checkout description | none |
| `02-list-exact-spelling` | same | not consulted / not consulted | `Down`, `Down`, `Right` | canonical `list (ls)` row expanded to its audited `mem list` forms | none |
| `03-checkout-git-style-routes` | same | not consulted / not consulted | `Left`, `Down` ×3, `Right` | Checkout expanded as the ordinary Context-switch route plus the distinct `-b` Branch routes | none |
| `04-plain-read-only-verification` | `mem help </dev/null \| rg '^(branch\|checkout\|list\|ls\|switch) '` | not consulted / not consulted | separate non-interactive invocation | filtered stable plain inventory contains `list (ls)`, omits a standalone `ls` row, uses Git-style wording, and contains no whole-command alias claim | none |

After capture 03, `Q` closes the read-only full-screen browser with exit status
0. The script asserts the expected command rows and Forms before accepting each
capture. Every numbered state has a raw `.typescript`, terminal-text `.txt`,
and full-canvas `.png` artifact.
