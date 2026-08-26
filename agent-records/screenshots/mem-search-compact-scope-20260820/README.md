# Semantic Search compact Scope

This ordered set runs the actual `mem search` executable against the Study
Profile whose current Context is `practice/source`. The search target is the
READ-granted `task-1/campus-wiki` subtree. Every step uses a color-capable
180-column by 52-row PTY with `TERM=xterm-256color`, `COLORTERM=truecolor`, and
`NO_COLOR` removed. The pexpect recorder cannot answer CPR, so its process sets
`PROMPT_TOOLKIT_NO_CPR=1`; this suppresses recorder-only warnings and does not
change application state or rendering semantics.

## Interaction log

| Capture | Command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-search-entry` | `mem search --context task-1/campus-wiki --recursive --limit 5` | Compact Scope above focused empty Search; Browse tree absent | none |
| `02-browse-open` | `Shift-Tab` ×3, `Enter` | Complete frozen Profile/readable Context tree appears only inside Scope | none |
| `03-descendant-excluded` | `Down`, `Space` | One independently unchecked descendant changes the exact effective count from 7 to 6 | none |
| `04-browse-closed` | `Space`, `Tab` | Range restored to 7 and tree removed from the canvas | none |
| `05-query-entered` | `Tab` ×3, type `construction zone` | Query draft is visible; no provider turn has started | none |
| `06-searching-frozen-scope` | `Enter` | Actual provider-backed background turn; Scope is locked | none |
| `07-complete-results` | wait for provider | Complete one-logical-row ranked result; conditional Save As group visible; no ellipsis | none |
| `08-first-result-checked` | `Space` | First ranked result checked; `SAVE 1 CHECKED AS COPY` is staged only | none |
| `09-read-only-status-verification` | `Ctrl-C`, then `mem status -s` | Profile/current Context counts equal the pre-capture status | none |

The script asserts foreground/background ANSI styles, exact PTY geometry,
complete unelided result content, transient Browse visibility, background scope
freeze, and no durable Context/checkpoint change.
