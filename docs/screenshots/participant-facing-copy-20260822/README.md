# Participant-facing operation copy

These ordered captures record the participant-visible copy change for the three
read-only discovery surfaces that motivated the work. All screens use an actual
`180 × 52` color PTY with `TERM=xterm-256color`, `COLORTERM=truecolor`, and
`NO_COLOR` removed. Typed local responses replace provider network access so the
copy and interaction states are deterministic; no Context, Memory, session, or
checkpoint is created or changed.

| Image | Command / state | Preceding input | Visible contract | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-query-entry.png` | `mem query` entry | none | `ENTER A QUESTION`; no implementation-state subtitle | none |
| `02-querying.png` | Query provider turn | `When does the north entrance close?`, Enter | `QUERYING`; no frozen-scope narration | none |
| `03-query-answer.png` | Query result | provider response | `ANSWER READY` and grounded answer | none |
| `04-query-read-only-verification.png` | Query close receipt | Ctrl-C | no session save or Source mutation | none |
| `05-search-entry.png` | `mem search` entry | none | one `MEM SEARCH` heading and direct query prompt | none |
| `06-searching.png` | Search provider turn | `entrance construction`, Enter | `SEARCHING`; no frozen-scope narration | none |
| `07-search-results.png` | Search result | provider response | `2 RESULTS`; no complete/frozen status suffix | none |
| `08-search-read-only-verification.png` | Search close receipt | Ctrl-C | no saved result or Source mutation | none |
| `09-find-entry.png` | `mem find` entry | none | `ENTER A PATTERN` | none |
| `10-find-results.png` | deterministic Find result | `nihao`, Enter | `1 MEMORY · 1 OCCURRENCE` | none |
| `11-find-read-only-verification.png` | Find close receipt | Ctrl-C | no Source mutation | none |

The capture program also verifies that every raw `.typescript` contains ANSI
terminal control sequences and that the set contains true-color foreground or
background styling.
