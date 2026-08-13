# `mem summarize` and the shared understanding unit

## Status

Implemented. This note defines the reusable `UnderstandingSummary` embedded in
Atomize and Compare and the standalone read-only `mem summarize` producer.

## Decision

Only `WHAT MEM UNDERSTOOD` is common. Operation-specific accounts remain owned
by their operation:

```text
UnderstandingSummary
  text
  source Memory identities

Atomize
  UnderstandingSummary
  WHAT HAPPENED
  WHAT REMAINS UNRESOLVED

Compare
  UnderstandingSummary
  WHAT BOTH CONTAIN
  WHAT DIFFERS
  side-only reports
```

`mem summarize [CONTEXT]` independently produces and renders only the shared
unit. It does not run Atomize classifications, ambiguity or conflict scans, a
comparison ledger, or any Context mutation. It is comprehension, not
distillation: no summary Memory or checkpoint is created.

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
source aliases. Unknown or duplicate aliases, duplicate JSON keys, list-shaped
prose, over-limit output, and source-free nonempty claims fail closed. Output
is terminal-escaped by the common renderer.

`--copy` writes the verified `WHAT MEM UNDERSTOOD` heading and body to the
operating-system plain-text clipboard after source revalidation. It omits the
command header and execution status, creates no structured mutation clipboard
stage, and performs no additional provider turn. A copy failure leaves the
rendered result visible and exits with an explicit error. Copying prose derived
from a granted frame is an explicit user-controlled disclosure outside the
revocable Grant store; it does not make the prose durable inside MemCommit.

After the semantic call, the command rebuilds the same frame and compares its
digest before publishing output. A granted READ frame additionally freezes and
revalidates the exact grant binding. Results are process-local: this avoids
copying authority-derived prose into the participant store and avoids creating
a stale summary cache before a separately designed revocable artifact exists.

## Reuse boundary

Common type, evidence binding, schema helpers, and rendering are reusable.
Operation-specific prompt context and the resulting text are not automatically
interchangeable. A summary may be reused as data only when its complete frame
and operation-neutral understanding contract match; equal-looking headings do
not prove equal evidence.

Physical provider batching is independent of this logical boundary. Atomize
may continue returning its understanding, classifications, and quality results
in one completion while validating the understanding as its own unit. A later
refactor may share more prompt composition without changing this contract.

## Intentional limitations

- No persistent summary cache or `--refresh` lifecycle exists yet.
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
`memcommit.commands`. `memcommit.summarize_runtime` now supplies the real
MemoryStore/Grant adapter and a terminal-free `execute_summarize` composition;
provider construction remains injected and terminal rendering remains above the
application. The console host executes that path once, then an injected router
selects either the plain renderer or the read-only semantic Viewer. The CLI,
TUI, and direct Python runtime therefore share the same Source freeze, provider,
and freshness path while the use case can still run without a terminal or
command invocation.

The Summarize TUI projects `SummarizeResult` directly into the shared typed
Viewer document. It does not parse CLI text, reload evidence, reconnect the
provider, or introduce a review/Apply lifecycle. Automatic routing uses an
injected terminal capability; `--plain` and `--tui` make the presentation route
explicit, and forced TUI failure occurs before Store construction.

The runtime has one documented transitional dependency on the existing
operation-neutral Grant mechanics under `memcommit.commands.granted_context`.
Those mechanics are already reused outside commands. They are not copied or
moved in this slice because a second operation must first confirm their final
owner and lifecycle.

This is not yet a stable public Python API. The exact callable and dependency
record, security boundary, focused verification, and remaining gates are kept
in [`summarize-application-boundary-matrix.md`](summarize-application-boundary-matrix.md).
The component ownership, alternatives, migration boundary, installed-wheel
check, and ordered PTY evidence are recorded in
[`tui-component-architecture-design-rationale.md`](tui-component-architecture-design-rationale.md).
