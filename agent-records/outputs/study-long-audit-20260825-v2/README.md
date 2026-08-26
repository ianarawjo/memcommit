# Long six-world user audit v2 · 2026-08-25

Status: **complete**. Official verification reports **1,980/1,980 attempts**,
**396/396 operation-world cells**, **18/18 ledgers**, and `status=complete` in
both normal and strict `--check` modes. No product code was edited. See
`final-report.md` for the ranked findings and prior-campaign comparison.

The separate shared-Profile regression lane recorded 115 product calls and is
verified in `shared-concurrency/verification.json`; it is excluded from the
official 1,980 count.

## Fixed boundary

- current working-tree implementation was copied before the first counted
  `mem` attempt;
- the code copy is read-only and its complete included-file digest is
  `a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84`;
- the frozen public Help catalog still contains 66 operations;
- one initialized Study template was physically copied into six lane roots;
- every lane begins with identical registry, Store, Context, config, provider
  policy, current Context, command history, session, and cache bytes;
- the same Profile UID across lanes is intentional: the absolute lane Store
  root is the second half of the execution identity.

The counted contract is `6 worlds × 66 operations × 5 materially different
methods = 1,980 attempts`. Lane A contains those attempts. A later Lane B is a
separate shared-state concurrency campaign and does not inflate this total.

## Worlds

1. `task-1`: update every affected campus-wiki area from verified construction
   Memories and contribute the completed update.
2. `task-2`: combine two equal co-advisor policy stores without favoring either,
   consolidating duplicates, clarifying conditions, and reconciling or
   explaining conflicts.
3. `task-3`: decide which personal Memories a healthcare agent should receive,
   exclude the rest, and transfer only the selected information.
4. `ticker`: grow, test, and maintain reusable synthetic company-ticker rules
   from varied examples, including punctuation, numerals, and share classes.
5. `a-is-apple`: start from an empty namespace and grow a small alphabet-to-word
   knowledge set while preserving provenance and recovering from deliberate
   duplicates, conflicts, and edits. There is no pre-existing Ground.
6. `practice-source`: atomize the editing constraints in `practice/source`
   without performing the edits or changing their intended meaning, while the
   surrounding working state continues to grow.

## Counted phases

- `core`: 21 operations × 5 attempts × 6 worlds = 630
- `transform`: 24 operations × 5 attempts × 6 worlds = 720
- `admin`: 21 operations × 5 attempts × 6 worlds = 630

The exact phase sets are authored in `catalog.json`.

## Five-method rule

Within each operation/world unit the five attempts are interleaved with other
operations and differ in a meaningful dimension:

1. exact canonical/direct CLI input;
2. hierarchical, recursive, multiple, or granted scope;
3. a prior operation's UID/report/checkpoint/Context/query result as input;
4. empty, ambiguous, unavailable, stale, or protected boundary plus recovery;
5. later accumulated state, preferably TUI discovery or reopened session.

An unsupported dimension must be replaced by a genuine operation-specific
method and explained in the ledger. Cosmetic input changes do not count.

## Safety and isolation

- Counted commands use `run_world_mem.py`; a worker must never call the live
  `mem` executable or unpinned `python -m memcommit.cli`.
- Each worker runs commands sequentially inside its lane. The six lanes may run
  concurrently.
- `HOME` and `CODEX_HOME` are unchanged. The runner pins Profile registry,
  Store, and config paths before importing the CLI.
- `eval` always receives a lane-local absolute `--ledger-dir`.
- OS clipboard routes are globally serialized or omitted.
- TUI evidence uses an independent 180×52 color PTY per worker with `NO_COLOR`
  removed, `TERM=xterm-256color`, and `COLORTERM=truecolor`.
- External Share, real disclosure, unsupported-fact approval, ambiguous goal
  choice, and destructive semantic Apply outside world-local scratch require a
  user decision. Safe failures are recorded without retrying away the evidence.
- Product bugs are not fixed during collection.

## Evidence

Each world owns only `worlds/<world>/`. Its phase ledger records command,
result, starting state, entry and target route, scope, input provenance,
consumer, expected/actual behavior, defects, cost, Profile/Store identity,
pre/post target digests, recovery evidence, and raw stdout/stderr or PTY
artifact paths. A successful exit is not automatically a satisfactory result.
