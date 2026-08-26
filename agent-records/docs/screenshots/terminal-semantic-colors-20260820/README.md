# Shared terminal semantic-color capture log

> Historical palette evidence. Revert's current entry and revision-result
> layout have since changed and are refreshed under
> `agent-records/docs/screenshots/revert-revision-result-20260821/`; the semantic palette
> meanings remain current.

This ordered snapshot set verifies the common History row color adapter through
the production Revert flow. The underlying scenario is intentionally the same
as the existing Revert policy study capture; a separate directory avoids
overwriting concurrent changes to that evidence while recording the new visual
contract.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/terminal-semantic-colors-20260820/capture.py`
- Operation path: bare `mem revert` command function, Context selection,
  History selection, exact policy review, Apply, receipt, and read-only result
  verification
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated temporary store; current
  `task-1/participant`; selectable target `task-1/recovery`
- Provider provenance: none; all rows and impacts come from local checkpoint
  records
- PTY: `180` columns × `52` rows, set and read live before the application
  starts
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, `NO_COLOR` unset
- Renderer: actual color-preserving PTY bytes replayed through `pyte` onto a
  full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt` evidence
  are retained beside every PNG.
- Color verification: the harness requires the shared blue action foreground,
  red removal impact, focused-row reverse treatment, and alternate-screen ANSI
  sequence before succeeding

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-context-picker-empty-current.png` | Launch Revert | Context tree starts on the empty current Context | None |
| `02-empty-history-view.png` | `Enter` | Empty History view proves no unavailable target can be applied | None |
| `03-created-atomize-boundary.png` | `Backspace`, `Down`, `Right` | Recovery Context expands into correlated operation rows | None |
| `04-recovery-checkpoints.png` | `Enter` | History Items show a focused Add row, neutral mixed Atomize, and blue unfocused Init action | None |
| `05-target-impact-preview.png` | `Down` × 2 | Focus moves to Init and overrides its semantic blue; unfocused Add remains blue and removal impact is red | None |
| `06-discard-newer-policy.png` | `Enter` | Exact checkpoint selected; default discard policy focused | None |
| `07-keep-all-policy.png` | `Right` | Keep-all policy checked and explained | None |
| `08-exact-apply.png` | `Enter` | Frozen checkpoint and policy repeated at Apply | None |
| `09-success-receipt.png` | `Enter` | Revert completes with an exact recovery receipt | Restores the target and writes a recovery checkpoint |
| `10-read-only-verification.png` | Launch verification child | Original checkpoint history is retained and current Context is unchanged | None |

Only the shortest trusted action token receives a semantic color. Mixed
`atomize` remains neutral, row focus owns the complete selected-row treatment,
and all descriptions, timestamps, UIDs, and report chrome remain neutral.
