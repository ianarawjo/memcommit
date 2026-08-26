# Endpoint Setup focused Memory PTY trace

Command under test: a component harness for the rebuilt role-based Endpoint
Setup with one Update-like Source role.

- PTY: `180` columns × `52` rows, verified in the child process.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed.  The
  capture script checks that raw output retains ANSI foreground styles.
- Store: an isolated temporary `.mem` root containing `source` with two direct
  Memories and `target` with one; current remains `target`.
- Loader: caller-owned and process-local.  It returns only the exact selected
  Context's frozen direct-Memory projections.
- Provider: not constructed or called.

## Exact Memory path

| Image | Keys before capture | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-a-context.png` | none | Source Context selector owns initial focus | none |
| `02-exact-range-focused.png` | `Tab` | A remains `THIS CONTEXT ONLY` | none |
| `03-whole-context-memory-focus.png` | `Tab` | Memory Focus starts on checked `WHOLE CONTEXT` | none |
| `04-first-memory-hovered.png` | `Down` | First Memory is the keyboard target; whole Context remains checked | none |
| `05-exact-memory-selected.png` | `Enter` | First exact Memory is checked and To Do shows its UID prefix | none |
| `06-exact-memory-review.png` | `Tab` | To Do reviews exact Context plus exact Memory together | none |
| `07-exact-memory-receipt.png` | `Enter` | Typed value contains the full exact Memory UID; only `source` was loaded | none |

## Descendant-clearing path

| Image | Keys before capture | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `08-clearing-branch-memory-selected.png` | `Tab`, `Tab`, `Down`, `Enter` from a fresh launch | Exact Memory precondition is visible | none |
| `09-range-before-broadening.png` | `Shift-Tab` | Range owns focus while the exact Memory remains staged | none |
| `10-descendants-clear-memory.png` | `Right` | A becomes `INCLUDE DESCENDANTS`; To Do immediately drops the Memory UID | none |
| `11-memory-focus-disabled-for-subtree.png` | `Tab` | Memory surface states that focused Memory requires exact reach | none |
| `12-descendant-review-without-memory.png` | `Tab` | To Do reviews the subtree with no hidden Memory constraint | none |
| `13-descendant-receipt-without-memory.png` | `Enter` | Typed value records descendants `True` and Memory `None` | none |
| `14-cancelled-without-memory-draft.png` | `Escape` from a fresh launch | No draft; Store verification remains unchanged | none |

The trace proves interaction, typed draft identity, exact lazy projection, and
read-only behavior.  It does not authorize input, traverse descendants,
construct an operation request, or apply a result.
