# `mem rationale` complete-narrative length-unit captures

This ordered set records complete natural-language provenance under the default
word bound and explicit character, UTF-8 byte, and tighter word bounds. Each
provider response is composed to fit its requested unit; no sentence is clipped
after generation. The retained directory name preserves existing evidence
links.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/mem-rationale-character-bounds-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside every child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Fixture: the motivating longer instruction → sentence Chunk → Undo → Redo →
  Remove Trace for `Um...`
- Durable boundary: every scenario uses an isolated temporary store; Rationale
  performs exactly one production-shaped provider turn, performs no cache
  operation, and leaves Context content unchanged

## Ordered scenarios

| Images | Invocation bound | Visible result | Durable mutation |
| --- | --- | --- | --- |
| `01`–`02` | default `40 words` | exact 33-word canonical provenance, then store verification | None |
| `03`–`04` | `--limit 150 --unit characters` | a complete 146-character origin-and-lifecycle narrative | None |
| `05`–`06` | `--limit 150 --unit bytes` | a complete 137-byte ASCII-quoted narrative | None |
| `07`–`08` | `--limit 24 --unit words` | a complete 21-word compressed narrative | None |

Each odd-numbered image is the direct terminal receipt. Its following image is
the capture harness's read-only verification. None opens `RATIONALE REPORT`
Viewer chrome; every scenario asserts exactly one provider call, an untouched
legacy cache, and unchanged Context content.
