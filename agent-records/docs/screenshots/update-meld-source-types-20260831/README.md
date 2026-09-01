# Update and Meld Source Type PTY trace

This ordered trace records the operation-specific Update and Meld Endpoint
Setup adapters after adding explicit `CONTEXT`, `STORED MEMORY`, and `INLINE
MEMORY` Source Types.

- Command surfaces: `$ mem update` and `$ mem meld`, exercised through their
  production `choose_update_endpoint_setup` and `choose_meld_endpoint_setup`
  adapters so the trace stops before semantic planning.
- PTY: `180` columns × `52` rows, verified inside every child process.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed. The
  capture script rejects output without true-color ANSI foreground or
  background sequences.
- Store: an isolated temporary `.mem` root with readable
  `practice/coffee/source`, current `practice/coffee/target`, and empty
  `practice/coffee/result` Contexts.
- Provider: never constructed or called. Setup approval returns only a typed
  process-local receipt.
- Provenance: every PNG is rendered from the matching real color PTY byte
  stream retained in `.typescript`; `.txt` is the same terminal canvas without
  ANSI styling.

## Update path

| Image | Keys or text before capture | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-update-entry-context.png` | none | Update starts with explicit `CONTEXT`; A and B are distinct Context endpoints | none |
| `02-update-stored-memory-selected.png` | `Right`, `Tab` ×3, `Enter` ×2 | `STORED MEMORY` keeps A's owner Context, requires one exact UID, and emits `--source-memory` | none |
| `03-update-inline-empty-invalid.png` | fresh launch, `Right` ×2 | `INLINE MEMORY` hides Source Context controls; blank content leaves the proposed command invalid | none |
| `04-update-inline-exact-command.png` | `Tab`, type `나는 자연인이다`, `Down` ×2 | exact review shows `mem update --memory '나는 자연인이다' --to practice/coffee/target` | none |
| `05-update-inline-setup-receipt.png` | `Enter` | exact-command approval returns `source_name=None` plus the exact inline content | none |
| `06-update-read-only-verification.png` | `v` | Context bytes and current Context are unchanged; checkpoints and provider calls remain zero | none |

The stored-Memory branch is cancelled after image 02. Its child also checks the
same read-only conditions before exit; the inline branch records the visible
typed receipt and verification as the representative successful setup path.

## Meld path

| Image | Keys or text before capture | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `07-meld-symmetric-context-peers.png` | none | symmetric Meld contains only peer Context rows A/B and separate Result C; no Source Type control is present | none |
| `08-meld-directional-context-source.png` | `Right` | directional mode exposes the three-way incoming Source Type, initially `CONTEXT` | none |
| `09-meld-stored-memory-selected.png` | `Tab`, `Right`, `Tab` ×3, `Enter` ×2 | `STORED MEMORY` keeps the incoming owner Context and exact UID, emitting `--incoming-memory` | none |
| `10-meld-inline-empty-invalid.png` | fresh launch, `Right`, `Tab`, `Right` ×2 | `INLINE MEMORY` replaces incoming Context scope; blank content is invalid | none |
| `11-meld-inline-exact-command.png` | `Tab`, type `keep this exact distinction`, `Down` ×2 | exact review uses the directional authority spelling `mem meld --memory ... --into practice/coffee/target` | none |
| `12-meld-inline-setup-receipt.png` | `Enter` | approval returns directional `left_name=None` plus the exact inline content and baseline Context | none |
| `13-meld-read-only-verification.png` | `v` | Context bytes and current Context are unchanged; checkpoints and provider calls remain zero | none |

The stored-Memory Meld branch is cancelled after image 09 and verified
read-only before exit. This trace intentionally proves setup identity,
canonical command review, and the no-mutation boundary; it does not claim that
a semantic Update or Meld plan was prepared or applied.
