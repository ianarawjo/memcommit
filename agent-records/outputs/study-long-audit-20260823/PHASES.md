# Execution phases

The five attempts for an operation are interleaved with the other operations
in its phase. A phase is not five consecutive repeats of each command.

## Phase 1 · parallel core goal work (21 operations, 105 attempts/world)

Status: **complete for all six worlds · 126/126 operation-world units ·
630/630 attempts**.

`contexts`, `list`, `show`, `find`, `search`, `query`, `summarize`,
`add`, `copy`, `reference`, `embed`, `edit`, `move`, `replace`, `chunk`,
`compare`, `find-duplicates`, `find-redundancies`, `find-ambiguities`,
`find-conflicts`, `fit`.

These routes accept explicit Contexts or are read-only enough to run over
disjoint world namespaces in parallel.

## Phase 2 · transformation and evidence lifecycle (24 operations, 120 attempts/world)

Status: **complete for all six worlds · 144/144 operation-world units ·
720/720 attempts**.

`atomize`, `audit`, `checkpoint`, `check-conformance`, `clear`, `delete`,
`diff`, `distill`, `elaborate`, `resolve`, `dedup`, `dedun`, `forget`, `ground`,
`impact`, `meld`, `merge`, `rationale`, `revert`, `review`, `sever`, `trace`,
`translate`, `update`.

Workers must build recovery material before destructive cases, avoid undoing a
different world's command, and leave outputs useful for the next phase.

Although the short summary describes the current Context, `atomize` exposes
positional Context, `--context`, and `--memory` exact-target routes. Workers use
those forms in parallel. Implicit-current, `--save-as`, and session-launcher
forms remain serialized because they can depend on or change global current.

## Phase 3 · namespace, profile, and system lifecycle (21 operations, 105 attempts/world)

Status: **pending for all six worlds · 0/126 operation-world units ·
0/630 attempts**. Overall verified progress is **270/396 units ·
1,350/1,980 attempts**.

`status`, `branch`, `checkout`, `config`, `eval`, `help`, `import`, `init`, `init-study`,
`lock`, `log`, `profile`, `provider`, `pwd`, `redo`, `rename`, `share`,
`shell-init`, `switch`, `undo`, `unlock`.

This phase is globally serialized where the operation changes active Profile,
current Context, global configuration, or the one-turn Undo/Redo cursor. A
world may exercise an unavailable or protected route as one boundary attempt,
but it must also exercise the meaningful successful forms that its authority
permits.

## Five-method minimum

Where the operation supports the dimension, use one route from each row:

1. exact canonical/direct CLI input;
2. hierarchical, recursive, multiple, or granted scope;
3. a prior operation's output (UID, report, checkpoint, Context, or query
   result) as the next input;
4. an empty, ambiguous, unavailable, stale, or protected boundary followed by
   the visible recovery path;
5. a later accumulated-state route, preferably via TUI discovery or reopened
   session rather than the same direct form.

For an operation that lacks one of these axes, replace it with a genuine
operation-specific dimension and say why in the ledger.
