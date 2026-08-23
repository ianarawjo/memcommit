# `mem replace` direct execution evidence

Captured on 2026-08-22 from the repository command adapter in a real
color-capable `180×52` PTY (`TERM=xterm-256color`, `COLORTERM=truecolor`, and
`NO_COLOR` removed). `PROMPT_TOOLKIT_NO_CPR=1` suppresses a recorder-only CPR
warning because the pexpect stream does not emulate a cursor-position reply.
The compact form remains on the primary screen and the capture asserts that no
alternate-screen entry sequence was emitted.

Every run used a fresh temporary `MemoryStore`; no user Profile or Context was
opened or changed. The initial current Context was `replace/demo`, containing
two `writer` occurrences. Its child `replace/demo/child` contained one more.
The recorder preserves the raw PTY stream (`.typescript`), terminal text
(`.txt`), and rendered terminal image (`.png`) for every step.

## Direct complete command

| Snapshot | Exact command or preceding input | Visible contract | Durable effect at this step |
| --- | --- | --- | --- |
| `01-direct-command-receipt` | `mem replace writer author --context replace/demo` | A complete deterministic request executes immediately and prints only a concise receipt plus the Undo promise | Two occurrences in one Memory changed as one checkpoint |
| `02-direct-read-only-verification` | `Enter` in the recorder harness | The owner Memory contains `author`; the child remains unchanged; exactly one checkpoint exists | None; direct Store verification is read-only |

## Compact operand-free form

The exact launch was `mem replace --context replace/demo`. It has no Review,
To Do, plan digest, or exact-command approval surface.

| Snapshot | Preceding keys or text | Visible contract | Durable effect at this step |
| --- | --- | --- | --- |
| `03-tui-entry` | command launch | Primary-screen `SCOPE → FIND → REPLACE WITH`; exact current Context, literal mode, and case policy are visible | None |
| `04-tui-descendants-selected` | `Shift-Tab` ×3, `Right` | The shared compact Scope projects the root and lexical child as two exact execution targets | None |
| `05-tui-scope-browse` | `Shift-Tab`, `Enter` | Browse exposes the checked local hierarchy without creating or opening a Context | None |
| `06-tui-find-entered` | `Escape`, `Tab` ×4, type `writer` | Find text is staged directly in the compact form | None |
| `07-tui-replacement-entered` | `Enter`, type `author` | Replace With owns the final execution gesture; there is no intermediate plan or review | None |
| `08-tui-direct-apply-receipt` | `Enter` | The form erases itself and leaves one concise receipt in primary terminal history | Three occurrences in two Memories changed atomically as two grouped checkpoints |
| `09-tui-read-only-verification` | `Enter` in the recorder harness | Both directly owned Memories contain the literal replacement and exactly two checkpoints exist | None; direct Store verification is read-only |

## Stale execution rejection

The exact launch was
`mem replace writer author --context replace/demo --tui`. The capture adapter
creates an unrelated local Context after the internal freeze and before Apply,
changing catalog membership without touching either Source Memory.

| Snapshot | Preceding keys | Visible contract | Durable effect at this step |
| --- | --- | --- | --- |
| `10-stale-execution-stopped` | `Enter`, `Enter` | Replace reports that the namespace changed during execution and keeps the compact request editable | Only the deliberately injected unrelated Context exists; no Replace Memory or checkpoint effect published |
| `11-stale-no-partial-write-verification` | `Escape`, then `Enter` in the recorder harness | Both original `writer` Memories remain and checkpoint count is zero | None; direct Store verification is read-only |

The capture script asserts the PTY dimensions, foreground and background ANSI
styles, primary-screen behavior, direct and TUI receipts, changed success
state, stale error wording, unchanged failure state, and exact checkpoint
counts.
