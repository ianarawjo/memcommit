# Compact literal Find pager

This ordered set runs the actual `mem` executable in the Study Profile
`study-20260819T175451Z-5ce5d722`, with current Context `practice/source`.
Every step uses a real color-capable PTY at a verified `180` columns by `52`
rows with `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed.
The pexpect recorder cannot answer terminal cursor-position probes, so the
capture-only environment sets `PROMPT_TOOLKIT_NO_CPR=1`.

## Interaction log

| Capture | Command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-first-page` | `mem find 'construction\|entrance' --context task-1/campus-wiki --recursive --regex --ignore-case` | Primary-screen 10-item result window; result `1` is focused, `SHOWING 1–10 OF 64`, and `N [UID] content, [Context mX]` rows wrap without content elision | none |
| `02-second-row-focused` | `Down` | Result `2` owns the shared blue focus treatment; page range is unchanged | none |
| `03-second-page` | `Right` | Corresponding focused row moves to the second discrete page; `SHOWING 11–20 OF 64` | none |
| `04-final-page` | `End` | Last partial page contains result ordinals `61`–`64` and reports `SHOWING 61–64 OF 64` | none |
| `05-closed-to-shell` | `q` | Last inspected page remains in scrollback and the shell prompt returns without an alternate-screen transition | none |
| `06-read-only-status-verification` | `mem status -s` | Profile/current Context counts equal the pre-capture status | none |

The harness rejects alternate-screen control sequences and CPR warnings, checks
foreground and focused-row background ANSI styles, and verifies that paging and
closing leave durable state unchanged. It also rejects application-authored
ellipsis characters in every captured Find result page.
