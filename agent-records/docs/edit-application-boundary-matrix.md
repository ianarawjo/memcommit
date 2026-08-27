# Edit application boundary matrix

## Decision

Single-Memory Edit now has one terminal-independent freeze/apply boundary.
Explicit `mem edit MEMORY_SELECTOR CONTENT [--context CONTEXT]`, qualified
`mem edit CONTEXT:UID CONTENT`, and bare TTY setup all resolve the same direct
ordinary Memory, retain its full UID and position, and publish at most one Edit
checkpoint. A bare UID scans every ordinary local direct Context without
preferring the current Context; multiple matches fail closed and require
`CONTEXT:UID`. File/stdin batch mode stays the established `--input BATCH_FILE`
route; `--input` is not an inline content option and cannot be combined with
positional selector or content.

## Route and ownership matrix

| Concern or route | Owner | Invariant |
| --- | --- | --- |
| Exact request, locator grammar, frozen plan, and receipt | `memcommit.application.operations.edit.application` | Terminal-, Store-, and provider-independent values; `CONTEXT:UID` and `--context` are mutually exclusive; receipt must match the frozen Context, Memory, before value, and requested after value. The former `memcommit.edit_application` path remains a module-identity compatibility alias. |
| UPDATE access, direct-Memory/profile search, drift check, save, checkpoint | `memcommit.application.operations.edit.runtime.MemoryStoreEditPort` | Capture current once; freeze exact canonical Context UID/digest and full Memory UID/content; changed Context or Memory publishes nothing. Bare search enumerates ordinary local direct frames only. The former `memcommit.edit_runtime` path remains a module-identity compatibility alias. |
| Prefix grammar | `memcommit.application.ops.resolve_direct_memory` | Exact UID or one unambiguous prefix across direct items; MemoryRef, embedded Context, and query rows are never editable Memories. |
| Explicit and batch CLI composition | `memcommit.commands.edit.command` | Positional selector/content routes to the exact application; `--input` retains atomic UID-tab-content batch parsing and its existing checkpoint. |
| Interactive setup | `memcommit.adapters.interfaces.tui.operations.edit` | Shared direct-Memory selector -> prefilled multiline replacement -> proposed exact command -> `FrozenEditPlan`; process-local editing has no durable effect. |
| Shared selector mechanics | `memcommit.core.context_targeting.tui.direct_memory_selector` | Context cursor, Memory hover, and checked exact Memory remain distinct; the control assigns no edit/snapshot/embed meaning. |

## Freeze and Apply

The runtime captures the command-start current Context once. A qualified
`CONTEXT:UID` splits the owner from the Memory selector, resolves relative
Context syntax such as `../source:UID` against that one snapshot, and then uses
the same UPDATE access path as `--context`. Supplying both owner forms is an
error. A bare selector scans one strict snapshot of every ordinary local direct
frame. Exactly one matching ordinary Memory is required even when one match is
in the current Context; a current match never hides another owner.

Profile search ignores MemoryRef records and embedded Context bodies. It
deduplicates nothing across owners: copied branch identities are deliberately
ambiguous and the error prints each canonical `CONTEXT:FULL_UID` choice with
its JSON-quoted exact content, followed by an instruction to rerun with the
chosen displayed value. This recognition aid remains limited to the ordinary
local direct-Memory catalog already searched by the command. Granted
mutation remains explicitly named with a public `CONTEXT:UID` or `--context`
instead of silently enumerating authority content. Freeze then records the
canonical Context UID, record digest, full Memory UID, and original content.
Interactive Edit continues to prefill the editor from one exact selected row
and reviews a command containing the full UID, exact multiline value, and
canonical public Context name.

Edit projects that final boundary as one editable `PROPOSED COMMAND` frame. A
Memory choice or replacement-content change immediately rebuilds the command;
a complete valid command atomically updates the checked direct Memory and the
multiline replacement field. Invalid or incomplete command text remains local,
moves neither upper field, turns the frame red, and blocks Apply. Because the
command is one physical terminal line, arbitrary replacement content uses the
canonical injective display escapes: `\n` represents a newline while `\\n`
represents a literal backslash followed by `n`.

The `mem edit` operation prefix is a fixed prompt outside the writable buffer;
only its arguments can be revised. Destructive editing and pasted text cannot
delete or replace the operation name, while validation still reconstructs the
whole line and checks the form prefix before any upper control changes.

The runnable frame contains only the shell-quoted argv; an invalid frame adds
only its validation reason, and the apply instruction stays in the footer. It
deliberately omits the generic `TO DO` label, effect summary, and approval prose
because those lines repeat the single-Memory contract already established by
selection and do not participate in execution. This is an Edit-only
presentation choice: the frozen review still retains its effect metadata for
equality checks, and other exact-command consumers keep their
operation-appropriate summaries.

Apply reloads and compares the frozen Context and Memory before modifying the
detached frame. A drift failure, cancellation, or invalid selector publishes no
partial content or checkpoint. A changed replacement preserves UID/order and
creates one checkpoint through the authorized mutation boundary. An unchanged
replacement creates no checkpoint and returns an explicit unchanged receipt.

## Selector and input roles

Selector-looking text is not enough to determine an object role. Add stores
its positional value literally as new Memory content. Edit uses a positional
`MEMORY_SELECTOR` and accepts its owner as `CONTEXT:UID` or
`--context CONTEXT`. The `:` separator has always been forbidden in ordinary
Context names, while `#` already identifies view handles elsewhere. `--input`
consistently names an external batch input in Add/Edit and never means the
replacement content following a selector.

Help forms therefore spell `[memory_content]` separately from
`[memory_selector]`, and CLI usage errors give an executable canonical example
instead of only reporting that arguments conflict.

## Boundaries and verification

- Version 1 does not move Edit's existing atomic batch-file route into the
  single-Memory application type; the two intake shapes remain explicit.
- Edit does not call a provider or use semantic cache/session state.
- A Memory Embed or Reference remains read-only in its containing Context.
  Cross-Context lookup selects the directly owned Source Memory; it never
  writes through a pointer or refreshes an immutable snapshot.
- The TUI does not persist drafts or broaden UPDATE authority.
- `tests/test_edit.py` covers qualified and relative owner locators, bare local
  search, cross-owner ambiguity, the established prefix grammar, exact
  checkpoint, unchanged route, non-Memory rejection, and post-freeze drift.
- `tests/test_edit.py` also covers interactive prefill, exact replacement
  freeze, command-to-control synchronization, and cancellation. The ordered
  180×52 real-color flow is recorded in
  `agent-records/docs/screenshots/direct-memory-selector-actions-20260820/edit-interaction-log.md`.
