# `mem translate` design rationale

## Implementation ownership

Translate follows the repository's layer boundary instead of treating one
operation package as the owner of every concept. The command-independent
`MemoryTranslationCatalog`, its entries, provider/curated variants, and their
invariants belong to `memcommit.core.memory_translation`. They describe what a
same-UID translation catalog means without knowing how a provider, file, or
terminal works.

`memcommit.application.operations.translation.translate` owns the Translate use cases.
`application` validates and orchestrates typed requests;
`provider_catalog` converts provider plans to and from the core catalog;
`curate_translations` owns edit, verify, reset, and catalog-save workflows;
`exchange_translations` owns import/export documents; and
`add_translations_to_current_context` plus `create_translated_context` own the
two explicit Context write actions. `runtime` retains provider planning and
pure in-memory Context transformations.

`memcommit.persistence.store.translation_catalog` owns only the durable JSON
record format, path/key convention, filesystem validation, locks, atomic
publication, source revalidation, and compare-and-swap. The console command
owns argv, terminal/file I/O, progress, editor launch, Save Location review,
and rendering. Persistence does not import Translate application code, and
Core imports neither Application nor Persistence.

The reviewed route is now `CLOSED`. The CLI owns only argv, terminal/file I/O,
progress, editor launch, Save Location review, and rendering adapters; every
semantic and durable decision enters the typed operation boundary recorded in
`translate-application-boundary-matrix.md`.

## Status and current decision

Bare `mem translate` is a persisted, read-oriented language catalog. It translates
the selected directly owned `Memory` records, saves the validated result as a
digest-bound same-UID catalog, renders that representation, and exits:

```bash
mem translate
mem translate --to French
mem translate task-123 --to English
mem translate ac827aaa --to en-CA
mem translate task-123:ac827aaa --to en-CA
mem translate --to English --refresh
```

`--to` defaults to `English`. The optional positional target uses the shared
Context/direct-Memory grammar: a Context locator selects that direct frame, a
bare public UUID-shaped UID or prefix finds one unique ordinary-local direct
owner, and `CONTEXT:UID` states the owner explicitly. A Memory target narrows
the catalog operation to one directly owned Memory. An exact stored catalog is reused without
contacting the provider. `--refresh` deliberately obtains and publishes a new
provider translation even when the existing representation is an exact match.
It never overwrites a manually edited or imported representation.

The same catalog is also an explicit editing and review surface:

```bash
mem translate ac827aaa --to ko --edit
mem translate ac827aaa --to ko --set "정확한 한국어 본문"
mem translate ac827aaa --to ko --verify
mem translate ac827aaa --to ko --unverify
mem translate ac827aaa --to ko --reset
mem translate --to ko --export translations.json
mem translate --to ko --input translations.json
```

`--export` emits source UID and source-content digest bindings plus the exact
base catalog digest. `--input` requires those bindings and applies the complete
validated batch in one catalog compare-and-swap. Rows whose text and review
state were not changed retain their existing provider or curated provenance;
only changed rows become imported curated layers. Imported text and manual
edits are curated layers;
their review state is either `UNREVIEWED` or `VERIFIED`. Verification binds
the exact current translation digest rather than making a general quality
claim about future edits.

This default does not create or modify a Context, write a checkpoint, change
the current Context, or allocate a result UID. In particular, translating a
Context named `task-123` no longer implicitly consumes a `task-123-en` Context
name. The translated strings are representations of existing Memories, not
new Memory occurrences.

An explicit noncurrent Context or uniquely owned Memory is valid for this
read-oriented saved catalog and does not switch current. Context Apply remains
more restrictive: `--save-as` and `--in-place` require the selected Source to
be the command-start current Context and reject a noncurrent target before a
provider is connected. That preserves the existing source/current
revalidation and final-switch contract rather than granting cross-Context
mutation through positional auto-typing.

## Provider and curated layers

There is one authoritative catalog for each exact
`(Context UID, semantic target)` pair and one entry for each source Memory UID.
An entry may retain two layers:

- a provider layer bound to the complete direct Context digest, source text
  digest, provider response digest, and generation time; and
- a curated layer bound to the source text digest, exact edited/imported text,
  origin, review status, optional import evidence digest, and review time.

The current curated layer wins when its source digest is current. Otherwise a
current provider layer may be displayed. Provider refresh changes only the
provider layer. This asymmetry is deliberate: a model refresh is allowed to
improve a generated baseline but cannot silently replace text that a person
edited, imported, or verified.

