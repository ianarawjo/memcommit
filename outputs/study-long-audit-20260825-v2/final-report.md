# Six-world audit v2 · final report · 2026-08-25

## Outcome

The rerun is complete on the exact working-tree snapshot frozen at campaign
start. No product code was changed.

- Official coverage: **1,980/1,980 attempts**, **396/396 operation-world
  cells**, **18/18 phase ledgers**.
- Contract: 6 worlds × 66 public operations × 5 materially different methods.
- Phase totals: Core 630, Transform 720, Admin 630.
- Verification: normal and strict `verify_coverage.py --check` both report
  `status=complete`; `ruff check` also passes.
- Additional shared-Profile lane: **115 product calls**, excluded from the
  official 1,980 count, with its own complete verification.
- TUI evidence: 11 representative Admin attempts, 27 ordered real 180×52
  true-color screenshots, and 11 interaction logs.
- Share safety: 30/30 official Share attempts produced **zero deliveries**.

The ledger references 105 distinct issue IDs and 324 issue-attempt links. Those
are not 105 independent product bugs: repeated consumers, controls, and study
instrumentation can reference the same root problem. The ranked families below
deduplicate them.

## Frozen boundary and isolation

- Git HEAD at freeze: `ed4b3786a04745534a86757d017d38abf9bda183`
  on `user-study-prototype`; the working tree was dirty, so the exact bytes—not
  HEAD alone—were copied.
- Code snapshot digest:
  `a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84`
  across 3,349 read-only files.
- Help/catalog digest:
  `3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5`.
- Provider policy digest:
  `b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca`.
- Runner digests stayed fixed. All six lanes used Profile UID
  `8d6d6360-c3eb-40f9-a490-5c7b2a242bfd` but distinct absolute Store roots and
  inodes. No symlinks or cross-lane regular-file inode collisions were found.
- The participant's global config and the originally active live Store state
  remained byte-identical. Three unrelated post-freeze Study creations changed
  the live registry/current selection, but no pre-existing Profile or Grant was
  changed or removed, and no six-world runner escaped its pinned lane.

## Highest-priority product findings

### Critical/P1 · Branch history can poison global Undo/Redo

This is the strongest new finding.

1. A successful Rename of a Branch-created Context changes the live owner name
   but leaves the original Branch receipt membership name stale.
2. Branch or `checkout -b` from a Context carrying Branch history copies the
   old creation receipt into a new owner with a different UID/name.
3. `build_command_stacks()` scans the Profile globally and requires exact
   owner UID/name membership. One stale or cloned receipt therefore blocks all
   later Undo/Redo reconstruction, including otherwise valid newer units.

Rename-triggered corruption reproduced in 4/6 worlds; the branch-of-branch
cascade reproduced in 3/6. Negative-control lanes then saw all later Undo/Redo
attempts fail before Context mutation. A clean-source positive control in the
ticker lane retained valid stack behavior, isolating the trigger.

Recommended fix: migrate receipt membership atomically on Rename; do not copy
creation receipts as ordinary history when Branch changes owner identity; add a
stack-integrity preflight and a direct regression for branch-of-branch,
recursive Branch containing a prior branch descendant, and Rename→Undo.

### P1 · Chunk loses dependent meaning and omits reusable identities

Condition, trigger, exception, draft-only, and approval clauses became
independent Memories in 5/6 worlds. All six worlds also observed that successful
Chunk receipts omitted the new child UIDs—22/22 successful split receipts in
the aggregated evidence—forcing rediscovery before Trace, Rationale, or exact
follow-up. This reproduces old `CF-03`.

Recommended fix: require source-to-child span/condition coverage, default to
keeping a statement whole when a dependent boundary cannot be preserved, and
emit a typed parent→child UID map.

### P1 · Semantic transforms can reverse or invent intent

- Forget produced five harmful outcomes across task-3, ticker, and
  a-is-apple, puncturing preservation intent. This reproduces `CF-15`.
- Elaborate persisted unsupported examples or fabricated quoted premises in
  five commands across four worlds. `UNVERIFIED` labels improved visibility but
  did not prevent materialization. This reproduces `CF-14`.
- Positive Fit/Resolve/Sever routes remained disposition-opaque in 18 recorded
  receipts across practice-source and task-3, continuing `CF-10`.

Recommended fix: preserve complete Source constraints, require source-span
support for persisted additions, and show exhaustive per-Memory disposition
before Apply.

### P1 · Recovery views can hide the current destructive state

Checkpoint Diff reported “THIS CHECKPOINT VS PREVIOUS” rather than the current
post-Clear state in 13/13 exact recovery windows across three worlds. A person
can therefore inspect a valid checkpoint diff and still miss what Clear has
done now. This is new and related to, but not identical with, old `CF-18`.

Recommended fix: label both comparison endpoints explicitly and offer a
checkpoint-vs-current mode by default after destructive operations.

### P1 · Update and typed snapshot boundaries remain unsafe or opaque

Four Update routes across task-3 and ticker auto-applied changes without a
clear changed-text review or selected one side of an explicit Source conflict.
Additional controls found a `ContextSnapshotRef` traceback and an applied
Update whose Trace metadata was rejected twice.

Recommended fix: separate analysis from Apply, require reviewed exact effects
for conflicting inputs, and add typed snapshot round-trip tests across Update,
Trace, Status, and Review.

