# `mem summarize` and the shared understanding unit

> **Console route update (2026-08-30):** `mem summarize` now has one
> line-oriented result route. The `--plain`/`--tui` switches and generic
> console runner described in historical sections below are retired. The
> standalone workbench remains component-level code, not a current command
> entry path; see `summarize-application-boundary-matrix.md`.

## Status

Implemented. This note defines the reusable `UnderstandingSummary` embedded in
Atomize and Compare and the standalone read-only `mem summarize` producer.

## Decision

Only the source-linked `UnderstandingSummary` semantic value is common.
Its user-facing heading is owned by the operation that presents it:

```text
UnderstandingSummary
  text
  source Memory identities

Atomize
  UnderstandingSummary
  rendered as WHAT MEM UNDERSTOOD
  WHAT HAPPENED
  WHAT REMAINS UNRESOLVED

Compare
  UnderstandingSummary
  rendered as WHAT MEM UNDERSTOOD
  WHAT BOTH CONTAIN
  WHAT DIFFERS
  side-only reports

Summarize
  UnderstandingSummary
  rendered directly as the Summary body
```

`mem summarize [CONTEXT]` independently produces and renders only the shared
semantic unit. Because that one paragraph is the requested Summary artifact,
the `SUMMARY` command title already supplies its role and no nested
`WHAT MEM UNDERSTOOD` heading is shown. It does not run Atomize
classifications, ambiguity or conflict scans, a
comparison ledger, or any Context mutation. It is comprehension, not
distillation: no summary Memory or checkpoint is created.

The ordinary command is execution-first. `mem summarize` is already a complete
request because its Source defaults to the command-start current Context and
its reach defaults to direct; `mem summarize CONTEXT` replaces only that
Source. In automatic console mode both forms execute immediately and remain in
the primary line-oriented terminal flow, including in a TTY. The broader
Recent/Context/range workbench is an additional, explicit `--tui` action. This
keeps an executable operand from behaving like an initial value that still
requires a second Run confirmation, while retaining the exploratory flow for
people who ask for it.

Atomize retains its existing serialized overview shape for compatibility, but
its `understood` value is now the common type. Compare retains the serialized
`overview` string accepted by earlier analysis schemas while exposing the
validated in-memory value as `analysis.understanding`; `analysis.overview`
remains a compatibility text property. Both use the common terminal renderer.

## Standalone command contract

The command defaults to `-d/--direct`: only directly owned ordinary Memories
from the selected Context enter the frame. `-r/--recursive` expands every
readable lexical descendant name and follows permitted embedded Context edges.
A Context reached through both routes, or through a cycle, is visited once by
stable Context identity. Ordinary Memory order is preserved and temporary
provider aliases are mapped back to exact local Memory UIDs.

The normal output deliberately omits `WHAT WAS INCLUDED` and
`WHAT WAS OUTSIDE THIS SUMMARY` sections. Those are execution-scope facts, not
semantic understanding. The compact header states only `READ-ONLY` and
`RECURSIVE` or `DIRECT`; scope validation remains an internal invariant. The
two spellings are mutually exclusive and the application request retains
lexical descendant reach and embedded traversal as separate booleans.

`MemoryRef` and `QueryContextRef` content does not enter this first summary
frame. Query-only content is never opened. An empty ordinary-Memory frame is
reported deterministically without connecting a provider. Oversized input is
rejected rather than truncated or divided into hidden provider calls.

The provider returns one concise natural-language paragraph plus temporary
source aliases. Unknown aliases, repeated temporary aliases, duplicate JSON
keys, list-shaped prose, over-limit output, and source-free nonempty claims
fail closed. Two distinct authorized aliases may expose the same durable
Memory UID; their citations collapse to that UID once in first-seen order.
Output is terminal-escaped by the common renderer.

`--copy` writes the verified Summary body to the operating-system plain-text
clipboard after source revalidation. For an interactive `BOTH` result it keeps
`[CURRENT ONLY]` and `[CURRENT + DESCENDANTS]` as two labelled sections instead
of silently choosing one, but it does not repeat a second Summary or
understanding heading inside either scope. It
omits the command header and execution status, creates no structured mutation
clipboard stage, and performs no additional provider turn. A copy failure
leaves the rendered result visible and exits with an explicit error. Copying prose derived
from a granted frame is an explicit user-controlled disclosure outside the
revocable Grant store; it does not make the prose durable inside MemCommit.

The interactive Viewer exposes the same disclosure as a process-local action:
`y` copies the scope containing the focused Summary section and `Y` copies the
complete available Summary document. For `BOTH`, the shared title and status
describe the complete document, so `y` and `Y` are identical there. Focus
inside the current-only or descendants group makes lowercase `y` copy only
that labelled scope. These keys use the injected plain-text writer, show a
transient success or failure receipt, and likewise create no structured stage.

