# Ordinary Query one-shot capture log

This ordered snapshot set records the changed ordinary Query execution shape:
one complete frozen corpus enters one answer turn, the model returns prose plus
temporary aliases, and the host renders real numbered References.

## Reproduction frame

- Command: `python docs/screenshots/ordinary-query-one-shot-20260813/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: no store or Profile is opened; the child uses a
  seven-item Task 1-shaped process-local corpus and a visible `task-1` marker
- Provider provenance: the production prompt, schema, decoder, citation
  renderer, workbench, and background lifecycle run unchanged; a deterministic
  capture provider returns the answer after 1.4 seconds so the in-flight state
  can be recorded without another external model call
- PTY: `180` columns × `52` rows; the child prints the live dimensions
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: actual ANSI PTY streams replayed through `pyte` and drawn on a full
  `1832×1124` Menlo canvas; raw `.typescript` and plain `.txt` evidence remain
  beside each PNG
- Color verification: the script requires foreground and background ANSI
  styles before succeeding

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-and-frozen-scope.png` | Launch | Blank Question; checked `task-1` subtree, descendant range, and embed policy are visible; no provider call | None |
| `02-question-entered.png` | Type comparison/conflict question | Writable question contains both-side and conflict requirements | None |
| `03-one-shot-querying.png` | `Enter` | Answer reports `QUERYING`; the request and complete corpus are frozen | None |
| `04-answer-with-host-citations.png` | Wait for the single completion | Three answer blocks show host-created `[1]` through `[7]`; References are separate typed blocks | None |
| `05-first-reference-focused.png` | `Down` | Reference 1 owns the shared blue focused-control background | None |
| `06-aggregate-reference-focused.png` | `Down` × 6 | Reference 7, the aggregate conflict assessment, is independently focused | None |
| `07-read-only-verification.png` | `Ctrl-C` | Receipt confirms one call, all seven aliases exposed, Sol/none policy, no session save, and no Source mutation | None |

The deterministic capture is UI evidence, not the deployment quality result.
The separate real same-question run used `mem query --context task-1 ...`,
completed in about 22.8 seconds, produced six answer blocks and 66 used
References, cited baseline and construction-update Memories, and bounded its
no-conflict conclusion to the reviewed Compare corpus.
