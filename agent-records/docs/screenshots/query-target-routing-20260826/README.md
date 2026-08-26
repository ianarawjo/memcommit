# Query target routing capture log

These captures record the materially changed Query View path after removing
the per-Memory catalog and handle selector. They use the real prompt-toolkit
Query screen through a color-capable `180×52` PTY. A typed synthetic
`GrantedQueryTarget` and injected process-local answer runner isolate terminal
behavior without opening a Profile, Store, concealed Source, or network
provider.

- Capture command: `PYTHONPATH=src python agent-records/docs/screenshots/query-target-routing-20260826/capture.py`
- PTY: `180` columns × `52` rows, `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Visible ordinary Context: `coffee`
- Initial Query View: `demo/query-only`
- Initial reach: `EXACT VIEW`
- Durable mutation: none in every step

| Image | Preceding keys/text | Visible state | Durable effect |
| --- | --- | --- | --- |
| `01-query-view-preselected.png` | screen entry | Query View Source is already selected, matching positional target initialization | None |
| `02-blank-question-rejected.png` | empty `Enter` | Required-question validation is visible; no runner call occurred | None |
| `03-question-entered.png` | `What is authorized?` | Exact question draft remains in the one-line input | None |
| `04-querying.png` | `Enter` | Background one-shot answer turn is visibly active | None |
| `05-answer-ready.png` | wait for injected answer | One authorized answer is visible; no Memory catalog or handle exists | None |
| `06-read-only-verification.png` | `Ctrl-C` | Child assertions confirm one request, blank rejection, exact target/reach, and no durable state | None |
