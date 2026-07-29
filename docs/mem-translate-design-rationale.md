# `mem translate` design rationale

## Status and decision

`mem translate` creates new translated `Memory` occurrences inside the current
Context while retaining every source `Memory` byte-for-byte. The default scope
is every directly owned Memory; one UID or unique UID prefix narrows the
operation to one directly owned Memory.

```bash
mem translate
mem translate --to French
mem translate ac827aaa --to en-CA
mem translate --to English --yes
```

`--to` defaults to `English`. Version 1 accepts a short printable language name
or tag as provider data; it does not claim to validate or canonicalize BCP 47
tags. `--yes` skips the apply confirmation, but not validation or stale-state
checks.

The motivating study scenario is a Context containing 54 Korean Memories that
also needs English occurrences. On 2026-07-29,
`mem translate --to English --yes` completed one live plumbing pilot on
`temp/task-1-atomized`: it created 54 paired results, increased the Context
from 54 to 108 Memories, and added one `translate` checkpoint. A sampled result
was then verified with both `mem show` and a `TRANSLATED / RECORDED`
`mem trace`.

That run establishes end-to-end execution, not automated translation quality.
The implemented tests validate operation, privacy, persistence, concurrency,
provenance, and response-contract behavior with controlled fixtures; human
assessment of terminology and translation quality remains separate.

## Same-Context sibling copies

Each result receives a fresh Memory UID and is inserted immediately after its
source:

```text
source A
translated A
source B
translated B
```

Sources are never edited or removed. Equal source contents remain distinct
occurrences and are translated separately. A valid translation that is
byte-identical to its source, such as a proper name or technical identifier,
still becomes a new occurrence because the operation records that a
translation was requested and accepted.

This same-Context design follows the motivating requirement to add an English
version to the existing memory collection. A required `--save-as` destination
was rejected for this version because it would create a separate version of
the complete Context instead of adding translations “within” the selected
Context. In-place replacement was also rejected because it would destroy the
source-language evidence.

## Data and graph boundary

Only directly owned `Memory` records are translation candidates.

- `MemoryRef` targets are not opened, sent, copied, or translated.
- `QueryContextRef` source content remains opaque and is never opened. Its
  public pointer record is preserved.
- Embedded Contexts are not traversed. Their pointer records are preserved.
- Selecting a reference, query-only Context, or embedded Context as the
  positional selector is an error.

The operation therefore adds sibling nodes to one Context; it does not
recursively produce a translated Context graph or hierarchy.

The base `Memory` schema intentionally remains `uid + content`. Adding
operation-specific `language` or `translation_of` fields would silently make a
generic atomic Memory type aware of one semantic operation. Instead, the
automatic checkpoint stores a validated mapping from each source UID to each
new result UID, the target language, content digests, operation UID, source
Context fingerprint, scope, and provider-response digest.

`mem trace` validates that mapping against adjacent snapshots, including the
recorded full-Context digest, every source/result content digest, result
placement, and preservation of all non-result pointer metadata. A valid
mapping produces a `TRANSLATED / RECORDED` event connecting the unchanged
source and new result. This records the derivation without asserting that the
model's translation is linguistically correct. If the metadata does not match
the snapshots, trace falls back to ordinary snapshot reconstruction and
reports a warning.

## Provider contract

Translation uses the temporary, ChatGPT-authenticated Codex provider used by
newer semantic operations, not the legacy configured `LLMClient`. One
invocation receives:

- a printable target-language label;
- opaque per-call candidate IDs such as `m000001`;
- the exact content of selected directly owned Memories.

Real Context and Memory UIDs are not sent. The prompt treats all payload fields
as data and asks for translation only: no answering, summarization,
normalization, correction, ambiguity resolution, or fact addition. Names,
numbers, dates, negation, modality, uncertainty, relationships, Markdown, and
line breaks should be preserved as far as the target language permits.

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
validation additionally rejects duplicate JSON keys, extra fields, missing,
duplicate, or unknown candidates, blank or non-string content, oversized
input/output, and terminal control characters. Provider order is ignored;
results are rebound to sources in canonical Context order. Any failure occurs
before a result UID is created.

The one-call prototype caps its serialized input at 200,000 characters. A
Task-sized aggregate can contain dozens of Memories, so only this operation's
Codex timeout is raised to 300 seconds. It does not silently batch or retry:
doing so would require a separately specified consistency and partial-failure
contract.

## Preview, application, and concurrency

The validated source and translated text are displayed before mutation.
Confirmation defaults to No. A rejected preview creates no Memory and no
checkpoint. `--yes` is the explicit non-interactive apply path.

The provider call and review can take minutes. The command initially loads the
Context through the non-resolving direct path, then reloads a save-safe Context
immediately before mutation. It requires:

- the same current Context name and Context UID;
- an exact match of the complete ordered direct serialized record, including
  pointer metadata;
- an exact source UID and content match for every proposal.

Any concurrent direct edit, addition, removal, reorder, pointer change, or
delete-and-recreate observed at revalidation makes the plan stale and aborts
the whole operation. The final save also acquires the Context's cooperative
process lock, rereads the disk record under that lock, and compares it with the
plan's expected digest before writing a checkpoint or Context file. Ordinary
Contexts loaded by `MemoryStore` retain a non-serialized base digest, and
ordinary `MemoryStore.save` calls enforce that digest under the same lock.
This also prevents an older ordinary writer from erasing a translation after
the translation has completed. Digests use the canonical logical direct
record, so supported legacy files without an explicit `order` field compare
equal to their normalized in-memory form.

All result UIDs are generated locally only after stale validation. The Context
and one automatic `translate` checkpoint are then persisted through the
store's atomic save path. Provider failure, invalid output, refusal, or stale
state changes nothing.

## Privacy and trust boundary

Ordinary selected Memory content is sent to OpenAI and consumes the user's
ChatGPT Codex allowance. Query-only source material is neither loaded nor sent.
As with other subscription-backed prototype operations, a prompt and read-only
sandbox are not a production security boundary: the isolated Codex process
still has a tool-capable runtime. Use only study data approved for that
provider. A production version should use a tool-less translation endpoint
with explicit access control and retention policy.

## Intentional limitations

- A translated result is an ordinary Memory in the live Context. `mem ls`
  cannot display its language or source relation without consulting history.
- Re-running whole-Context translation can translate earlier translation
  results and create additional copies. Automatic deduplication was rejected:
  the generic Memory schema has no stable live translation identity, and text
  equality is not proof of occurrence equivalence.
- Translation quality, dialect choice, terminology consistency, and semantic
  equivalence are not mechanically proven by strict JSON validation.
- Source-language detection is delegated to the provider.
- Recursive Context-graph translation, cross-Context reverse lineage, cached
  previews, provider retries, and automatic destination Contexts are outside
  version 1.
- The save lock coordinates `MemoryStore.save` callers. Direct external edits
  to Context JSON and deletion code paths do not participate in that lock and
  remain unsupported concurrent mutations.
