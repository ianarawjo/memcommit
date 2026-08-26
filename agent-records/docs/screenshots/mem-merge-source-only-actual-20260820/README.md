# Actual Source-only Merge evidence

- Capture command: `python agent-records/docs/screenshots/mem-merge-source-only-actual-20260820/capture.py`
- PTY: `180×52`, `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Store: fresh isolated temporary `.mem` root
- Preconditions: Source contains one Memory; Target contains zero Memories
- Actual commands: `mem merge source --into target --direct`, followed by
  `mem show --context target`

| # | State | Evidence | Durable effect |
| --- | --- | --- | --- |
| 01 | Merge receipt | `NEW 1 (1 memory)`, `TARGET CHANGED YES`, and one checkpoint | The exact Source Memory is copied into Target |
| 02 | Target inspection | `mem show` displays the same UID and all three Source lines byte-for-byte | Read-only verification only |

Merge does not invent the displayed prose. The fixture creates it only in
Source; the Merge command creates the corresponding Target Memory with the
same UID and content.
