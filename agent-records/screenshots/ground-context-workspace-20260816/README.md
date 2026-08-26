# Context-rooted Ground workspace capture log

This ordered set records creation, exact physical edits, read-only workspace
navigation, Ground-local Undo, and the authority boundary for typed external
inputs. It uses an isolated temporary Store and never reads or changes the
active user Profile.

## Reproduction frame

- Capture command: `python agent-records/screenshots/ground-context-workspace-20260816/capture.py`
- Command under observation: `mem ground capture/ticker` and the exact commands
  named below
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store/current Context: isolated temporary Store; `capture/orientation` remains
  current for the complete flow
- PTY: `180` columns × `52` rows, verified from the live child terminal
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset,
  24-bit prompt-toolkit color enabled
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at full-size Menlo canvas; `.typescript` and `.txt` evidence accompany PNGs
- Color check: the script requires foreground and background ANSI color styles

## Ordered interaction

| Image | Exact command or input since the preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-physical-creation-receipt.png` | `mem ground capture/ticker --goal 'Learn how real US ticker symbols are assigned.' --snapshot` | Creation receipt and the root plus five physical Contexts | Atomically creates six Contexts and their genesis checkpoints; current Context unchanged |
| `02-typed-edit-receipts.png` | `--add-rule`, then `--add-example`; an external structural setup creates `/contexts/us-market` | Each reviewed Ground edit has its own revision receipt | Root plus the selected lane are one command unit per edit; descendant creation remains an external Context operation |
| `03-workspace-entry.png` | `mem ground capture/ticker` | Physical workspace TUI starts with `/goals` selected | None |
| `04-contexts-row-focused.png` | `Down` × 3 | `/contexts` is the keyboard target; the opened Memory surface has not changed | None |
| `05-contexts-memory-surface.png` | `Enter` | `/contexts` becomes the process-local opened surface | None |
| `06-local-descendant-open.png` | `Tab`, `Right`, `Down`, `Enter` | Real lexical descendant `/contexts/us-market` is opened | None; global current still unchanged |
| `07-read-only-close-verification.png` | `Q` | TUI closes and prints the unchanged global current Context | None |
| `08-ground-local-edit-receipt.png` | `mem ground capture/ticker --add-relation ...` | Root-scoped edit revision and Memory receipt | Root manifest plus `/relations` commit as one Ground command |
| `09-ground-local-undo-verification.png` | `mem ground capture/ticker --undo`, then `--snapshot` | Relation is absent, revision remains monotonic, no legacy JSON exists, current unchanged | One Ground-local undo command restores root-plus-lane pre-image |
| `10-typed-reference-fail-closed.png` | Add external `MemoryRef`, then `mem distill --ground capture/ticker --plain` | Explicit authority-aware projection error and provider call count zero | Only the separately prepared reference is durable; Distill publishes nothing |

The physical TUI is currently a read-only adapter. Writable conversational
Ground editing and typed-reference provider disclosure remain separate future
slices; neither is simulated in these captures.
