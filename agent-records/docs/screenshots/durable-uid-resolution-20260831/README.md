# Durable UID resolution captures

These captures exercise the real prompt-toolkit Find, Search, and Query
workbenches against isolated Stores. Each Source contains one Memory whose UID
is `11111111-1111-4111-8111-111111111111`; its content does not contain that
identifier. Search and Query install provider factories that fail if called, so
their successful result screens also verify that standalone UID lookup stayed
local and deterministic.

- Command: `PYTHONPATH=src python agent-records/docs/screenshots/durable-uid-resolution-20260831/capture.py`
- PTY: `180` columns × `52` rows, verified by `stty size`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Profile/current Context: isolated explicit Store; current `uid-demo`
- Durable mutation: fixture creation occurs before each capture; every captured
  Find, Search, and Query interaction is read-only

## Interaction log

| Images | Operation and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| 01 | Find entry | Blank literal pattern and exact readable scope | No |
| 02 | Type `11111111` | Printed UID prefix in the Find pattern field | No |
| 03 | Enter | One Memory, zero text occurrences, one explicit UID match | No |
| 04 | `Ctrl-C` | Fresh checkpoint-list verification and unchanged Source | No |
| 05 | Search entry | Blank semantic query and exact readable scope | No |
| 06 | Type `11111111` | Printed UID prefix in the Search query field | No |
| 07 | Enter | Exact authorized Memory result without provider construction | No |
| 08 | `Ctrl-C` | Fresh checkpoint-list verification and unchanged Source | No |
| 09 | Query entry | Blank ordinary question and exact readable scope | No |
| 10 | Type `11111111` | Printed UID prefix in the Query question field | No |
| 11 | Enter | Grounded UID identity answer with typed Reference | No |
| 12 | `Ctrl-C` | Fresh checkpoint-list verification and unchanged Source | No |
