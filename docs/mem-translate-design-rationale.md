# `mem translate` design rationale

## Status and current decision

Bare `mem translate` is a persisted, read-oriented language view. It translates
the selected directly owned `Memory` records, saves the validated result as a
digest-bound sidecar projection, renders that projection, and exits:

```bash
mem translate
mem translate --to French
mem translate ac827aaa --to en-CA
mem translate --to English --refresh
```

`--to` defaults to `English`. One UID or unique UID prefix narrows the view to
one directly owned Memory. An exact stored projection is reused without
contacting the provider. `--refresh` deliberately obtains and publishes a new
translation even when the existing projection is an exact match.

This default does not create or modify a Context, write a checkpoint, change
the current Context, or allocate a result UID. In particular, translating a
Context named `task-123` no longer implicitly consumes a `task-123-en` Context
name. The translated strings are representations of existing Memories, not
new Memory occurrences.

Materialization remains explicit:

```bash
mem translate --to English --save-as task-123-en
mem translate --to English --in-place
```

`--save-as` creates a derived Context. `--in-place` retains the historical
bilingual-sibling operation. Those modes allocate result UIDs and record
checkpoints because they change the Memory graph; they cannot be combined.

## Semantic target and exact identity

`--to` accepts a semantic translation specification, not only a registered
language name or code. All of these are valid uses of the same option:

```bash
mem translate --to English
mem translate --to en-CA
mem translate --to "plain Canadian English for a newcomer; preserve legal terms"
```

Short conventional names and language tags are simply concise semantic
specifications. A longer value may additionally describe locale, dialect,
register, audience, or terminology. The complete trimmed string is sent to
the provider as data under the translation-only contract; there is no local
language registry, source-language detector, fuzzy resolver, or BCP 47
canonicalizer deciding what the person meant. The provider may interpret the
specification semantically, but only translation-related constraints are in
scope. A request for an unrelated action or for weakening the output contract
must be ignored.

Interpretation is semantic; persisted identity is exact. View lookup uses the
complete trimmed target string, case-sensitively, together with its source and
scope bindings. Thus `English`, `english`, and `plain English` intentionally
occupy different saved-view slots even when a provider might produce similar
text. Fuzzy reuse was rejected because two superficially similar descriptions
can differ materially in dialect, register, audience, or terminology. Reusing
one for the other would silently discard user intent and make cache behavior
and provenance difficult to explain. The one-line, printable target limit is
500 characters so useful guidance fits without turning `--to` into a general
prompt channel.

Shell quotes cannot select a second interpretation mode: a shell normally
removes grouping quotes before `mem` receives its argument, so `--to English`
and `--to "English"` arrive as the same string. Making quoted values semantic
and unquoted values registry-bound would therefore be inconsistent across
shells and direct API calls. If a future strict registered-tag mode is needed,
it should use an explicit option such as `--to-tag`, not quote syntax.

The serialized field remains named `target_language` for translation-plan,
sidecar, and checkpoint compatibility. Its contract is the semantic target
described above, not a claim that the value is a canonical language
identifier. `translate-v1` names this complete semantic-target and provider
contract because UID-less views are introduced with that behavior; there is
no earlier released view contract to migrate. A later material change to
prompt meaning or validation must use a new contract version and treat older
slots as stale rather than silently reusing them.

## Persisted view contract

For a direct source frame:

```text
source
├── Memory A
├── MemoryRef P
└── Memory B
```

a whole-Context English view contains translated text for A and B, anchored to
their existing UIDs. P remains a visible opaque pointer record. Rendering the
view does not make a second Context:

```text
source · English view
├── Memory A UID: translated text for A
├── unchanged MemoryRef P
└── Memory B UID: translated text for B
```

The sidecar is not a `Context`, `Memory`, checkpoint, or trace event. It has no
UID of its own and contains no translated-result UIDs. It records:

- the source Context's existing UID and name;
- the exact source direct-record digest;
- the exact validated semantic target and translation-contract version;
- whole-frame or selected-Memory scope;
- each existing source Memory UID and source-content digest;
- the validated translated text in canonical source order;
- a digest of the validated provider response.

An integrity digest over the sidecar may be used for validation and
compare-and-swap publication. That checksum is not an identity and must not be
surfaced as a Memory or projection UID.

The read-only planning path also leaves the translation operation UID unset.
An operation UID is allocated only when `--save-as` or `--in-place` crosses
the materialization boundary and a checkpointed graph change can occur.

Consequently ordinary identity-aware commands do not discover extra objects:
`mem contexts` still lists one source Context, and `mem ls`, `mem find`,
`mem merge`, and `mem trace` do not see a translated Memory until the person
explicitly materializes it.

## Reuse, refresh, and staleness

