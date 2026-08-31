# Replace callable boundary matrix

Last reviewed: 2026-08-30.

## Closure statement

Every implemented Replace route enters one terminal-independent frozen-plan
application boundary. Planning is read-only and complete over its frozen local
scope. Apply accepts only that exact plan, revalidates every scanned Context
and the local namespace, and publishes all changed Contexts as one Undo/Redo
command unit or publishes nothing.

The implementation is owned by `memcommit.application.operations.replace`. The former
top-level application and runtime paths remain true module aliases rather than
copied re-export namespaces. That preserves type identity, import-order and
monkeypatch behavior, and pre-relocation pickle lookup while moving ownership;
it changes no request, plan, validation, Store effect, output, or interaction.

```text
mem replace PATTERN REPLACEMENT --\
compact Replace form --------------+--> ReplaceRequest --> internal plan/apply
                                    |                          |
                                    |                          v
                                    |               atomic Store command batch
                                    |
MemCommitClient.plan_replace ------+--> typed remote-review compatibility
agent/MCP kind=plan/apply ----------/        plan handle --> apply_replace
```

## Boundary matrix

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Request | `memcommit.application.operations.replace.application.ReplaceRequest` | Nonempty literal or explicit regex pattern, literal replacement text (including empty), distinct local roots, and explicit lexical, embedded, and case policies |
| Existing Context locators | CLI/public composition adapters | Current is captured once; every relative operand resolves against that snapshot; targets must be ordinary local Contexts rather than Grants or query-only views |
| Frozen scope | `memcommit.application.operations.replace.runtime.MemoryStoreReplacePort.freeze` | Every selected lexical/embedded owner is loaded directly; every ordinary Memory is frozen; references are never treated as writable owners |
| Plan | `memcommit.application.operations.replace.application.plan_replace` | Every non-overlapping span has exact start/end/text and one before/after Memory value; regex selects spans but never interprets replacement backreferences |
| Internal execution identity | `memcommit.application.operations.replace.application.FrozenReplacePlan.plan_digest` | Digest covers exact request values, all scanned Context identities/digests/counts, matches, spans, and before/after text; human CLI/TUI routes keep it internal while the process-local token binds one Store adapter and operation UID |
| Freshness | `memcommit.application.operations.replace.runtime` Apply | Every scanned Context, including a no-match Context, and the complete local Context-name catalog must remain unchanged |
| Publication | `MemoryStore.save_context_command_batch` | Source bindings and catalog are revalidated under the write boundary; all changed Contexts and checkpoints publish atomically or none do |
| No-op | `memcommit.application.operations.replace.application` / `runtime` | No match or identical before/after still revalidates the complete scope and returns an explicit no-op receipt without a checkpoint |
| Recovery | command history | Per-Context checkpoints share one operation UID, so one Undo or Redo restores the complete multi-Context command unit |
| CLI | `memcommit.adapters.console.commands.replace.command` | A complete request executes immediately with one receipt in any terminal; only a missing pattern or replacement opens the input editor, and retired presentation flags are rejected |
| TUI | `memcommit.adapters.console.commands.replace.workbench` | The primary-screen compact form edits pattern, replacement, local target set, lexical/embedded reach, mode, and case; Enter on Replace With executes directly, closes the form, and prints one concise receipt without Review or To Do |
| Python | `MemCommitClient.plan_replace` / `apply_replace` | A typed immutable plan carries an opaque client-local handle; Apply rejects plans from another client or modified digests |
| Agent | `memcommit_replace` version 1 | `plan` returns JSON-safe complete changes; `apply` recomputes from exact request values and requires the previously reviewed digest; provider use is always false |

Console-specific ownership is co-located under
`memcommit.adapters.console.commands.replace`: `command.py` owns orchestration,
`workbench/` owns interactive editing and direct execution, `proposal.py`
retains the human-readable frozen-plan projection for the planned proposal
workflow, and `receipt.py` owns completed-command output. The proposal renderer
is deliberately retained without wiring a new human review step in this
relocation.

## Verification

- `tests/test_replace_application.py` proves exact spans, literal regex
  replacement, empty replacement, complete plan identity, and plan tamper
  rejection without Store or terminal dependencies.
- `tests/test_replace_runtime.py` proves lexical and embedded scope,
  reference exclusion, no-match freshness, namespace freshness, atomic
  multi-Context Apply, failure rollback, and operation-unit Undo/Redo.
- `tests/test_replace_cli.py` proves immediate atomic execution, Undo, one
  terminal-independent receipt route, relative-locator snapshots,
  literal/regex distinction, deletion syntax, and incomplete-input editing.
- `tests/test_replace_tui.py` proves direct execution, cancellation,
  primary-screen cleanup, and visible descendant projection.
- `tests/test_replace_public_api.py` and
  `tests/test_replace_agent_adapter.py` prove stable Python and machine
  contracts, client ownership, stale-plan rejection, and provider isolation.
- `tests/test_replace_ownership.py` proves legacy/canonical module identity in
  either import order, implementation-free facades, lazy package import, and
  pre-relocation pickle lookup through the compatibility alias.
- Agent registry, MCP projection, package-import, and installed-wheel smoke
  tests cover the exposed callable route.
- `agent-records/docs/screenshots/mem-replace-direct-20260822/` records the actual
  color-capable compact entry, scope, input, direct receipt, stale failure, and
  read-only verification paths.

## Intentional boundaries

- Replace performs no semantic interpretation, ranking, provider call,
  semantic cache lookup, or visible analysis session.
- Version 1 conservatively invalidates a plan when any local Context name is
  created or removed, even outside the selected roots. This is stricter than
  necessary but closes descendant-membership races at the Store boundary.
- Regex replacement backreferences, overlapping matches, semantic selection,
  referenced-Source mutation through a pointer, and deletion of the entire
  Memory are separate contracts and are not inferred.
