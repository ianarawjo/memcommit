# Update shared Endpoint Setup PTY trace

Command under test: Update's actual `choose_update_setup` command adapter,
backed by `console.tui.components.endpoint_setup`.

- PTY: `180` columns × `52` rows, verified in the child process.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed.
- Store: isolated `participant/construction-updates` Source and `campus-wiki`
  Target Contexts; the Target also has one descendant.
- Provider: not constructed or called. Endpoint setup returns only a typed,
  process-local receipt.

| Image | Keys before capture | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-source-context.png` | none | A Source Context owns initial focus | none |
| `02-source-exact-range.png` | `Tab` | A range remains this Context only | none |
| `03-source-whole-context.png` | `Tab` | A Memory Focus begins at whole Context | none |
| `04-source-memory-selected.png` | `Down`, `Enter` | One exact A Memory is checked | none |
| `05-target-context.png` | `Tab` | B Target Context owns focus; A Memory remains staged | none |
| `06-target-descendants-selected.png` | `Tab`, `Right` | Only B is broadened to descendants | none |
| `07-target-memory-disabled.png` | `Tab` | B cannot retain a focused Memory under descendant reach | none |
| `08-reviewed-independent-scope.png` | `Tab` | To Do shows exact A Memory and recursive B independently | none |
| `09-read-only-typed-receipt.png` | `Enter` | Receipt contains full A UID and B descendants | none |
| `10-cancelled-before-update.png` | `Escape` from a fresh launch | No receipt and no Update execution | none |

The receipt and cancellation captures also verify unchanged Context bytes,
unchanged current Context, zero checkpoints, no staged Update, no Impact
cache, and zero provider calls. They prove setup translation, not provider
analysis, application, CAS, Undo, or saved-session rendering; those boundaries
remain covered by the Update regression suite.
