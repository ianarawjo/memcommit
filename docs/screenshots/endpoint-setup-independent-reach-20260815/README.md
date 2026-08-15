# Independent endpoint reach PTY trace

Command under test: a component harness for the rebuilt role-based Endpoint
Setup using an Update-like A → B contract.

- PTY: `180` columns × `52` rows, verified in the child process.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed.  The
  capture script checks that the raw PTY stream retains ANSI foreground styles.
- Store: an isolated temporary `.mem` root containing `source`,
  `source/child`, `target`, and `target/child`; current remains `target`.
- Provider: not constructed or called.

## Ordered interaction

| Image | Keys before capture | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-a-context.png` | none | A Context selector focused; both A and B ranges are exact | none |
| `02-a-descendants-selected.png` | `Tab`, `Right` | A range is `INCLUDE DESCENDANTS` | none |
| `03-b-range-remains-exact.png` | `Tab`, `Tab` | B range is focused and remains `THIS CONTEXT ONLY` | none |
| `04-complete-range-review.png` | `Tab` | To Do shows A descendants and B exact together | none |
| `05-read-only-range-receipt.png` | `Enter` | Typed receipt records `A=True`, `B=False`; Store bytes/current/checkpoints unchanged | none |
| `06-cancelled-without-ranges.png` | `Escape` from a fresh entry | No draft and the same read-only verification | none |

This trace proves interaction and receipt identity only.  The component does
not expand either root, load descendants, authorize disclosure, or execute an
operation.