A later source edit does not delete curated work because the same UID remains
reachable. The catalog retains it as a stale entry and reports that state,
while refusing to display or verify the old translation as current. Removing
the source UID instead purges both provider and curated layers on the next
catalog write: otherwise that text would have no valid selector, source, or
reset path.

The batch import schema is intentionally strict. It carries the exact Context
UID/name, semantic target, and base catalog digest, and each record carries
source UID, source SHA-256, translated content, and review status. Duplicate
keys, duplicate source UIDs, unknown sources, stale hashes, invalid scalar
types, attempts to blank an existing translation, or extra fields reject the
whole batch before publication. Blank rows for sources that still have no
translation remain harmless export placeholders. An imported `VERIFIED` value therefore
means the supplied pair was reviewed by the importing workflow; existing
fixture-level checkboxes about source text do not automatically imply
cross-language equivalence.

Context Apply remains explicit:

```bash
mem translate --to English --save-as task-123-en
mem translate --to English --in-place
```

`--save-as` creates a derived Context. `--in-place` retains the historical
bilingual-sibling operation. Those modes allocate result UIDs and record
checkpoints because they change the Memory graph; they cannot be combined.
The explicit `--in-place` option is the complete approval for its checkpointed
mutation and does not open a second `y/N` prompt.

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

Interpretation is semantic; persisted identity is exact. Catalog lookup uses the
complete trimmed target string, case-sensitively, together with its source and
scope bindings. Thus `English`, `english`, and `plain English` intentionally
occupy different catalog slots even when a provider might produce similar
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

The serialized field remains named `target_language` in translation plans,
catalog records, and checkpoints. Its contract is the semantic target
described above, not a claim that the value is a canonical language
identifier. `translate-v2` is currently the sole supported provider/curated
catalog contract. The pre-release provider-only scoped-view implementation and
its migration path were removed rather than retained as a second model. A
later material change to prompt meaning or validation must use a new contract
version rather than silently reusing incompatible results.

## Persisted catalog contract

For a direct source frame:

```text
source
├── Memory A
├── MemoryRef P
└── Memory B
```

a whole-Context English catalog contains translated text for A and B, anchored to
their existing UIDs. P remains a visible opaque pointer record. Rendering the
view does not make a second Context:

```text
source · English catalog
├── Memory A UID: translated text for A
├── unchanged MemoryRef P
└── Memory B UID: translated text for B
```

The catalog is not a `Context`, `Memory`, checkpoint, or trace event. It has no
UID of its own and contains no translated-result UIDs. Its durable record contains:

- the source Context's existing UID and name;
- the exact validated semantic target and translation-contract version;
- catalog creation/update times and a compare-and-swap revision;
- each existing source Memory UID; and
- optional provider and curated variants with their separate source,
  evidence, text, time, origin, and review bindings.

Whole-frame and selected calls merge into this one catalog rather than
occupying competing scope files. Only the authoritative catalog schema is
readable; the removed pre-release scoped-view files are neither loaded nor
migrated. The physical store directory is still named `translation-views` so
existing study fixture layout need not change in this refactor. That directory
spelling is a persistence detail and a separate future storage-layout decision,
not a second domain concept.

An integrity digest over the catalog record may be used for validation and
compare-and-swap publication. That checksum is not an identity and must not be
surfaced as a Memory or catalog UID.

The read-only planning path also leaves the translation operation UID unset.
An operation UID is allocated only when `--save-as` or `--in-place` crosses
the Context Apply boundary and a checkpointed graph change can occur.

Consequently ordinary identity-aware commands do not discover extra objects:
`mem contexts` still lists one source Context, and `mem ls`, `mem find`,
`mem merge`, and `mem trace` do not see a translated Memory until the person
explicitly applies it to a Context.

## Reuse, refresh, and staleness

A provider variant is reusable only when its source Context UID, exact direct
record digest, semantic target, source UID/content digest, and contract match.
A curated variant is reusable when its Context identity, target, source UID,
and source-content digest match. It deliberately does not depend on unrelated
Memory reorder or pointer changes because no provider inferred it from the
whole frame. A matching call reads and renders the catalog without spending
provider allowance. `--refresh` bypasses provider reuse but retains the same
source binding and every curated layer.

A changed direct frame makes provider variants stale. A source Memory edit also
makes that UID's curated variant stale but preserves its text for repair.
Removal purges the entry because there is no longer an identity against which
it could be reviewed. A later provider call may populate a current provider
fallback without silently deleting or relabeling stale curated work for an
edited source.

