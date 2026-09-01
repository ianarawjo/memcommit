# Granted Context Reference TUI — 2026-08-31

> Historical evidence: the persisted recursive Context-snapshot behavior and
> explicit command remain current, but the bare mode-based launcher shown here
> was superseded by the exact-Memory-only compact launcher recorded in
> `../reference-compact-exact-memory-20260831/`. Context Reference is now
> entered through explicit CLI or callable operands.

This ordered capture records one recursive immutable Context Reference from the
explicit public READ Grant root `shared/source` into the ordinary local Context
`workspace`. The retained package contains the public root, its readable
lexical child, and its readable embedded Context without exposing the
authority-private `authority/source` name as an operand.

- Command: bare `mem reference`, followed by the TUI's reviewed exact command
  `mem reference shared/source --into workspace --recursive`.
- PTY: `180` columns × `52` rows, verified inside the child before entry.
- Color environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, with
  `NO_COLOR` removed; `capture.py` rejects a stream without ANSI foreground
  color and the exact PTY-size receipt.
- Profile/current Context: active `authoring` Profile; current ordinary local
  Context `workspace`; managed authority Profile `reference-authority`.
- Authority contract: the Source has exactly `READ`; Context Source lists the
  public Grant beside ordinary local Sources, while Target lists only local
  Contexts. Recursive Freeze stays inside the explicitly selected Grant scope
  and records each contributing public/authority binding.

## Ordered interaction log

1. `01-entry-granted-context` — bare command entry in default Context mode;
   `shared/source` is already the selected public Source and `SNAPSHOT UNIT` is
   focused. No durable mutation.
2. `02-granted-context-source-selected` — keys `Tab`, `Enter`; the explicit
   `GRANT shared/source` row is confirmed as Source. No durable mutation.
3. `03-recursive-scope` — keys `Tab`, `Right`; recursive scope is selected,
   covering READ-admitted lexical descendants and embedded Context contents in
   the selected Grant package. No durable mutation.
4. `04-local-target` — key `Tab`; Target focus shows only local `workspace`.
   No durable mutation.
5. `05-exact-command-approval` — key `Tab`; the review names public Source,
   local Target, and `--recursive` before approval. No durable mutation.
6. `06-success-receipt` — key `Enter`; Apply revalidates every exact Grant and
   authority record, holds the Source Store through Target CAS, then saves one
   immutable Context snapshot and one checkpoint in `workspace`. The authority
   Store is unchanged by Reference.
7. `07-read-only-retained-verification` — key `Enter` at the capture gate; the
   fixture then edits the authority root and downgrades its Grant to QUERY-only.
   `mem show REFERENCE_UID --context workspace` remains a read-only inspection
   of the original three-Context retained package, proving that it neither
   follows later authority edits nor needs live authorization after publication.

Each stem has a cumulative raw `.typescript`, a final-canvas `.txt`, and a
color-preserving `.png`. Run `python
agent-records/docs/screenshots/granted-context-reference-20260831/capture.py`
from the repository root to refresh the complete set.
