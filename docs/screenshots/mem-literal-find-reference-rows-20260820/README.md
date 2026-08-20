# Compact literal Find Reference rows

This ordered capture set runs the actual `mem` executable against the Study
Profile `study-20260819T175451Z-5ce5d722`, whose current Context remains
`practice/source`. Every command uses a real color-capable PTY with
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed.

The harness sets and verifies `52` rows by `180` columns before execution but
does not print the diagnostic `stty size` value into the product screenshots.
The primary-screen Find recorder cannot answer CPR, so it sets
`PROMPT_TOOLKIT_NO_CPR=1` to suppress a recorder-only warning. All steps are
read-only.

## Interaction log

| Capture | Command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-inline-two-reference-rows` | `mem find construction --context task-1/campus-wiki --recursive --ignore-case` | Two `N [UID] content, [Context mX]` rows; `N` is match order, `mX` is frozen searchable-corpus position, and raw spans are absent | none |
| `02-inline-bounded-preview` | `mem find 'construction\|entrance' --context task-1/campus-wiki --recursive --regex --ignore-case --plain` | Complete counts report 64 matched Memories and 71 occurrences; `SHOWING 1–10 OF 64` identifies the bounded result range while every displayed Memory retains complete content and may wrap physically | none |
| `03-inline-empty-scope` | `mem find construction --context task-1/campus-wiki --ignore-case` | Zero scanned items are distinguished from a searched scope with no matching content | none |
| `04-tui-entry` | `mem find construction --context task-1/campus-wiki --recursive --ignore-case --tui` | Primary-screen `SCOPE → FIND → RESULTS`; exact Context fast path, tree absent, Pattern focused | none |
| `05-tui-browse-open` | `Shift-Tab` ×4, `Enter` | Complete frozen Profile/readable Context tree appears only while Browse is open | none |
| `06-tui-descendant-excluded` | `Down`, `Space` | Independently unchecked child changes the exact effective range from 7 to 6 Contexts | none |
| `07-tui-range-restored` | `Space` | Child restored; exact effective range returns to 7 | none |
| `08-tui-browse-closed` | `Tab` | Browse tree leaves the canvas while its checked range remains staged | none |
| `09-tui-complete-reference-rows` | `Tab` ×4, `Enter` | Complete two-row result; first row owns blue focus | none |
| `10-tui-second-row-focused` | `Down` | Second compact Source row owns blue focus | none |
| `11-tui-focused-row-copied` | `y` | Focused numbered row copied; complete typed result remains in Results | clipboard only |
| `12-read-only-status-verification` | `q`, then `mem status -s` | Profile/current Context counts equal the pre-capture status | none |

The script asserts that plain inline commands never enter the alternate screen, the
TUI raw stream contains foreground and background ANSI styles, `SPANS` is
absent from human rows, no Find row contains an application-authored ellipsis,
the broad preview does not silently misreport complete counts, and status is
unchanged after the full path.