Provider work is performed outside long-lived Context locks. Before
publication, the command reacquires the cooperative source and catalog
locks and revalidates both the exact source identity/digest and the previously
observed catalog checksum or absence. If the source changed during the
provider call, the candidate is discarded and the earlier catalog is
preserved. If another translation call published first, an older in-flight
call cannot overwrite it. A complete catalog is published atomically, so
readers never observe a partially written catalog.

Manual and imported changes use the same catalog-level compare-and-swap but
revalidate only the exact source UIDs and content digests edited in that
operation. This permits repair of one current entry even when an unrelated
preserved entry is stale, without weakening the edited source binding. Every
catalog entry must still have a directly owned source UID at the final locked
write: an unrelated concurrent source removal rejects the save so stale
caller state cannot resurrect its orphaned catalog entry.

Provider failure, invalid output, an empty candidate set, or failed
revalidation leaves the source and any earlier catalog unchanged. Because the
default command has no Context application step, it needs no apply
confirmation and never changes global current-Context state.

## Data and graph boundary

Only directly owned `Memory` records are translation candidates.

- `MemoryRef` targets are not opened, sent, copied as content, or translated.
- `QueryContextRef` source content remains opaque and is never opened.
- Embedded Contexts are not traversed.
- Pointer records can be represented unchanged in the rendered direct-frame
  catalog, but their targets do not become provider payload.
- Selecting a pointer or embedded Context as the positional selector is an
  error.

The operation projects one direct Context frame; it does not translate a
recursive Context graph. A `MemoryRef` can still resolve to content in a
different language because it remains a live pointer to its existing source,
not because translate opened or persisted that target.

The base `Memory` schema remains `uid + content`. Language and catalog data stay
in the catalog record rather than adding operation-specific fields to every generic
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
catalog or Context result is published.

Each provider payload uses the shared 1,000,000-character effective provider
capacity and a 300-second Codex timeout. A fitting selection retains the
historical one-call path. A
larger selection uses the shared `COVERAGE_MAP` plan: batches split only between
Memories, every global candidate alias is exposed exactly once, every batch is
fully validated, and no plan is returned after a partial failure. One oversized
Memory is never truncated. The final proposals retain canonical source order.

## Explicit Context Apply and provenance

`--save-as CONTEXT` is the boundary at which a read-oriented representation
becomes a derived Memory graph. It uses an exact validated translation
catalog selection, creates a destination with the supplied name, replaces each
selected source slot with a fresh-UID translated `Memory`, writes durable
baseline and translation checkpoints, and switches to the destination only
after the normal source and current-Context revalidation. There is no
automatic language-suffix destination; a person must opt into both Context
creation and its name.

Immediately after the translation preview and before Apply, interactive
`--save-as` renders the shared `SAVE LOCATION` card. `E` opens a one-line
direct edit, revalidates the replacement as an exact fresh ordinary Context
name, and returns to the same apply choice without another provider turn.
`--yes` deliberately bypasses this review and remains bound to the exact CLI
operand. In-place translation omits the card because it updates the already
reviewed source Context rather than creating a distinct result. It applies
immediately after rendering the informational translation preview; `--yes`
remains accepted with `--in-place` only so existing scripts keep working.

The current checkpoint provenance schemas retain one response digest field.
For a staged provider-only translation this is the digest of the canonical
ordered tuple of raw batch responses; the batch count and individual response
digests are not yet durable metadata. They also do not describe manual/import
evidence, reviewer identity, or an applied mixture assembled from unrelated
provider and curated batches. Therefore
`--save-as` and `--in-place` currently fail closed for curated or mixed
catalogs and for imported provider catalogs whose multiple responses were not
produced by this planner's one frozen exactly-once execution. Those catalogs
remain useful same-UID representations. Applying them to a Context later
requires a new checkpoint schema rather than fabricating provider evidence.

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

Before contacting the provider or reusing a catalog for `--save-as`, the
destination name and current storage availability are checked. Creation
rechecks both absence and the source name/UID/digest while holding the source
and destination cooperative write locks, so neither a concurrent owner nor a
stale source frame is published. A source change before this boundary leaves
no destination. The baseline save and its checkpoint are one atomic store
operation. The final destination save uses the baseline digest as an
optimistic-concurrency compare-and-swap.

