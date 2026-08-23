# Compact execution-decision TTY capture

This ordered set records the report-free execution surface shared by Meld,
Update, Forget, Sever, Atomize, and Resolve. The deterministic harness uses the
real shared Prompt Toolkit surface. It retains a full report route for explicit
Review but does not render that report or a second command-confirmation screen
during execution.

## Reproduction frame

- Command: `python docs/screenshots/compact-execution-decisions-20260822/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Scenario: two required Meld conflicts, with three operation-authored choices
  per conflict
- PTY: `180` columns × `52` rows, verified inside each child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  on a full-size Menlo canvas. Raw `.typescript` and plain `.txt` evidence sit
  beside each PNG; capture fails when true-color ANSI is absent.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-first-conflict.png` | Launch | `MELD NEEDS INPUT · < 1/2 >`; the typed Recommended option is already checked and focused; complete report hidden | None |
| `02-right-second-conflict.png` | `Right` | Issue 2/2 opens directly; no submission or forced order | None |
| `03-down-second-choice.png` | `Down` | Choice B is the keyboard target; blue focus makes arrow movement visible | None |
| `04-enter-stages-second-choice.png` | `Enter` | Choice B retains `✓`; the process remains on issue 2 | None |
| `05-left-returns-first-conflict.png` | `Left` | Issue 1/2 returns without losing issue 2's process-local choice | None |
| `06-down-preserve-both-focus.png` | `Down`, `Down` | `Preserve both` is the visible arrow-key target while Recommended remains checked | None |
| `07-enter-stages-preserve-both.png` | `Enter` | `Preserve both` receives the retained check for this run | None |
| `08-response-row-focus.png` | `Down` | `RESPONSE · Add a direction…` is a distinct arrow-key target, not an `Other` choice | None |
| `09-apply-row-ready.png` | `Down` | A blank line separates item judgment from `APPLY ALL · 2/2 READY`; no `A`, Defer, or draft action appears | None |
| `10-applied-receipt.png` | `Enter` | Apply runs immediately and the compact receipt exposes the report Review route; no second confirmation screen appears | Target checkpoint (fixture receipt) |
| `11-read-only-verification.png` | `v` | Both reviewed choices, retained report, zero unresolved requirements, and no extra provider call | None |
| `12-response-editor.png` | New run, `Down` ×3, `Enter` | The shared multiline `RESPONSE` field opens in place; choices and report are not replaced by a separate screen | None |
| `13-response-multiline-text.png` | Exact text, `Ctrl-J`, exact text | A two-line direct direction is visible before submission | None |
| `14-response-staged.png` | `Enter` | The direct response is compacted to one checked row and remains process-local | None |
| `15-continue-response.png` | `Down` | The final row honestly changes to `CONTINUE`; custom semantic guidance cannot bypass the provider revision turn | None |
| `16-response-incorporated-receipt.png` | `Enter` | Meld consumes the response without mutating Source or target and requires review of the revised proposal | None |
| `17-close-discards-process-local-response.png` | New run, open Response, enter temporary text, `Enter`, `Esc` | Closing discards the staged compact response and recommendation without saving a draft | None |

The three runs demonstrate that arrows and Enter are the complete interaction
grammar and one separated Apply row is the only confirmation. The conditional
Response row uses the same grammar; Enter saves, `Ctrl-J` inserts a newline,
and Escape returns. Numeric choice keys and direct `L`, `A`, `D`, and `P`
actions are deliberately inert. A
recommendation is selected only when the operation explicitly types it;
option order is never treated as recommendation. Defer, Preserve-all, and
saved drafts are absent from this compact surface. Their legacy domain/CLI
values remain readable for compatibility, but explicit report inspection
belongs to Review.
