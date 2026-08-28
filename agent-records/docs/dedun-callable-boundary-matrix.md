# Dedun callable boundary matrix

## Reviewed scope

Dedun is the applying complete-DUN operation. It reuses the read-only Find
Redundancies analyzer, includes every same-role exact direct-item group, groups
every eligible direct-Memory exact or non-exact finding, retains the earliest
existing occurrence UID per group, and applies immediately. `mem dedup`
remains the provider-free exact-only shortcut, and its complete exact layer
participates in DUN.

| Route | Public input | Application entry | Review/effect |
| --- | --- | --- | --- |
| CLI | `mem dedun [CONTEXT] [-d\| -r]` | shared per-Context redundancy analyzer plus role-aware exact detector, then direct Apply or recursive scope preparation and batch Apply | one direct checkpoint, one atomic multi-Context command unit, or a no-change receipt in every terminal mode |
| Exact CLI replay | hidden evidence/revision/survivor fields emitted by the final review | the same core | one checkpoint or no write |
| Public Python | `plan_dedun` / `apply_dedun` over reviewed redundancy evidence | `adapters.python_api._operations.dedun` | `DedunPlanResult` and `DedunApplyResult` |
| Agent/MCP | `memcommit_dedun` | the same public Python routes | JSON-safe plan or checkpoint result |

Canonical application ownership is
`memcommit.application.operations.dedun`; plain presentation and the optional
resolution workbench are co-located under
`memcommit.adapters.console.commands.dedun`. The hidden `consolidate` command
remains only an executable replay compatibility boundary. The separate
`find_duplicates` command module is shared with Find Redundancies but enters
immediate Apply only when called by Dedun. Canonical applying vocabulary is
`dedun`, `redundancy-evidence-v2`, `REDUNDANCY`, `DEDUN`, and
`memcommit_dedun`.

The historical `dedup-component-*` identifier prefix remains frozen because
component UIDs occur in exact replay commands and retained checkpoints. Public
Python `Dedup*Result`, `plan_dedup`, and `apply_dedup` spellings remain thin
aliases; new implementation code and module ownership use Dedun names only.

## Shared behavior evidence

Every applying route:

- accepts typed `EXACT`, `SURFACE_EQUIVALENT`, or
  `SEMANTIC_EQUIVALENT` evidence;
- includes exact Memory Embed, Memory Reference, and Context Reference groups
  only when their complete role-specific identity matches;
- never constructs Memory–Embed, Memory–Reference, or Embed–Reference edges;
- preserves the report equation `DUN evidence = DUP / EXACT evidence +
  semantic-DUN evidence`, while counting connected cleanup groups separately;
- revalidates the complete Source frame, Context digest, public name, Grant,
  and reviewed revision;
- builds the same connected redundancy groups and retains the earliest
  unchanged existing survivor per group unless an exact compatibility replay
  supplies a separately reviewed survivor;
- preserves survivor wording and unrelated direct-item order;
- blocks inbound References to absorbed owned Memory UIDs; and
- publishes a direct removal in one `dedun-v3` checkpoint; recursive reach
  publishes one such evidence checkpoint per changed Context inside one
  operation-UID-bound Undo/Redo unit, or publishes nothing.

Recursive CLI reach is deliberately one local lexical subtree. It rejects a
granted root or readable granted descendant before provider connection because
the Store batch has no cross-authority durable transaction. It freezes the
local catalog before analysis, runs each Context as an independent semantic
frame, prepares every survivor projection, scans the complete local graph for
inbound References, and binds unchanged graph records plus namespace membership
through the final batch. A later-frame provider failure, stale Context, new
namespace member, blocked Reference, or write exception therefore exposes no
partial command.

The earlier reviewed-resolution capture remains historical evidence for the
hidden replay adapter. The direct execution capture records compact progress,
success receipt, checkpoint Review, no-change, and read-only finder behavior.