The source is reloaded and compared with the exact catalog-derived plan before
derivation and again before switching. Any source-frame or current-Context
change prevents the final switch and leaves the source untouched. Once a
baseline Context has been published, it is not automatically deleted during
error cleanup: another process could already have switched to, embedded, or
referenced it. A later failure instead preserves the visible baseline or
completed destination for manual inspection.

`--in-place` retains the historical behavior for an intentionally bilingual
Context: it inserts a fresh-UID translated sibling immediately after every
selected source and writes its translation checkpoint. It does not merely
update the catalog and cannot be combined with `--save-as`.

## Why this is not `impact`

An impact artifact answers what a proposed state-changing operation would do
and exists to support review before a separate application decision. The
translated catalog rendering is itself the requested read result. Persisting it
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
ChatGPT Codex allowance when no exact catalog is reused or when `--refresh` is
requested. Query-only source material is neither loaded nor sent. The
translated text is persisted locally and should be treated with the same
sensitivity and retention expectations as its source content, not as an
ephemeral terminal preview.

Translation catalogs are owned by the source Context lifecycle. Cooperative source
Context deletion removes its catalogs while holding the same
lifecycle boundary, so translated content does not survive as an
undiscoverable orphan. A stale replacement removes the superseded payload
only after the new catalog is durable. Failure before atomic publication
retains the prior payload. A provider refresh does not remove a curated
payload; an explicit `--reset` removes only the selected curated layer.

Concealed study sources use a separate QuerySource-v2 representation with
stable entry UIDs, canonical English, and optional language variants. This is
not an exception that lets `mem translate` open query-only content. The query
command selects the concealed source language explicitly inside the query
boundary; ordinary translate, list, show, find, and export operations still
cannot read it.

Catalogs are not copied merely because a Context is embedded or referenced,
and deleting one must not touch the source Memories or a separately
created Context. A destination owns its fresh Memories and checkpoint evidence
independently; later catalog refresh or deletion cannot
rewrite that history.

This research provider is not a production security boundary; use only study
data approved for that provider. The instruction to treat the semantic target
and Memory content as data is a behavioral prompt boundary, not a proof of
prompt-injection isolation. Strict JSON output validation proves the shape of
what is accepted locally, but it does not prove what the provider did while
producing it; a read-only sandbox is not confidentiality isolation. A
production implementation should use a tool-less translation endpoint with
explicit access and retention policy.

## Implementation history and pre-release cleanup

The first implementation inserted translated siblings into the current
Context. A live 54-Memory Korean-to-English pilot proved the provider,
persistence, and lineage plumbing, but produced a difficult 108-item
bilingual list and allowed a later whole-Context run to translate earlier
translations. The implementation next made a fresh, automatically named
derived Context the default. That avoided the bilingual list, established the
version-2 baseline/provenance model, and preserved the source, but still
created durable identity and changed navigation for a read-oriented request.

The persisted UID-less catalog became the default because it keeps the useful
provider result and exact source binding without enlarging the Memory graph.
The current catalog adds person-controlled text and review state without changing
that identity decision. Because the prototype has not been released, the
earlier provider-only scoped-view model, its files, compatibility aliases, and
lazy migration/CAS branches were removed. Supporting two models would obscure
the actual domain concept without protecting deployed data.

The two earlier Context write behaviors remain explicit as `--in-place` and
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
- One saved catalog covers one exact semantic target for one direct Context;
  it is a same-UID representation registry, not a multilingual base-Memory
  schema.
- Curated or mixed catalogs cannot yet be applied to a Context until their
  checkpoint provenance contract is defined. Verifying provider text creates
  a curated layer, so its historical `PROVIDER` origin does not make it an
  untouched applicable provider batch.
- A partially translated derived Context intentionally contains more
  than one language.
- `mem merge` remains a structural fresh-UID union. Merging a translated
  Context into its source deliberately creates a bilingual
  Context; same-UID catalogs do not participate.
- Semantic targets are interpreted by the provider but reused only by their
  exact trimmed, case-sensitive strings. They do not claim language detection,
  fuzzy equivalence, or BCP 47 canonicalization.
- A translation target does not select the authoring, analysis, explanation,
  or interface language for Mem as a whole. That broader multilingual policy
  remains the deferred research TODO in
  [`multilingual-memory-and-explanation-language-design-rationale.md`](multilingual-memory-and-explanation-language-design-rationale.md).
- Translate's catalog publication, Context creation/save, final
  state-switch, and Context deletion paths use cooperative locks. Unsupported
  direct JSON edits do not participate in those guarantees.
