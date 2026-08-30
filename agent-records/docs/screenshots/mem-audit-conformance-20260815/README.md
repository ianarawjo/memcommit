# Audit with optional Rule Conformance

This ordered capture verifies the optional fourth `mem audit --against RULES`
check through the real shared Audit wait and read-only semantic Viewer. The
provider is deterministic so the capture tests presentation and persistence
without spending another external inference turn; the separate ticker
Conformance capture records the real configured-provider behavior.

## Reproduction

- Command: `python agent-records/docs/screenshots/mem-audit-conformance-20260815/capture.py`
- PTY: 180 columns by 52 rows, verified before rendering by the recorder
- Terminal: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Frozen Target: `ticker/examples`, two direct Memories
- Frozen Rules: `ticker/rules`, one direct Rule Memory
- Durable mutation: one private Audit receipt only; neither Context changed

## Ordered interaction log

1. `01-fourth-check-running.png` — The first three independent quality
   finders are complete and the fourth Conformance turn is running. The title,
   row count, and pending-result boundary all expose the four-check contract.
   No Audit receipt exists yet and no Context is mutated.
2. `02-complete-four-check-audit.png` — The complete saved Audit opens in the
   shared read-only Resolution Viewer. It reports `4/4 CHECKS`, identifies the
   Conformance Rule count and issue count, and keeps Conformance outside the
   actionable quality-finding ledger.
3. `03-read-only-verification.png` — Escape closes the Viewer, the exact saved
   receipt is reloaded, and the noninteractive projection is rendered. Exact
   pre/post Context digests match and both checkpoint histories remain empty.

Each PNG has a sibling `.txt` terminal canvas and a color-preserving
`.typescript` raw PTY stream. The generated store is temporary and is removed
after verification.

## Result

The optional Audit path calls the same typed Context Conformance core used by
`mem check-conformance`; it does not parse the standalone command's text. The
four reports publish together only after every provider response has been
validated. A failed fourth turn therefore cannot leave a partial saved Audit.
