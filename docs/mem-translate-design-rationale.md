# `mem translate` design rationale

## Status and current decision

`mem translate` creates a new derived Context by default. Each selected,
directly owned source `Memory` is replaced at the same logical slot in the
derived Context by one fresh-UID translated `Memory`. The source Context,
source Memories, and source checkpoint history are not changed.

```bash
mem translate
mem translate --to French
mem translate --to English --save-as task-123-en
mem translate ac827aaa --to en-CA
mem translate --to English --yes
```

`--to` defaults to `English`. `--yes` skips confirmation, but not provider
validation, source revalidation, collision checks, or persistence checks.
One UID or unique UID prefix narrows the operation to one directly owned
Memory; the other direct items remain unchanged in the derived Context.

The initial implementation inserted translated siblings into the current
Context. A live 54-Memory Korean-to-English pilot proved the provider,
persistence, and lineage plumbing, but it also made the usability problem
concrete: the resulting 108-item bilingual list was difficult to navigate,
and another whole-Context run could translate both originals and earlier
translations. The default therefore changed to a derived Context after the
pilot. The earlier checkpoint schema remains readable, and the old behavior
is available only through the explicit `--in-place` option.

The live run establishes end-to-end execution, not automated translation
quality. Human assessment of terminology, dialect, and semantic equivalence
remains separate.

## Derived Context contract

For a current Context named `task-123`, the default English destination is:

```text
task-123-en
```

`English` deliberately uses the study-facing `en` suffix. Other target labels
are NFKC-normalized, case-folded, and reduced to a hyphenated alphanumeric
slug for naming only. This does not claim language detection or BCP 47
canonicalization. `--save-as CONTEXT` supplies an exact destination name.
A collision is an error; the command never silently invents `-2` because that
would make duplicate translated versions easy to create accidentally.

Given:

```text
source
├── Memory A
├── MemoryRef P
└── Memory B
```

a whole-Context translation produces:

```text
source-en
├── translated Memory A'
├── unchanged MemoryRef P
└── translated Memory B'
```

The source still contains only A, P, and B. The destination contains A', P,
and B, so its ordinary `mem ls` output does not show source/translation pairs.
Fresh result UIDs preserve an explicit derivation rather than treating
different text as the same live occurrence.

A selector creates a partially translated derived Context: only the selected
slot is replaced, while other directly owned Memories stay in their source
language. This is intentional branch-like editing, but a user wanting a
complete language version should omit the selector.

After both destination checkpoints are durable, the command atomically checks
that the global current Context is still the source and switches to the
destination. A concurrent switch is never overwritten.

## Baseline and translation checkpoints

The destination has two checkpoints and does not copy the source's checkpoint
files:

1. an `init` baseline containing the exact source direct frame under a fresh
   destination Context UID and name;
2. a `translate` checkpoint replacing each selected source UID with its fresh
   result UID.

The baseline records the source Context identity and digest. Its purpose is
not to duplicate unrelated source history, but to give destination-local
trace reconstruction a real before-state. The translation checkpoint records:

- operation UID and target-language label;
- exact source Context UID, name, and direct-record digest;
- destination Context UID, name, and baseline digest;
- whole-Context or selected-Memory scope;
- provider-response digest;
- source/result UIDs and both content digests.

Checkpoint schema version 1 means the earlier same-Context sibling insertion.
Schema version 2 means derived-Context replacement. `mem trace` validates both.
For version 2 it additionally proves that:

- the baseline becomes the recorded source frame when only its root Context
  identity is changed back;
- removed UIDs are exactly the recorded sources;
- added UIDs are exactly the recorded results;
- every result occupies its source's raw direct slot;
- every unselected Memory and every pointer record is unchanged.

A valid mapping renders `TRANSLATED / RECORDED`. Invalid metadata falls back
to snapshot reconstruction with a warning rather than suppressing ordinary
created, removed, edited, or reordered events.

## Data and graph boundary

Only directly owned `Memory` records are translation candidates.

- `MemoryRef` targets are not opened, sent, copied as content, or translated.
- `QueryContextRef` source content remains opaque and is never opened.
- Embedded Contexts are not traversed.
- All three pointer record types are copied unchanged into the destination.
- Selecting a pointer or embedded Context as the positional selector is an
  error.