A projection is reusable only when all inputs that define its meaning match:
source Context UID, exact direct-record digest, semantic target string,
selection scope, selected source UID and content digest, and
translation-contract version. A matching call reads and renders the saved
sidecar without spending provider allowance. `--refresh` bypasses that reuse
check but retains the same source binding.

A changed direct frame makes the saved projection stale. This includes a
direct edit, addition, removal, reorder, pointer change, or deletion and
recreation of the Context. The next translation call obtains a new result and
atomically replaces the stale projection for that language and scope. It does
not accumulate a chain of obsolete translations and does not reuse a
translation merely because the semantic target still matches.

Provider work is performed outside long-lived Context locks. Before
publication, the command reacquires the cooperative source and projection
locks and revalidates both the exact source identity/digest and the previously
observed sidecar checksum or absence. If the source changed during the
provider call, the candidate is discarded and the earlier sidecar is
preserved. If another translation call published first, an older in-flight
call cannot overwrite it. A complete projection is published atomically, so
readers never observe a partially written translation.

Provider failure, invalid output, an empty candidate set, or failed
revalidation leaves the source and any earlier sidecar unchanged. Because the
default command has no Context application step, it needs no apply
confirmation and never changes global current-Context state.

## Data and graph boundary

Only directly owned `Memory` records are translation candidates.

- `MemoryRef` targets are not opened, sent, copied as content, or translated.
- `QueryContextRef` source content remains opaque and is never opened.
- Embedded Contexts are not traversed.
- Pointer records can be represented unchanged in the rendered direct-frame
  view, but their targets do not become projection payload.
- Selecting a pointer or embedded Context as the positional selector is an
  error.

The operation projects one direct Context frame; it does not translate a
recursive Context graph. A `MemoryRef` can still resolve to content in a
different language because it remains a live pointer to its existing source,
not because translate opened or persisted that target.

The base `Memory` schema remains `uid + content`. Language and view data stay
in the sidecar rather than adding operation-specific fields to every generic
Memory or treating different text as the same mutable Memory occurrence.

## Provider contract

Translation uses the temporary, ChatGPT-authenticated Codex provider used by
newer semantic operations. One invocation receives:

- a printable, one-line semantic translation target;
- opaque per-call candidate IDs such as `m000001`;
- exact content from the selected directly owned Memories.

Real Context and Memory UIDs are not sent. The prompt requests translation
only: no answering, summarization, normalization, correction, ambiguity
resolution, or fact addition. Names, numbers, dates, negation, modality,
uncertainty, relationships, Markdown, and line breaks should be preserved as
far as the semantic target permits.

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
sidecar or materialized result is published.

The one-call prototype caps serialized input at 200,000 characters and uses a
300-second Codex timeout. It does not silently batch or retry because doing so
would require a separate partial-failure contract.

## Explicit materialization and provenance

`--save-as CONTEXT` is the boundary at which a read-oriented representation
becomes a derived Memory graph. It uses an exact validated translation
projection, creates a destination with the supplied name, replaces each
selected source slot with a fresh-UID translated `Memory`, writes durable
baseline and translation checkpoints, and switches to the destination only
after the normal source and current-Context revalidation. There is no
automatic language-suffix destination; a person must opt into both
materialization and its name.

A selector produces a partially translated derived Context: only the selected
slot is replaced, while other directly owned Memories remain in their source
language. Pointer records are copied unchanged. A complete language version
therefore omits the selector.

The destination has two checkpoints and does not copy the source checkpoint
files:

1. an `init` baseline containing the exact source direct frame under a fresh
   destination Context UID and name;
2. a `translate` checkpoint replacing each selected source UID with its fresh
   result UID.

The baseline records the source Context identity and digest. Its purpose is
not to duplicate unrelated source history, but to give destination-local
trace reconstruction a real before-state. The translation checkpoint records:

- operation UID and exact semantic target;
- exact source Context UID, name, and direct-record digest;
- destination Context UID, name, and baseline digest;
- whole-Context or selected-Memory scope;
- provider-response digest;
- source/result UIDs and both content digests.

Checkpoint schema version 1 means the historical same-Context sibling
insertion. Schema version 2 means derived-Context replacement. `mem trace`
continues to validate both. For version 2 it additionally proves that:

- the baseline becomes the recorded source frame when only its root Context
  identity is changed back;
- removed UIDs are exactly the recorded sources;
- added UIDs are exactly the recorded results;
- every result occupies its source's raw direct slot;
- every unselected Memory and every pointer record is unchanged.

A valid mapping renders `TRANSLATED / RECORDED`. Invalid metadata falls back
to snapshot reconstruction with a warning rather than suppressing ordinary
created, removed, edited, or reordered events.

Before contacting the provider or reusing a projection for `--save-as`, the
destination name and current storage availability are checked. Creation
rechecks absence while holding the destination's cooperative write lock, so a
concurrently created Context is never overwritten. The baseline save and its
checkpoint are one atomic store operation. The final destination save uses
the baseline digest as an optimistic-concurrency compare-and-swap.

