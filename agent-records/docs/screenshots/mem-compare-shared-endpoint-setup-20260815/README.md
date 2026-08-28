# Compare shared Endpoint Setup PTY trace

Command under test: Compare's actual `choose_compare_setup` command adapter,
now backed by `console.tui.components.endpoint_setup`.

- PTY: `180` columns × `52` rows, verified in the child process.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed.
- Store: isolated `reference` and `peer` Contexts with two direct Memories
  each; `reference` remains current throughout.
- Provider: not constructed or called. Endpoint setup returns only a typed,
  process-local receipt.

| Image | Keys before capture | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-reference-context.png` | none | A Reference Context owns initial focus | none |
| `02-reference-exact-range.png` | `Tab` | A range remains this Context only | none |
| `03-reference-whole-context.png` | `Tab` | A Memory Focus begins at whole Context | none |
| `04-reference-memory-selected.png` | `Down`, `Enter` | One exact A Memory is checked | none |
| `05-peer-context.png` | `Tab` | B Peer Context owns focus; A Memory remains staged | none |
| `06-peer-descendants-selected.png` | `Tab`, `Right` | Only B is broadened to descendants | none |
| `07-peer-memory-disabled.png` | `Tab` | B cannot retain a focused Memory under descendant reach | none |
| `08-reviewed-independent-scope.png` | `Tab` | To Do shows exact A Memory and recursive B independently | none |
| `09-read-only-typed-receipt.png` | `Enter` | Command receipt contains full A UID and B descendants | none |
| `10-cancelled-before-compare.png` | `Escape` from a fresh launch | No receipt and no Compare execution | none |

The receipt capture also verifies unchanged Context bytes, unchanged current
Context, zero checkpoints, both exact direct-Memory projections loaded once,
and zero provider calls. It proves setup translation, not semantic provider
analysis or saved-session rendering.