After the semantic call, the command rebuilds the same frame and compares its
digest before publishing output. A granted READ frame additionally freezes and
revalidates the exact grant binding. Ordinary results are process-local, so
authority-derived prose is not copied into the participant Store. A participant
Study Profile may resolve an exact prepared understanding from its pinned
immutable baseline bundle after the same READ freeze. The result is still
materialized only in the invoking process and is revalidated before return.

## Reuse boundary

Common type, evidence binding, and schema helpers are reusable. Presentation
headings and operation-specific prompt context are not. A summary may be reused
as data only when its complete frame and operation-neutral understanding
contract match; equal-looking prose does not prove equal evidence.

Physical provider batching is independent of this logical boundary. Atomize
may continue returning its understanding, classifications, and quality results
in one completion while validating the understanding as its own unit. A later
refactor may share more prompt composition without changing this contract.

## Intentional limitations

- No ordinary Profile-local summary cache, saved Summary session, or
  `--refresh` lifecycle exists. Study-only exact artifacts remain in the
  immutable shared baseline bundle.
- Plain clipboard integration inherits the existing macOS-only system
  clipboard adapter.
- No query-only summarize route is inferred; `mem query` remains authoritative.
- No responsibility judgment is inferred from content or grant ownership.
- Compare's historical overview serialization is not migrated implicitly.
- `WHAT HAPPENED`, unresolved findings, and comparison category reports are
  not generalized into the understanding unit.

## Application-boundary extraction

Summarize is the first non-Study operation used to validate the planned public
interface/application/infrastructure separation. The CLI now delegates the
complete read-only sequence to `memcommit.summarize_application.run_summarize`:
freeze an authorized frame, skip provider connection for an empty frame,
perform the bounded semantic call, revalidate the exact source, and return a
typed result.

The application module imports neither Typer, prompt-toolkit, nor
`memcommit.adapters.console.commands`. `memcommit.summarize_runtime` now supplies the real
MemoryStore/Grant adapter and a terminal-free `execute_summarize` composition;
provider construction remains injected and terminal rendering remains above the
application. The console host selects an adapter without putting terminal state
in the application. Automatic and `--plain` modes execute immediately and
render once. Explicit `--tui` mode first freezes the Profile-wide readable
Context catalog. The
three-way range control appears above the Context picker and offers `BOTH`,
`THIS CONTEXT ONLY`, and `INCLUDE DESCENDANTS`. The Context picker owns initial
focus and the same lazy direct-item preview as Distill: lowercase `m` affects
only the focused Context and uppercase `M` affects every Context in the frozen
readable catalog. These rows are inspection-only and do not change the staged
Context or reach. Before a result exists, the Summary frame itself contains the
explicit Run action, so one forward focus move from Context reaches execution.
An operand-free `--tui` flow starts on `BOTH`; explicit `-d` and `-r` retain
their individual initial selections.
Only the explicit Summarize action constructs and executes requests;
cancellation executes nothing. `BOTH` performs the direct request first and the
recursive request second, then publishes the pair only after both succeed.
Each later rerun is another visible action over the staged picker values. The CLI,
TUI, and direct Python runtime therefore share the same Source freeze, provider,
and freshness path while the use case can still run without a terminal or
command invocation.

The Summarize TUI composes a three-way reach choice, single-Context selector,
and typed semantic Viewer in one vertical workbench. The empty Viewer position
owns Run; after execution, the typed result replaces that action in place.
One result is projected directly from `SummarizeResult`; `BOTH` uses a typed
`SummarizeTuiOutcome` and shows `[CURRENT ONLY]` and `[CURRENT +
DESCENDANTS]` as independently navigable sections. It never parses CLI text or
derives one view by trimming the other. The picker is process-local and never
switches the global current Context. Each execution re-resolves and
reauthorizes the selected canonical name, freezes its source, and connects the
provider only when its frame is nonempty and no exact Study artifact is
available. There is no review/Apply lifecycle or Context mutation. Automatic
routing remains line-oriented; the explicit `--tui` route uses an injected
terminal capability and fails before Store construction when no TTY exists.

The runtime has one documented transitional dependency on the existing
operation-neutral Grant mechanics under `memcommit.application.context_access.access`.
Those mechanics are already reused outside commands. They are not copied or
moved in this slice because a second operation must first confirm their final
owner and lifecycle.

This is not yet a stable public Python API. The exact callable and dependency
record, security boundary, focused verification, and remaining gates are kept
in [`summarize-application-boundary-matrix.md`](summarize-application-boundary-matrix.md).
The component ownership, alternatives, migration boundary, installed-wheel
check, and ordered PTY evidence are recorded in
[`tui-component-architecture-design-rationale.md`](tui-component-architecture-design-rationale.md).
The current-vs-explicit immediate route and opt-in workbench are captured under
[`screenshots/mem-summarize-immediate-routing-20260821/`](screenshots/mem-summarize-immediate-routing-20260821/README.md).
