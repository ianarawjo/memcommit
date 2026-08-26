# Forget word-diff receipt terminal trace

This ordered 180×52 color-PTY set records the compact receipt printed only
after a reviewed Forget batch has been applied. It shows one whole-Memory
deletion, one inline edit, and a fresh read-only reload of the isolated Source.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Command: `mem forget "Forget the obsolete desk location and normalize the merge wording." --context capture/forget-word-diff`
- Current and direct Source Context: `capture/forget-word-diff`
- Initial Source: three deterministic direct Memories; one DELETE, one EDIT, and one KEEP decision
- Provider: deterministic complete-coverage `_ForgetProvider`; exactly one call
- Route: explicit non-interactive application semantics are selected inside the harness while stdout remains a real PTY, isolating the changed receipt without opening the unchanged Resolution TUI
- PTY: `180` columns × `52` rows, verified in every child
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed; the raw applied-receipt stream is checked for shared REMOVE red `#ed8796` and EDIT green `#a6da95`
- Renderer: actual cumulative PTY bytes replayed through `pyte`; each PNG has matching `.typescript` and `.txt` evidence
- Profile: none; the store is an isolated temporary directory deleted after capture

## Ordered interaction

| Image | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-applied-receipt` | launch the exact Forget command and complete one deterministic provider turn | applied Source, submitted Forget instruction, two one-line changes, checkpoint/Review receipt, and Undo recovery; removed spans are red and added spans are green without an arrow or per-change WHY | one Source checkpoint removes one Memory and edits one Memory |
| `02-durable-verification` | `V` at the capture-only verification gate | removed UID is absent, edited and retained contents are exact, two direct Memories remain, one checkpoint exists, and one provider call occurred | none |

Reproduce from the repository root with:

```sh
python agent-records/screenshots/forget-word-diff-receipt-20260823/capture.py
```
