# Fit multi-source verification

This focused ordered set verifies the two Ground-free source forms immediately
before the Fit receipt change is committed. Both captures execute the
production `mem fit` command path in a real color-capable `180 × 52` PTY with
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed. The
semantic provider is deterministic so the capture verifies operand expansion,
receipt projection, and the read-only boundary without depending on a live
model response.

Command:

```bash
python agent-records/screenshots/fit-multi-source-check-20260821/capture.py
```

| # | File | Exact Fit command | Profile/current Context | Visible state | Durable mutation |
| --- | --- | --- | --- | --- | --- |
| 01 | `01-three-contexts` | `mem fit context-a context-b context-c` | isolated fixture / `context-a` | One `[TARGETS: CONTEXT context-a, context-b, context-c]` bracket and operation-wide green `YES`; expanded Memory bodies remain typed but hidden | Fixture setup precedes the command; Fit changes no Context and creates zero Fit receipts |
| 02 | `02-three-memories` | `mem fit 11111111 22222222 33333333` | isolated fixture / `memory-set` | One `[TARGETS: MEMORY 11111111, 22222222, 33333333]` bracket and operation-wide green `YES`; no Context group is fabricated | Fixture setup precedes the command; Fit changes no Context and creates zero Fit receipts |

No keys or text are sent between command entry and the result; the provider
turn completes once and the compact receipt appears directly. The trailing
verification lines prove that the frozen source records retain their exact
pre-command digests and that general Fit remains process-local.