The operation derives one direct Context frame; it does not translate a
recursive Context graph. A copied `MemoryRef` can still display content in a
different language because it remains a live pointer to its existing source.

The base `Memory` schema remains `uid + content`. Language and derivation
metadata live in validated checkpoint evidence rather than adding
operation-specific fields to every generic Memory.

## Provider contract

Translation uses the temporary, ChatGPT-authenticated Codex provider used by
newer semantic operations. One invocation receives:

- a printable target-language label;
- opaque per-call candidate IDs such as `m000001`;
- exact content from the selected directly owned Memories.

Real Context and Memory UIDs are not sent. The prompt requests translation
only: no answering, summarization, normalization, correction, ambiguity
resolution, or fact addition. Names, numbers, dates, negation, modality,
uncertainty, relationships, Markdown, and line breaks should be preserved as
far as the target language permits.

The model must return exactly:

```json
{
  "translations": [
    {
      "candidate_id": "m000001",
      "translated_content": "..."
    }
  ]
}
```

The output schema fixes the item count and candidate-ID allowlist. Local
validation rejects duplicate JSON keys, extra fields, missing, duplicate, or
unknown candidates, blank or non-string content, oversized input/output, and
terminal control characters. Provider order is ignored; results are rebound
to sources in canonical source order. Any validation failure occurs before a
result UID or destination Context is created.

The one-call prototype caps serialized input at 200,000 characters and uses a
300-second Codex timeout. It does not silently batch or retry because doing so
would require a separate partial-failure contract.

## Preview, application, publication, and concurrency

The complete validated mapping and destination name are displayed before any
write. Confirmation defaults to No. Rejection, provider failure, invalid
output, or an empty candidate set creates no destination and no checkpoint.

Before contacting the provider, the destination name and current storage
availability are checked. Creation later rechecks absence while holding the
destination's cooperative write lock, so a concurrently created Context is
never overwritten. The baseline save and its checkpoint are one atomic store
operation. The final destination save uses the baseline digest as an
optimistic-concurrency compare-and-swap.

The source is reloaded and compared with the provider plan before derivation
and again before switching. Any direct edit, addition, removal, reorder,
pointer change, delete/recreate, or current-Context change prevents the final
switch and leaves the source untouched. The final switch uses a locked
compare-and-set on global state while holding the destination Context lock and
revalidating its exact UID and digest. Cooperative Context deletion uses the
same lock, so the destination cannot be deleted or replaced between that
validation and the state update.

Once the baseline Context is published, it is never deleted automatically as
error cleanup. Another process could already have switched to, embedded, or
referenced that Context without changing the destination's own digest, so
deletion could create a dangling external pointer. A failure after baseline
publication instead preserves either the baseline or completed destination
and reports it for manual inspection. This is a visible recoverable partial
outcome, while failures before publication still leave no destination.

`--in-place` retains the earlier version-1 sibling behavior for an intentional
bilingual Context. It cannot be combined with `--save-as`.

## Privacy and trust boundary

Ordinary selected Memory content is sent to OpenAI and consumes the user's
ChatGPT Codex allowance. Query-only source material is neither loaded nor
sent. This research provider is not a production security boundary; use only
study data approved for that provider. A production implementation should use
a tool-less translation endpoint with explicit access and retention policy.

## Intentional limitations

- Translation quality, dialect choice, terminology consistency, and semantic
  equivalence are not mechanically proven by strict JSON validation.
- Source-language detection is delegated to the provider.
- Recursive graph translation, automatic provider retries, and cached
  previews remain outside this version.
- A partially translated derived Context intentionally contains more than one
  language.
- `mem merge` is a structural fresh-UID union. Merging a translated Context
  into its source would deliberately recreate a bilingual Context and is not
  the intended translated-version workflow.
- Context names are language hints, not stored language metadata.
- Translate's Context creation, Context save, final state-switch, and Context
  deletion paths use cooperative locks. Other store paths do not all share one
  cross-operation transaction, and unsupported direct JSON edits do not
  participate.
