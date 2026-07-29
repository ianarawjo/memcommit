# `mem find` design rationale

## Decision

`mem find` uses the same temporary, ChatGPT-authenticated Codex runner as
`mem query`, but it does not ask the model to answer the user's query. The
model may select only opaque candidate IDs. memcommit validates those IDs and
renders the corresponding local Information objects itself.

This separation keeps the model in the role of semantic ranker:

```text
visible local items
→ short per-run candidate IDs
→ temporary Codex ranking
→ strict ID validation
→ canonical local rendering
```

Model-generated content, names, explanations, and replacement text are never
accepted as find results.

## CLI contract

```bash
mem find "accessible entrance during construction"
mem find "parking changes" --context facilities-reference
mem find "parking changes" --limit 5
mem find "parking changes" --direct
```

The default search descends through explicitly embedded Context references.
It does not infer parent-child relationships from slash-prefixed Context
names. `--direct` searches only direct items in the selected Context.

`--context` selects a search root without changing the active Context.
`--limit` accepts values from 1 through 20 and defaults to 5.

Find is read-only. It does not save the query, matches, a Memory, or a
checkpoint. In a TTY it opens the interactive Find view after ranking. The
view assigns local result aliases, accepts repeated natural-language turns,
and currently supports one typed follow-up action: inspect a visible result
through an allowlisted, explicit-Context `mem show` command. That command is
constructed and executed locally; the turn provider receives no durable UID
or command authority.

Outside a TTY, Find retains its ordinary grouped stdout so it can be redirected
or copied by the shell. That output is a presentation format, not a durable or
supported structured selection for another memcommit operation. The
interactive transcript and aliases are likewise in-process presentation state,
not a persisted selection or resumable Find session.

The CLI groups results by their primary owning Context instead of repeating
the Context name on every item. Context groups appear in the order of their
first ranked result, and results within a group retain their relative model
order. This presentation deliberately gathers interleaved results from the
same Context, so the rendered order across different Contexts is group-oriented
rather than one flat global ranking. Memory content begins on the same line as
its type and UID; later content lines align beneath the first.

## Searchable item types

### Memory

The complete Memory content and its owning Context name are included in the
ranking payload. A returned candidate is rendered from the original Memory
object.

### MemoryRef

A resolved MemoryRef is searched using its current target content. A dangling
MemoryRef is omitted. Multiple references to the same target, and a direct
target encountered alongside its reference, are represented by one logical
candidate.

### Embedded Context

The Context object itself is not a result. Its searchable descendants are
visited recursively. Context UIDs prevent infinite traversal and repeated
visits through cycles or diamond-shaped graphs.

### QueryContextRef

Only the public query-only Context name and containing Context name are sent
for ranking. The provider key, target source UID, hidden path, and concealed
source content are not sent or loaded. A matching result prints the public
name and a `mem query` usage hint.

## Logical identity and provenance

Per-run candidate IDs such as `c000001` avoid ambiguity when the same Memory
UID exists in multiple branch Contexts.

Logical deduplication uses:

- owned Memory: owning Context UID plus Memory UID;
- resolved MemoryRef: target Context UID plus target Memory UID;
- QueryContextRef: provider key plus target source UID.

Branch Contexts have different Context UIDs, so their independently editable
copies remain distinct candidates even when a Memory UID was inherited.
Repeated occurrences of one logical candidate retain their visible Context
names as provenance.

## Structured provider response

Codex receives a JSON payload containing the natural-language query, result
limit, and visible candidates. It receives an output schema that permits only:

```json
{
  "matches": [
    {"candidate_id": "c000001"}
  ]
}
```

The schema enumerates candidate IDs created for that invocation. Local
validation additionally requires:

- exactly one top-level `matches` field;
- an array no longer than the requested limit;
- records containing only one string `candidate_id`;
- exact membership in the local candidate allowlist.

Duplicate valid IDs are collapsed while preserving model order in the validated
match sequence. The CLI then applies the Context grouping described above.
Unknown, partial, malformed, or content-bearing records fail the command
instead of being displayed.

## Provider and privacy

The Codex runner requires `Logged in using ChatGPT` and rejects API-key or
access-token environment overrides. It runs ephemerally in an empty temporary
directory, receives the prompt through standard input, and exposes no inherited
environment variables to model-proposed shell commands.

Ordinary searchable Memory content is sent to OpenAI for ranking and consumes
the user's ChatGPT Codex allowance. As with `mem query`, prompt instructions
and a read-only sandbox are not a production security boundary: the Codex
process retains a tool surface and may be able to read host files. Use only
approved study data. A production implementation should use a tool-less,
access-controlled ranking service.

The one-call prototype rejects a serialized search corpus larger than 200,000
characters. A later version can add explicit batching and final reranking
without changing the candidate-validation contract.
