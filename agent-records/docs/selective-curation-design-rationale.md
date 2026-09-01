# Selective curation design rationale

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Problem

`mem forget` and `mem sever` began with separate provider and review paths even
though both perform the same middle operation: compare a complete Source frame
with one criterion frame, then keep, transform, or drop each Source Memory.
Forget supplies one natural-language instruction and mutates the Source;
Sever supplies a Criteria Context and updates each selected Source owner in
place. Keeping their
batch semantics separate made completeness, alias safety, exact-keep, and
empty-drop validation drift, while Forget retained a legacy sparse proposal
screen instead of the shared Resolution report.

## Shared contract

One provider turn receives one frozen `CurationBatch`:

```text
Source Memory frame × Criterion frame
    → exactly one decision per Source Memory
```

The criterion frame is typed rather than inferred. Forget wraps the submitted
instruction as one process-local `INSTRUCTION` item. Sever projects the
selected ordinary Criteria Context as a `MEMORY_FRAME`. Neither representation
turns an instruction into a durable Memory or allows an operation to bypass its
own Context-access rules.

Every operation-specific decision maps to one common action:

| Common action | Forget | Sever |
|---|---|---|
| `KEEP` | `KEEP` | `KEEP_AS_WRITTEN` |
| `TRANSFORM` | `EDIT` | redaction, summary, or condition-preserving rewrite |
| `DROP` | `DELETE` | `FORGET` |

The common decoder requires complete Source coverage, unique and available
aliases, nonempty rationale, exact Source text for `KEEP`, standalone nonempty
content for `TRANSFORM`, and empty content for `DROP`. A malformed record makes
the whole batch fail closed. Inference is deliberately batch-wide so a Memory
may be interpreted in the context of neighboring Source Memories; review and
materialization remain individually addressable by Source UID.

## Resolution report

TTY Forget and Sever both project their operation-owned state into the shared
Resolution Workbench with `REPORT`, `ITEMS`, and `TO DO`. Each item presents
classification, criterion, exact Source Memory, rationale, one decision section,
proposed result, response, and trace. A Forget instruction is neutral report
text in a `FORGET INSTRUCTION` block. It is not rendered as a Memory object and
does not receive a fabricated Memory UID. Sever's applicable Criteria evidence
remains exact Memory evidence with its real local provenance.

The report is a projection, not semantic authority. Forget retains a
process-local typed review and maps an accepted result back to legacy
`EditChange` and `RemoveChange` values. Its public `ops.forget()` API and eval
scoring therefore remain sparse: explicit `KEEP` decisions are removed only at
that compatibility boundary. Sever retains its existing durable schema,
session store, and workbench adapter; it maps the common decoded analysis into
`SeverCandidate` records.

Both reports identify their operation frame above their operation-owned
overview using the shared typed `CONTEXT LOCATIONS` projection. Forget labels
its batch prose `ASSESSMENT`; Sever labels its bounded Source account `SOURCE
OVERVIEW`. Neither is placed inside a generic model-comprehension group.
Forget shows its Source. New Sever sessions show Source and Criteria only; the
after-state is review evidence, not a third Context endpoint. Source ownership
fixes every Sever write location, so no `SAVE LOCATION` frame is rendered.

The complete Forget result uses the same located `MemoryChange` projection as
Sever and Diff instead of flattening every outcome into one Results paragraph.
Each frozen Source Memory is one independent Viewer stop: DROP renders the
original as a removal, TRANSFORM renders the original and reviewed replacement
as a before/after diff, and KEEP renders the original as equal. This is a
presentation projection of the complete review, not a change to Forget's sparse
public mutation API. Reusing the shared Impact controller also supplies common
Up/Down, PageUp/PageDown, Home/End, focus, wrapping, and rationale expansion;
Forget does not own a parallel large-result navigation grammar. The Impact is
rebuilt with every process-local review revision so a changed treatment cannot
leave a stale before/after display, while the frozen Source value remains the
authoritative `before` side until Apply.

