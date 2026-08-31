# Retrieve & Answer shared SAVE captures

These ordered captures exercise the real prompt-toolkit Find, Search, and
Query workbenches in isolated Stores. The deterministic harness replaces only
Search retrieval and Query provider output; each checked-result or complete
answer save crosses the production application boundary and is then reloaded
read-only from a new `MemoryStore` instance.

- Command: `PYTHONPATH=src python agent-records/docs/screenshots/retrieve-answer-shared-save-20260831/capture.py`
- PTY: `180` columns × `52` rows, verified by `stty size`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Profile/current Context: isolated default profile; current `task/source`
- Fixture: local `task`, `task/archive`, and `task/source`; the Source contains
  `Needle: accessible entrance is on the east side.`

## Interaction log

| Images | Operation and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| 01–02 | Search entry; type `accessibility` | Query editor before execution | No |
| 03 | Enter | completed result and newly visible shared SAVE frame | No |
| 04 | Enter, Tab, Right | checked result and REFERENCE mode | No |
| 05 | Tab, replace location with `draft/search-result` | direct exact Save Location | No |
| 06 | Tab, Enter | local Context tree expanded inside SAVE | No |
| 07 | Up, Enter, Tab, Tab | `task/archive/search-result`, exact Action review | No |
| 08 | Enter | successful REFERENCE save receipt | Yes: new Context |
| 09 | Enter | fresh-Store read-only verification | No |
| 10–11 | Find entry; type `Needle` | literal pattern editor | No |
| 12 | Enter | completed match and newly visible shared SAVE frame | No |
| 13 | Enter, Tab, Right, Right | checked match and EMBED mode | No |
| 14 | Tab, replace location with `draft/find-result` | direct exact Save Location | No |
| 15 | Tab, Enter | local Context tree expanded inside SAVE | No |
| 16 | Up, Enter, Tab, Tab | `task/archive/find-result`, exact Action review | No |
| 17 | Enter | successful EMBED save receipt | Yes: new Context |
| 18 | Enter | fresh-Store read-only verification | No |
| 19–20 | Query entry; type the question | ordinary question editor | No |
| 21 | Enter | complete answer and mode-free shared SAVE frame | No |
| 22 | Tab, replace location with `draft/query-result` | direct exact Save Location | No |
| 23 | Tab, Enter | local Context tree expanded inside SAVE | No |
| 24 | Up, Enter, Tab, Tab | `task/archive/query-result`, exact Action review | No |
| 25 | Enter | successful complete-answer save receipt | Yes: new Context |
| 26 | Enter | fresh-Store read-only answer verification | No |

The tree selection is a placement aid only. It reparents the final name segment
but does not create, load, switch, rename, or persist a Context until the final
Action is explicitly activated.
