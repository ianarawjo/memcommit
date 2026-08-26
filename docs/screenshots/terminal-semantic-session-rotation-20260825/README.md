# Terminal semantic session rotation captures

These screenshots record the shared terminal-session lifecycle introduced for
Atomize, Meld, and ambiguity Review. Every interactive process ran in a real
`180×52` PTY with `TERM=xterm-256color`, `COLORTERM=truecolor`,
`PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` removed. Each Store
was isolated under a temporary directory; the launcher and historical Review
paths connected no semantic provider.

## Ordered interaction log

| # | Exact command / transition | Visible state | Durable mutation |
|---:|---|---|---|
| 01 | `mem atomize --sessions` | Active refreshed analysis and retained terminal analysis are both selectable | None |
| 02 | `Up` | Pinned `Add new Atomize session` action is focused | None |
| 03 | `Enter` | `NEW ATOMIZE` setup; Input and Output remain explicit | None |
| 04 | `Escape` | Cancel receipt verifies distinct UIDs, one history record, zero launcher provider calls, and an unchanged Store | None |
| 05 | `mem meld --sessions` | Active pending Meld and retained `KEPT_REVIEW_ONLY` Meld are both selectable | None |
| 06 | `Up` | Pinned `Add new Meld session` action is focused | None |
| 07 | `Enter` | `NEW MELD` setup; Direction and endpoints remain explicit | None |
| 08 | `Escape` | Cancel receipt verifies distinct UIDs, one history record, zero provider calls, and an unchanged Store | None |
| 09 | `mem review` | Active ambiguity Review and terminal retained Review appear together | None |
| 10 | `Down` | Retained terminal Review UID is focused | None |
| 11 | `Enter` | Historical Review opens against its frozen one-Memory source frame | None |
| 12 | `q` | Read-only verification contrasts the retained one-Memory frame with the current two-Memory Context | None |
| 13 | Read-only verification process | Common exact-retry, distinct-follow-up, explicit-refresh, and historical-source rules summarized | None |

The preparation phase deliberately creates terminal and successor sessions so
the launcher can display the real persisted catalogs. That setup happens before
the recorded commands and is not part of the interactive mutation audit.
