# Dedun callable boundary matrix

## Reviewed scope

Dedun is the applying complete-DUN operation. It reuses the read-only Find
Redundancies analyzer, groups every eligible exact or non-exact finding,
retains the earliest existing UID per connected group, and applies
immediately. `mem dedup` remains the provider-free exact-only shortcut, but
byte-identical `EXACT` evidence also participates in DUN.

| Route | Public input | Application entry | Review/effect |
| --- | --- | --- | --- |
| CLI | `mem dedun [--context CONTEXT]` | shared redundancy finder, then `prepare_dedup` / `apply_dedup` compatibility-named core | one immediate checkpoint or a no-change receipt in every terminal mode |
| Exact CLI replay | hidden evidence/revision/survivor fields emitted by the final review | the same core | one checkpoint or no write |
| Public Python | `plan_dedun` / `apply_dedun` over reviewed redundancy evidence | `api._operations.dedup` | `DedunPlanResult` and `DedunApplyResult` |
| Agent/MCP | `memcommit_dedun` | the same public Python routes | JSON-safe plan or checkpoint result |

The remaining `dedup_*` and `consolidate` module names are implementation or
executable compatibility boundaries. The separate
`find_duplicates` command module is shared with Find Redundancies but enters
immediate Apply only when called by Dedun. Canonical applying vocabulary is
`dedun`, `redundancy-evidence-v2`, `REDUNDANCY`, `DEDUN`, and
`memcommit_dedun`.

## Shared behavior evidence

Every applying route:

- accepts typed `EXACT`, `SURFACE_EQUIVALENT`, or
  `SEMANTIC_EQUIVALENT` evidence;
- preserves the report equation `DUN evidence = DUP / EXACT evidence +
  semantic-DUN evidence`, while counting connected cleanup groups separately;
- revalidates the complete Source frame, Context digest, public name, Grant,
  and reviewed revision;
- builds the same connected redundancy groups and retains the earliest
  unchanged existing survivor per group unless an exact compatibility replay
  supplies a separately reviewed survivor;
- preserves survivor wording and unrelated direct-item order;
- blocks inbound references to absorbed UIDs; and
- publishes every removal in one `dedun-v2` checkpoint or publishes
  nothing.

The earlier reviewed-resolution capture remains historical evidence for the
hidden replay adapter. The direct execution capture records compact progress,
success receipt, checkpoint Review, no-change, and read-only finder behavior.
