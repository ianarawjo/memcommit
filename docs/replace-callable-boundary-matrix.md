# Replace callable boundary matrix

Last reviewed: 2026-08-16.

## Closure statement

Every implemented Replace route enters one terminal-independent frozen-plan
application boundary. Planning is read-only and complete over its frozen local
scope. Apply accepts only that exact plan, revalidates every scanned Context
and the local namespace, and publishes all changed Contexts as one Undo/Redo
command unit or publishes nothing.

```text
mem replace PATTERN REPLACEMENT --------\
interactive Replace workbench -----------+--> ReplaceRequest
MemCommitClient.plan_replace ------------+          |
agent/MCP memcommit_replace(kind=plan) --/          v
                                                plan_replace
                                                    |
                                           MemoryStoreReplacePort
                                                    |
                                           FrozenReplacePlan
                                                    |
                         reviewed plan/digest ------+
                                                    v
                                               apply_replace
                                                    |
                                      atomic Store command batch
```

## Boundary matrix

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Request | `ReplaceRequest` | Nonempty literal or explicit regex pattern, literal replacement text (including empty), distinct local roots, and explicit lexical, embedded, and case policies |
| Existing Context locators | CLI/public composition adapters | Current is captured once; every relative operand resolves against that snapshot; targets must be ordinary local Contexts rather than Grants or query-only views |
| Frozen scope | `MemoryStoreReplacePort.freeze` | Every selected lexical/embedded owner is loaded directly; every ordinary Memory is frozen; references are never treated as writable owners |
| Plan | `plan_replace` | Every non-overlapping span has exact start/end/text and one before/after Memory value; regex selects spans but never interprets replacement backreferences |
| Review identity | `FrozenReplacePlan.plan_digest` | Digest covers exact request values, all scanned Context identities/digests/counts, matches, spans, and before/after text; the process-local token separately binds one Store adapter and operation UID |
| Freshness | runtime Apply | Every scanned Context, including a no-match Context, and the complete local Context-name catalog must remain unchanged |
| Publication | `MemoryStore.save_context_command_batch` | Source bindings and catalog are revalidated under the write boundary; all changed Contexts and checkpoints publish atomically or none do |
| No-op | application/runtime | No match or identical before/after still revalidates the complete scope and returns an explicit no-op receipt without a checkpoint |
| Recovery | command history | Per-Context checkpoints share one operation UID, so one Undo or Redo restores the complete multi-Context command unit |
| CLI | `memcommit.commands.replace` | Plain mode previews only; `--apply PLAN_DIGEST` re-freezes the exact request and rejects a different digest before mutation |
| TUI | `interfaces.tui.operations.replace` | Pattern, replacement, local target set, lexical/embedded reach, mode, and case are editable; Review exposes exact before/after changes; a separate exact-command To Do requires Enter to Apply |
| Python | `MemCommitClient.plan_replace` / `apply_replace` | A typed immutable plan carries an opaque client-local handle; Apply rejects plans from another client or modified digests |
| Agent/MCP | `memcommit_replace` version 1 | `plan` returns JSON-safe complete changes; `apply` recomputes from exact request values and requires the previously reviewed digest; provider use is always false |

## Verification

- `tests/test_replace_application.py` proves exact spans, literal regex
  replacement, empty replacement, complete plan identity, and plan tamper
  rejection without Store or terminal dependencies.
- `tests/test_replace_runtime.py` proves lexical and embedded scope,
  reference exclusion, no-match freshness, namespace freshness, atomic
  multi-Context Apply, failure rollback, and operation-unit Undo/Redo.
- `tests/test_replace_cli.py` proves preview-only defaults, exact-digest Apply,
  relative-locator snapshots, literal/regex distinction, and deletion syntax.
- `tests/test_replace_tui.py` proves plan-before-Apply, cancellation,
  focused/whole copy, and visible descendant projection.
- `tests/test_replace_public_api.py` and
  `tests/test_replace_agent_adapter.py` prove stable Python and machine
  contracts, client ownership, stale-plan rejection, and provider isolation.
- Agent registry, MCP projection, package-import, and installed-wheel smoke
  tests cover the exposed callable route.
- `docs/screenshots/mem-replace-20260816/` records the actual color-capable
  interactive entry, scope, review, approval, receipt, and verification path.

## Intentional boundaries

- Replace performs no semantic interpretation, ranking, provider call,
  semantic cache lookup, or visible analysis session.
- Version 1 conservatively invalidates a plan when any local Context name is
  created or removed, even outside the selected roots. This is stricter than
  necessary but closes descendant-membership races at the Store boundary.
- Regex replacement backreferences, overlapping matches, semantic selection,
  referenced-Source mutation through a pointer, and deletion of the entire
  Memory are separate contracts and are not inferred.
