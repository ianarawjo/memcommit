# Dedun callable boundary matrix

## Reviewed scope

Dedun is the applying semantic-redundancy operation. It reuses the complete
read-only Find Redundancies analyzer and report, then adds evidence
confirmation, survivor review, and exact Apply. Byte-identical content identity
belongs to Dedup and cannot enter this route.

| Route | Public input | Application entry | Review/effect |
| --- | --- | --- | --- |
| CLI | `mem dedun [--context CONTEXT]` | shared redundancy finder, then `prepare_dedup` / `apply_dedup` compatibility-named core | one continuous TTY review; non-TTY discovery is read-only |
| Exact CLI replay | hidden evidence/revision/survivor fields emitted by the final review | the same core | one checkpoint or no write |
| Public Python | `plan_dedun` / `apply_dedun` over reviewed redundancy evidence | `api._operations.dedup` | `DedunPlanResult` and `DedunApplyResult` |
| Agent/MCP | `memcommit_dedun` | the same public Python routes | JSON-safe plan or checkpoint result |

The remaining `dedup_*` and `consolidate` module names are version-1
implementation or executable compatibility boundaries. The separate
`find_duplicates` command module is shared with Find Redundancies but installs
the Apply handoff only when called by Dedun. Canonical applying vocabulary is
`dedun`, `semantic-redundancy-evidence-v1`, `REDUNDANCY`, `DEDUN`, and
`memcommit_dedun`.

## Shared behavior evidence

Every applying route:

- accepts only `SURFACE_EQUIVALENT` or `SEMANTIC_EQUIVALENT` evidence;
- excludes byte-identical `EXACT` groups, which belong to `mem dedup`;
- revalidates the complete Source frame, Context digest, public name, Grant,
  and reviewed revision;
- builds the same connected redundancy groups and requires one unchanged
  existing survivor per group;
- preserves survivor wording and unrelated direct-item order;
- blocks inbound references to absorbed UIDs; and
- publishes every removal in one `semantic-dedun-v1` checkpoint or publishes
  nothing.

The 180×52 color PTY sequence under
`docs/screenshots/mem-dedup-resolution-20260816/` verifies setup, evidence
confirmation, Dedun review, exact Apply, success, stale rejection,
inbound-reference failure, and read-only state verification. Historical folder
and file stems retain `dedup` for stable links; visible screens and the README
use the current vocabulary.
