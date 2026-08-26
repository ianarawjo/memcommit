# Long six-world user audit · 2026-08-23

This directory records a fixed-snapshot, user-goal-driven audit of every
public operation exposed by `mem help`.

The current integrated narrative is in
[`final-report.md`](final-report.md). It is explicitly provisional until the
strict verifier reaches 1,980/1,980 and the completion audit closes every
remaining requirement.

For live debugging, use the strict
[`confirmed-bug-index.md`](confirmed-bug-index.md), which keeps confirmed
actual bugs separate from execution-backed candidates and UX/contract
friction. It is also provisional while the serialized admin phase is pending.

Verified progress at this checkpoint is **1,350/1,980 attempts** and
**270/396 operation-world units**. All six core and transform phases are
complete. The 21-operation serialized admin phase remains pending for all six
worlds.

## Frozen boundary

- Study: `study-long-audit-20260823`
- Baseline: `study-baseline`
- Git HEAD: `61baf05adfa7796fd47d64bd19274c0bbf53404a`
- Tracked source diff SHA-256: `687ffcbdbb22e2155f1279d1dd1d996888f655560c6a960d84acd156ffdf159d`
- Untracked source SHA-256: `2b5a636e4990021e04d907f0747daa9d448a8d4bcfc6589db794e89180015eb5`
- Source status SHA-256: `1972ba8d5af21c4198a03c4684a2ffe093e467c8f97bd154983193842a1a8ccc`
- Provider policy: `study-provider-config-v1`, digest
  `9faa8cea3634d393e3b2f724077b1db14f8628ee7243de2ab75c93d22c816702`
- Initial participant state: 65 owned Contexts, 468 owned Memories,
  43 granted Contexts, 625 granted Memories, current `practice`.
- Physical code snapshot (created after the first in-flight core rounds):
  `/tmp/memcommit-study-long-audit-20260823-code.yfgwbK`
- Restart-stable read-only copy:
  `/Users/KimMunyeong/.codex/audit-snapshots/memcommit-study-long-audit-20260823-code`
- Snapshot/live package source digest at transition:
  `cd38ddfd678b1579dbfcd83e4dbed2d684265c8d215783dc479d993fdbeae787`
- Frozen launcher after transition:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/KimMunyeong/.codex/audit-snapshots/memcommit-study-long-audit-20260823-code python -m memcommit.cli`

Pre-transition commands ran while the live package matched the recorded source
fingerprints. The package was then copied and made read-only so unrelated live
repository refactoring cannot change later command behavior. Product defects
are logged and worked around inside the Study; fixes belong to a later task and
snapshot.

## Worlds and goals

1. `task-1`: update every affected campus-wiki area from verified construction
   memories and contribute the completed update.
2. `task-2`: combine two equal co-advisor policy stores without favoring either,
   consolidating duplicates, clarifying conditions, and reconciling or
   explaining conflicts.
3. `task-3`: decide which personal memories a healthcare agent should receive,
   exclude the rest, and transfer only the selected information.
4. `ticker`: grow, test, and maintain reusable synthetic company-ticker rules
   from varied examples, including punctuation, numerals, and share classes.
5. `a-is-apple`: start from an empty namespace and grow a small alphabet-to-word
   knowledge set while preserving provenance and recovering from deliberate
   duplicates, conflicts, and edits. There is no pre-existing Ground.
6. `practice-source`: atomize the editing constraints in `practice/source`
   without performing the edits or changing their intended meaning, while the
   surrounding working state continues to grow.

## Coverage contract

The frozen Help catalog contains 66 operations, so complete coverage is
`6 worlds × 66 operations × 5 attempts = 1,980 attempts`.
The matching operation-world contract is `6 × 66 = 396`; completed core and
transform phases account for `6 × (21 + 24) = 270` units and 1,350 attempts.

Each operation's five attempts must differ in a meaningful method dimension,
such as entry route, exact versus recursive/multiple/granted scope, direct
input versus a prior operation's output, early versus late accumulated state,
or success/empty/ambiguity/recovery boundary. Five consecutive cosmetic input
variants do not count.

Each phase ledger is JSON with this shape:

```json
{
  "world": "task-1",
  "phase": "core",
  "operations": {
    "show": {
      "attempts": [
        {
          "attempt": 1,
          "starting_state": "early; exact local Context",
          "entry_route": "direct CLI",
          "target_route": "canonical name",
          "scope": "exact/direct",
          "input_provenance": "world fixture",
          "consumer": "UID reused by Trace",
          "command": "mem show ...",
          "exit": 0,
          "actual": "concise observed result",
          "defect_ids": [],
          "cost": "none"
        }
      ]
    }
  }
}
```

Functional failures and user-experience defects both count as evidence, but a
failed attempt is not silently treated as satisfactory. Record the expected
behavior, actual behavior, workaround, and severity in the world's issue file.

## Coordination

- Commands run from the repository root using the real `mem` executable.
- Agents use explicit Context operands wherever supported.
- Profile selection, current-Context-only commands, Undo, Redo, and other
  global-state routes are serialized by the root agent.
- Independent reads and disjoint local-Context writes may run in parallel.
- No Study reset occurs between early, middle, and late phases.
- Collection pauses only for a product-meaning, permission, or frontend-flow
  decision that requires the user's judgment.

The current shared-Profile boundary and the recommended two-lane follow-up
(six isolated world Stores plus a focused shared-state concurrency campaign)
are recorded in [`runner-isolation-analysis.md`](runner-isolation-analysis.md).
The current campaign is not migrated mid-run because doing so would split its
accumulated-state and concurrency evidence boundary.

The reusable fast-discovery invariants distilled from the observed failures are
listed in
[`automatable-error-patterns.md`](automatable-error-patterns.md). They find
strong candidates before a full five-method user campaign, but do not replace
goal-level confirmation or user decisions.

`verify_coverage.py` checks more than the aggregate count: world/phase
membership, the exact phase operation set, attempt IDs 1–5, required evidence
fields, five-method signature uniqueness, the frozen launcher for post-snapshot
phases, and both missing and excess attempts.

## Frozen public operations

`add`, `atomize`, `audit`, `branch`, `checkout`, `checkpoint`,
`check-conformance`, `chunk`, `clear`, `compare`, `copy`, `config`, `contexts`,
`delete`, `diff`, `distill`, `elaborate`, `edit`, `replace`, `embed`, `eval`,
`find`, `search`, `fit`, `resolve`, `dedup`, `dedun`, `find-ambiguities`,
`find-conflicts`, `find-duplicates`, `find-redundancies`, `forget`, `ground`,
`help`, `impact`, `import`, `init`, `init-study`, `list`, `lock`, `log`, `meld`,
`merge`, `move`, `profile`, `provider`, `pwd`, `query`, `rationale`, `redo`,
`reference`, `rename`, `revert`, `review`, `sever`, `share`, `shell-init`,
`show`, `status`, `summarize`, `switch`, `trace`, `translate`, `undo`, `unlock`,
`update`.