### P1/P2 · Whole-frame semantic work is often lost after expensive calls

Whole-frame Atomize alone failed all six comparable calls across four worlds;
related Audit ambiguity decoding, Compare/Meld PEER validation, Conformance,
and Sever coverage-summary failures affected every world. No partial Context
publication was observed in the protected cases, but the result and user time
were lost. This expands old `CF-11`.

Recommended fix: validate provider schemas before the expensive turn where
possible, preserve raw repairable results, and test complete-frame invariants
against each operation's decoder.

## Repeated UX and contract findings

- `contexts` printed the complete 112-row Profile inventory in 30/30 calls and
  still cannot narrow to one world (`CF-04`).
- Recursive and saved reports often scale as raw output rather than decisions;
  this appeared in at least 18 routes across five worlds (`CF-06`).
- Summary omitted direct Reference/Embed source families or blurred different
  privacy dispositions in seven tagged routes across three worlds.
- Granted/readable routes remained inconsistent by consumer: whole-Context
  Reference, exact Memory Reference, Audit, Atomize, Impact, Meld, Merge, and
  recursive local-owner consumers did not agree on the same public name.
- Quality-scope grammar remained asymmetric across sibling commands (`CF-05`,
  `CF-09`).
- Rationale silently changed working language in task-1 and task-2 (`CF-08`).
- Same-owner two-Memory Compare was rejected in both exact tests even though
  the command advertises Memory auto-typing.
- `ContextSnapshotRef` handling failed in two independent ticker routes: one
  live-target identity mismatch and one `KeyError: name` traceback.
- A stale practice-source Meld Impact advertised Apply despite zero Source
  coverage and zero changes, reproducing `CF-19`.

## Comparison with the 2026-08-23 campaign

Strongly reproduced or continued: `CF-02`, `CF-03`, `CF-04`, `CF-05`, `CF-06`,
`CF-08`, `CF-09`, `CF-10`, `CF-11`, `CF-13`, `CF-14`, `CF-15`, and `CF-19`.

Best resolution evidence: old wrong-source Query `CF-01` did not reproduce.
Task-2's five explicit Query pairs cited only the requested frames. Treat this
as strong resolution evidence, not universal proof of closure.

Not comparable in isolated Lane A: `CF-07`, `CF-12`, `CF-16`, `CF-17`, and
`CF-18`. They were not marked resolved merely because the isolated design or
route selection removed their original preconditions.

## Shared-Profile concurrency lane

The focused supplemental lane used one sandbox shared by all six actor labels.
It is excluded from the 1,980 count.

- Setup: 24/24 actor-local Context/Memory calls succeeded.
- Current: after five barrier rounds, all six `pwd` calls in each round observed
  one last-writer Context. Only 5/30 actors observed their own Context.
- Switch: 19/30 competing writes failed closed because current changed.
- Explicit disjoint Branch: 5/6 failed because unrelated global current changed
  even though each command supplied an explicit Source.
- Update: one actor won; 5/6 competing saves failed before mutation with “active
  update record changed.” This CAS behavior is an improvement over old silent
  `CF-12` overwrite.
- Implicit Diff: 6/6 actor calls displayed the winning ticker Source, Target,
  and canary. Exact receipt-based Review resolved the winner correctly.
- Registry identity remained unchanged.

Conclusion: silent Update replacement is mitigated, but `current` and implicit
Diff remain Profile-global, and Branch has an unnecessary dependency on
unrelated current state even with explicit endpoints. A public process-pinned
Profile/Store option and actor-bound saved-state locator remain desirable.

## Campaign limitations and contained surprises

- Ticker ran 21 `OP -h` preflight calls before its official Admin phase. They
  are preserved in a separate excluded ledger; Context tree and identity were
  unchanged. They are not counted among the 1,980 attempts.
- Two UUID-shaped `init-study` inputs were assumed by the harness to be invalid
  but are valid portable names. Each created an isolated Study/Profile and made
  it active. This is primarily a protocol mistake/CLI footgun, not classified
  here as a confirmed product defect. The new Stores were preserved as
  evidence; recovery changed only the isolated registry `active_uid` back to
  the participant Profile, with no recovery `mem` call.
- The first shared-lane seed choice had the wrong active Profile. Its 102 calls
  were all rejected by the runner before product dispatch and are preserved
  under `shared-concurrency/failed-seed-preflight/`.
- A handful of harness parsers expected full IDs where the CLI printed short
  IDs; interrupted actual calls were reconstructed from durable receipts and
  never replayed.
- Provider timeouts and accepted provider variance are separated from product
  findings unless a stable decoder, mutation, or presentation contract failed.

## Evidence map

- Campaign boundary: `snapshot-manifest.json`, `catalog.json`, `README.md`.
- Official verifier: `verify_coverage.py`.
- Per-world truth: `worlds/<world>/phase-{core,transform,admin}.json` and each
  world's `issues*.json` / `issues*.md`.
- Critical history evidence: `worlds/practice-source/issues-admin.md`,
  `worlds/task-2/issues.md`, `worlds/task-3/issues-admin.md`, and
  `worlds/a-is-apple/issues-admin.md`.
- Shared lane: `shared-concurrency/verification.json`,
  `shared-concurrency/supplemental-report.json`, and
  `shared-concurrency/update-race-report.json`.
- TUI index:
  `agent-records/screenshots/six-world-audit-v2-20260825/a-is-apple-admin/README.md`.
