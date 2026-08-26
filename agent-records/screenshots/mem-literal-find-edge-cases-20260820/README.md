# `mem find` task-data and edge-case verification

This ordered set uses the actual `mem` executable and live Study data in a
color-capable `180×52` PTY. `NO_COLOR` is removed,
`TERM=xterm-256color`, and `COLORTERM=truecolor`. The active Profile is
`study-20260819T175451Z-5ce5d722`; the initial and final current Context is
`practice/source`.

## Interaction log

| Capture | Exact command | Visible behavior | Durable mutation |
| --- | --- | --- | --- |
| `01-normal-ignore-case-match` | `mem find Memory --ignore-case` | one actual Memory contains three case-insensitive literal occurrences | none |
| `02-context-name-is-not-content` | `mem find task --context task-1/campus-wiki --recursive --ignore-case` | the public Context name contains `task`, but the 300 scanned Memory bodies do not | none |
| `03-direct-parent-has-no-memory-source` | `mem find construction --context task-1/campus-wiki --ignore-case` | exact scope scans zero items because the selected parent contains embeds and a query view, not ordinary Memory content | none |
| `04-recursive-scope-finds-embedded-content` | `mem find construction --context task-1/campus-wiki --recursive --ignore-case` | recursive lexical/embed reach scans 300 items and finds two Memories | none |
| `05-regex-metacharacters-remain-literal` | `mem find '.*' --context task-1/campus-wiki --recursive` | default literal mode treats `.*` as text and safely returns no matches | none |
| `06-broad-explicit-regex-floods-terminal` | `mem find 'construction\|entrance' --context task-1/campus-wiki --recursive --regex --ignore-case` | explicit regex returns 64 Memories and 71 occurrences; complete output exceeds 52 rows and scrolls its header away | none |
| `07-zero-width-regex-rejected` | `mem find '^\|' --regex` | invalid zero-width matching is rejected with exit status 1 | none |
| `08-read-only-status-verification` | `mem status -s` | exact pre-capture status remains `practice/source [OWNED] · Memories 17 · Checkpoints 5` | none |

All Find result streams are asserted not to enter the alternate-screen buffer.
The capture script also compares the status before the first Find with capture
08 after the final Find.

## Observed usability boundary

The one-shot route is inline, but its complete-result contract is not compact
for a broad pattern. Capture 06 demonstrates the remaining edge: the command
does not take over the terminal, yet enough matches can still fill many screens
of scrollback. Any future result limit, summary, or pager would need to preserve
complete occurrence counts while making omitted rows explicit rather than
silently truncating the deterministic result.
