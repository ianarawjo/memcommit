# Selective curation design rationale

## Problem

`mem forget` and `mem sever` began with separate provider and review paths even
though both perform the same middle operation: compare a complete Source frame
with one criterion frame, then keep, transform, or drop each Source Memory.
Forget supplies one natural-language instruction and mutates the Source;
Sever supplies a Criteria Context and creates a separate result. Keeping their
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

Both reports identify their operation frame above `WHAT MEM UNDERSTOOD` using
the shared typed `CONTEXT LOCATIONS` projection. Forget shows its Source.
Sever shows Source, Criteria, and Result, including whether the Result is
`NOT CREATED` or `CREATED`. An unapplied Sever Result also uses the shared
compact `SAVE LOCATION` frame between `ITEMS` and final Review and Apply;
changing it updates the durable session but does not create the Context.

## Operation boundaries

The shared curation module does not resolve Context locators, open grants,
authorize provider disclosure, persist sessions, or mutate storage.

- Forget owns its direct active-Context scope, `UPDATE`/`DELETE` permission
  calculation, in-place Memory identity, and Source checkpoint.
- Sever owns independent Source/Criteria scope, retained granted bindings,
  `DERIVE + COMBINE + EXPORT + SAVE_ANALYSIS`, require-new result creation,
  and application receipt.

This separation prevents visual and semantic reuse from turning a read grant
into mutation or export authority. It also preserves the intentionally opposite
materialization semantics: Forget changes the Source, while Sever never does.

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
compatibility. The shared Resolution Workbench is the interactive TTY surface.