## Flagless Forget setup

In a TTY, `mem forget` without an instruction opens a process-local setup
workbench before connecting a provider. Its compact form contains only a
direct `FROM` field with a transient Browse control, a one-line `INSTRUCTION`,
and one always-visible editable `COMMAND`. The command box is the sole
execution action. The setup therefore does not add a parallel `READY`, metrics,
`TO DO`, or action-button surface merely to restate whether the command is
runnable. Initial focus remains in Instruction so the common current-Context
case starts with immediate semantic input.

The form is deliberately bidirectional. A valid upper-field edit projects to
the canonical command `mem forget 'INSTRUCTION' --from SOURCE`. A valid command
edit parses and validates the complete Source/instruction pair before moving
either upper field, so an invalid or incomplete command cannot partially
change the visible request. If further typing makes a previously valid command
invalid, the upper form retains that last complete accepted pair. The shared
`CommandEditorControl` preserves a person's focused spelling and argument order
while they edit; the next genuine upper-form change reprojects the canonical
command. `--context` and `-c`
remain accepted compatibility aliases, but `--from` is the canonical editable
and public option because the field's role is Source selection.

The current Context is the initial `FROM` value and is marked only for
orientation. Browsing opens the common `ContextSelectorControl` in `SINGLE`
mode over one frozen `ALL READABLE CONTEXTS` catalog. Selecting another row
updates `FROM` and the command but does not switch the global current Context.
Running the command produces the same process-local `ForgetSetupResult`
containing one canonical public Context name and one nonblank instruction. The
command retrieves the selected Context's exact store and Grant binding from
the same frozen catalog rather than resolving current state again.

Forget deliberately exposes no `PROFILE`, `MULTIPLE`, descendant-range, or
embedded-Context controls. Its mutation unit remains one direct Context and
one checkpoint, and its semantic invariant remains one complete direct Source
frame against one instruction. Profile-wide or recursive selection would
instead require a multi-owner mutation plan, effect permissions, freshness
checks, rollback, and user-visible application receipt; it is not merely a UI
option. Granted readable rows retain their full permission annotation, while
the accepted reviewed edits and deletes continue to determine the exact
`UPDATE`/`DELETE` union at the normal mutation boundary.

Cancellation publishes no analysis and connects no provider. Outside a TTY,
an omitted instruction fails with a stable usage error. Supplying
`mem forget "INSTRUCTION"` preserves the existing current-Context fast path;
`--from SOURCE` selects another exact Source without opening setup. Both retain
non-TTY prompt compatibility, the whole-frame provider turn, authority and
review boundaries, and checkpoint behavior. The compact setup remains only a
request editor: its instruction is a process-local `INSTRUCTION` criterion,
never an inline Memory or fabricated durable provenance. After a successful
TTY Apply, the command prints the canonical public Source, submitted
instruction, exact applied change lines, and checkpoint identity as its durable
success receipt; this appears only after the authorized save succeeds.

The compact applied receipt deliberately projects changes as a diff instead of
repeating an `EFFECTS · REMOVE n · EDIT n` summary. Each removed or edited
Memory occupies exactly one logical line and is identified by its short UID. A
whole-Memory removal uses `-` and colors the removed content with the shared
REMOVE red. An in-place edit uses `~`, keeps mechanically equal words neutral,
and interleaves removed words in REMOVE red with replacement words in EDIT
green; it has no directional arrow. The submitted Forget instruction appears
once above the diff, so per-change `WHY` prose is omitted from this immediate
receipt while remaining available in the checkpoint-backed Review evidence.
When color is unavailable, edit spans use the explicit
`[-removed-][+added+]` fallback so redirected output does not hide which words
left or entered the Memory. KEEP decisions are not change lines, and the
accepted all-KEEP receipt remains the distinct no-change/no-checkpoint path.