The source is reloaded and compared with the exact projection before
derivation and again before switching. Any source-frame or current-Context
change prevents the final switch and leaves the source untouched. Once a
baseline Context has been published, it is not automatically deleted during
error cleanup: another process could already have switched to, embedded, or
referenced it. A later failure instead preserves the visible baseline or
completed destination for manual inspection.

`--in-place` retains the version-1 behavior for an intentionally bilingual
Context: it inserts a fresh-UID translated sibling immediately after every
selected source and writes its translation checkpoint. It is not a sidecar
view and cannot be combined with `--save-as`.

## Why this is not `impact`

An impact artifact answers what a proposed state-changing operation would do
and exists to support review before a separate application decision. The
translated language view is itself the requested read result. Persisting it
makes repeated reading deterministic and avoids another provider call; it
does not imply a pending Context mutation.

Putting this behavior under `mem impact` would therefore misstate the user's
intent and make ordinary reading look like an unapplied edit. Conversely,
automatically creating `task-123-en` would assign new Context and Memory
identity to a representation that may only be needed for one reading session,
pollute Context navigation, and require checkpoint/current-switch semantics.
Explicit `--save-as` preserves that stronger operation for cases where the
translated text must become independently editable or addressable.

## Privacy, deletion, and lifecycle

Ordinary selected Memory content is sent to OpenAI and consumes the user's
ChatGPT Codex allowance when no exact view is reused or when `--refresh` is
requested. Query-only source material is neither loaded nor sent. The
translated text is persisted locally and should be treated with the same
sensitivity and retention expectations as its source content, not as an
ephemeral terminal preview.

Sidecars are owned by the source Context lifecycle. Cooperative source
Context deletion removes its translation projections while holding the same
lifecycle boundary, so translated content does not survive as an
undiscoverable orphan. A stale replacement removes the superseded payload
only after the new projection is durable. Failure before atomic publication
retains the prior payload.

Sidecars are not copied merely because a Context is embedded or referenced,
and deleting one must not touch the source Memories or a separately
materialized Context. A materialized destination owns its fresh Memories and
checkpoint evidence independently; later sidecar refresh or deletion cannot
rewrite that history.

This research provider is not a production security boundary; use only study
data approved for that provider. The instruction to treat the semantic target
and Memory content as data is a behavioral prompt boundary, not a proof of
prompt-injection isolation. Strict JSON output validation proves the shape of
what is accepted locally, but it does not prove what the provider did while
producing it; a read-only sandbox is not confidentiality isolation. A
production implementation should use a tool-less translation endpoint with
explicit access and retention policy.

## Implementation history and retained compatibility

The first implementation inserted translated siblings into the current
Context. A live 54-Memory Korean-to-English pilot proved the provider,
persistence, and lineage plumbing, but produced a difficult 108-item
bilingual list and allowed a later whole-Context run to translate earlier
translations. The implementation next made a fresh, automatically named
derived Context the default. That avoided the bilingual list, established the
version-2 baseline/provenance model, and preserved the source, but still
created durable identity and changed navigation for a read-oriented request.

The persisted UID-less view is the new default because it keeps the useful
provider result and exact source binding without enlarging the Memory graph.
The two earlier materialization behaviors remain explicit as `--in-place` and
`--save-as`; their checkpoint schemas and trace validation remain readable.
The live pilot establishes end-to-end execution, not automated translation
quality. Human assessment of terminology, dialect, and semantic equivalence
remains separate.

## Intentional limitations

- Translation quality, dialect choice, terminology consistency, and semantic
  equivalence are not mechanically proven by strict JSON validation.
- Source-language detection is delegated to the provider.
- Recursive graph translation, automatic provider retries, and partial
  provider-result recovery remain outside this version.
- One saved projection covers one exact semantic target and one whole-frame
  or selected-Memory scope; it is not a multilingual Memory schema.
- A partially translated materialized Context intentionally contains more
  than one language.
- `mem merge` remains a structural fresh-UID union. Merging a materialized
  translated Context into its source deliberately creates a bilingual
  Context; sidecar views do not participate.
- Semantic targets are interpreted by the provider but reused only by their
  exact trimmed, case-sensitive strings. They do not claim language detection,
  fuzzy equivalence, or BCP 47 canonicalization.
- A translation target does not select the authoring, analysis, explanation,
  or interface language for Mem as a whole. That broader multilingual policy
  remains the deferred research TODO in
  [`multilingual-memory-and-explanation-language-design-rationale.md`](multilingual-memory-and-explanation-language-design-rationale.md).
- Translate's projection publication, Context creation/save, final
  state-switch, and Context deletion paths use cooperative locks. Unsupported
  direct JSON edits do not participate in those guarantees.
