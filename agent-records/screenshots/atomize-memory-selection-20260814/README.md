# Atomize exact-Memory selection TTY capture

This ordered set records the `New Atomize` setup's exact direct-Memory target,
its typed receipt, and the zero-direct-Memory guard. Both runs use isolated
temporary stores. Fixture creation happens before the captured command; the
captured setup itself performs no Context mutation, provider call, or output
creation.

## Reproduction frame

- Command: `python agent-records/screenshots/atomize-memory-selection-20260814/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Synthetic current Contexts: `study/source` for the successful branch and
  `study/empty` for the rejected branch
- PTY: `180` columns × `52` rows, verified by each child after launch
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  on a full-size Menlo canvas. Raw `.typescript` and plain `.txt` evidence sit
  beside every PNG; the capture fails if no true-color ANSI style is present.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-setup-entry.png` | Launch Atomize setup | Input and Output endpoint frames; no Memory preview loaded | None |
| `02-input-memories-revealed.png` | `m` | Both directly owned Input Memories appear beneath `study/source` | None |
| `03-memory-focused.png` | `Down` | First Memory is the browsing cursor; no Memory is checked yet | None |
| `04-memory-selected.png` | `Enter` | First Memory retains `✓`; owner Context remains the exact Input | None |
| `05-hidden-preview-clears-selection.png` | `m` | Memory rows close; the executable UID is cleared with the now-hidden check | None |
| `06-output-confirmed-apply.png` | Reopen with `m`, reselect the same Memory, then `Tab`, `Down`, type `study/focused-output`, `Enter` | New Output is confirmed as `NOT CREATED`; Apply owns focus | None |
| `07-success-receipt.png` | `Enter` | Setup exits with exact Input name, Memory UID, and not-created Output receipt | None |
| `08-read-only-verification.png` | `v` | Source still owns two Memories, Output is absent, provider calls and checkpoints are zero | None |
| `09-empty-input-blocked.png` | Launch empty branch; `Tab`, `Enter`, `Tab`, `Enter` | Apply rejects `study/empty` with `0 direct Memories` before execution | None |
| `10-empty-input-verification.png` | `q` | Cancellation has no setup receipt, provider call, or checkpoint | None |

The successful branch demonstrates that the Memory check is independent from
the transient row cursor and reaches the operation adapter as an exact UID.
The rejected branch preserves the study failure boundary: an empty lexical
parent cannot silently produce a no-result Atomize run or borrow descendants.