The TTY application surface is ownership-aware. Provider dispositions stage one
answered treatment for every Source Memory. A local Source therefore applies
that complete decision-free batch directly and names `mem undo` in its receipt.
A granted Source is the actual authority mutation target, so it retains exact
final review when the reviewed batch contains an edit or removal. An all-KEEP
batch is different: it publishes no Context mutation, bypasses authority review,
prints an explicit unchanged/no-checkpoint receipt, and creates no artificial
Undo unit. This differs from Sever, where an all-KEEP review still records its
grouped Source-owner application even though Context bytes remain unchanged.

The Resolution workbench never mutates the loaded Context. It returns either
cancellation or the exact sparse reviewed change set. The command then computes
the required `UPDATE`/`DELETE` permissions, revalidates any Grant through the
authority-write boundary, applies the changes to the originally loaded direct
Context, and saves it with that load's optimistic Context digest. A concurrent
Source write therefore rejects the reviewed Forget before persistence; the
atomic save removes a provisional checkpoint on write failure, and the success
receipt is printed only after the checkpoint exists. Cancellation and accepted
all-KEEP completion remain observably distinct even though neither writes the
Source.

## Operation boundaries

The shared curation module does not resolve Context locators, open grants,
authorize provider disclosure, persist sessions, or mutate storage.

- Forget owns its direct active-Context scope, `UPDATE`/`DELETE` permission
  calculation, in-place Memory identity, and Source checkpoint.
- Sever owns independent Source/Criteria scope, retained Criteria grant
  bindings, local Source `UPDATE`/`DELETE` authority, grouped owner checkpoints,
  and its application receipt.

This separation prevents visual and semantic reuse from turning a read grant
into mutation authority. Forget uses one process-local instruction against one
Source; Sever uses a complete durable Criteria Memory frame and may update
multiple selected Source owners as one command.

## Compatibility and limitations

The batch decoder accepts the old sparse Forget provider shape only at a
compatibility boundary, expanding omitted Memories to explicit `KEEP`
decisions for review. New Forget prompts require complete candidates. The
public proposal API still returns only edits and removals so existing eval and
automation callers do not need to understand review-only `KEEP` values.

Forget review is currently process-local rather than a durable resumable saved
session. Sever remains durable. A later rollout may persist `ForgetReview`, but
must add source revision/digest revalidation and a normal command-unit CAS
boundary before advertising resume; the common curation contract alone does
not provide that authority or freshness guarantee.

The first implementation keeps Forget's non-TTY legacy prompt flow for script
compatibility. In a TTY, flagless setup precedes the shared Resolution
Workbench; an explicit instruction enters the existing Resolution path
directly.

Forget now resolves the same configured semantic provider as Sever and invokes
its bounded `complete()` primitive with the complete-coverage output schema.
The earlier CLI path required a second, Ollama-only `llm` setting even when the
profile's configured Codex, Ollama, or OpenRouter semantic provider was already
usable. That split made two implementations of the same selective-curation
contract fail at different setup boundaries. Existing library callers and test
doubles may still supply the old `chat(messages)` shape at a compatibility
boundary, but CLI provider selection, timeouts, and structured output no longer
use that legacy route. This migration does not make Forget durable or staged:
the complete Source, instruction, and any revision history still fit and run in
one provider turn or fail before disclosure.

The interactive Forget command wraps that indivisible whole-frame turn in the
shared `CommandProgress` heartbeat. It reports the frozen Source Memory count,
the one instruction criterion, animation, and elapsed seconds, but no invented
percentage or provider-internal stage. The transient line closes before the
Resolution Workbench opens. Redirected and non-TTY output retains the stable
legacy `Consulting ...` line because shared progress is deliberately TTY-only.

## 2026-08-20 lifecycle clarification

The whole-frame semantic invariant is unchanged, but the resulting decisions
now belong to the Forget/Sever execution invocation. “Resolution Workbench” in
the historical account means an execution decision surface, not the public
`mem review` operation. Successful Apply exits to a compact receipt; explicit
Review is a later read-only projection of terminal evidence.
