# `mem find` design rationale

## Decision

`mem find` uses the same temporary, ChatGPT-authenticated Codex runner as
`mem query`. Its initial ranking call does not ask the model to answer the
user's query: the model may select only opaque candidate IDs. memcommit
validates those IDs and renders the corresponding local Information objects
itself. In an interactive TTY, a separate staged follow-up may answer an
ordinary question from the visible results, the remainder of the same frozen
search frame, and—only when explicitly requested—other stored Contexts.

This separation keeps the model in the role of semantic ranker:

```text
visible local items
→ short per-run candidate IDs
→ temporary Codex ranking
→ strict ID validation
→ canonical local rendering
```

Model-generated content, names, explanations, and replacement text are never
accepted as find results. A generated follow-up answer is dialogue, not a
result, and carries locally validated scope aliases that the host turns into
numbered references to local source contents.

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
view keeps one full-screen Application alive, assigns local result aliases,
and accepts repeated natural-language turns. A controller turn runs in the
background while that same view displays a busy state, then applies the
completed state in place rather than returning to the terminal between turns.
The view supports two read-only outcomes: answer an ordinary question from
visible and same-frame content, optionally extend that answer to explicitly
requested other Contexts, or inspect one visible result through an allowlisted,
explicit-Context `mem show` command. Generated answers carry validated
provenance and a host-rendered reference list. The show command is constructed
and executed locally; neither answer provider turn receives durable UID or
command authority.

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

## Evidence-backed interactive answers

An ordinary follow-up question uses two isolated provider completions around
host-side evidence collection:

```text
user follow-up
→ strict ASK / ANSWER(scope) / SHOW_RESULT plan
→ local scope collection
→ strict three-part synthesis using temporary aliases
→ host-owned citation numbering and reference rendering
```

The initial candidate corpus and visible matches are frozen when the
interactive view opens. `ANSWER(CONTEXT)` uses:

- `mN` for the visible ranked results; and
- `cN` for every other logical candidate in that same frozen search frame.

Visible candidates are removed by logical identity, so a visible MemoryRef and
its directly encountered target do not reappear as separate same-Context
evidence. The remainder is not a second semantic ranking; it is the complete
locally visible remainder supplied to the bounded synthesis step.

`ANSWER(ALL_CONTEXTS)` additionally reads stored Context records directly,
excludes Contexts and logical candidates already in the selected frame,
resolves MemoryRefs only against that direct snapshot, deduplicates the
remainder, and projects it as `xN`. This wider read is triggered only when the
person explicitly asks for other or all Contexts. It is read-only but expands
the content sent to the provider, so it is not silently inferred from an
ordinary question. The intent provider must select `ALL_CONTEXTS`, and a
separate visible host confirmation must then receive the exact token
`confirm other contexts`. Before that second turn, no outside content is
collected or transmitted. `cancel other contexts` clears the pending request,
and every other reply leaves it pending. This structured opt-in prevents an
intent misclassification, quoted phrase, hypothetical question, or
result-content prompt injection from becoming wider disclosure.

The synthesis response has one text and one alias list for each scope. The
visible sentence must cite at least one `mN`; each alias must belong to its
own scope. The host then assigns `[1]`, `[2]`, and later numbers by first use,
places them after the supporting sentence, and prints the actual referenced
Memory projection below a `References` heading with its Context and local
identity metadata. Reusing an alias reuses its number, and uncited candidates
are not reproduced. Generated sentences cannot include numeric citation
markers or line breaks, and every source-content line is indented beneath its
host-owned metadata so stored text cannot imitate the reference structure.

The prompt requests exactly three natural sentences rather than a table:
visible results, same-frame remainder, then other Contexts. A completed scan
with no support says that no additional evidence was found, not that none
exists. If other Contexts were not requested, the third sentence says they
were not checked. Partial enumeration or a corpus ceiling is reported as an
incomplete check rather than an empty result.

Source-free scope prose is not trusted as an answer. For an empty same-frame
selection, an empty completed or partial outside selection, `NOT_REQUESTED`,
and `UNAVAILABLE`, the host substitutes a localized factual status sentence.
This prevents generated text with no provenance from claiming that an
unchecked scope contains a date or other fact.

The initial frame is stable for the interactive process. The wider scan is not
a store-wide atomic snapshot: Contexts can change between name enumeration and
direct loads. Consequently, it supports only a statement about evidence found
in that scan, never a strong global non-existence claim.

Query-only items retain the same privacy boundary in all three scopes. Only
their public name and `query-only` label may be synthesized or referenced;
hidden source content is never opened by Find. Local validation proves source
identity and scope membership, but natural-language entailment and the
grammatical one-sentence shape of each text field remain prompt-level
constraints in this prototype.

## Initial ranking response

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

## Interactive response schemas

The intent completion returns only:

```json
{
  "kind": "ANSWER",
  "understanding": "The user is asking when the closure ends.",
  "question": "",
  "selector": "",
  "scope": "CONTEXT"
}
```

`ASK` and `SHOW_RESULT` require `scope: "NONE"`; `SHOW_RESULT` may select only
an enumerated visible alias. `ANSWER` has no answer text at this stage and may
select only `CONTEXT` or `ALL_CONTEXTS`.

The synthesis completion then returns only:

```json
{
  "visible_text": "The visible results establish the closure.",
  "visible_sources": ["m1"],
  "context_text": "The same frame adds a date range.",
  "context_sources": ["c2"],
  "outside_text": "Other Contexts were not checked.",
  "outside_sources": []
}
```

Each source list has a scope-specific alias allowlist. Unknown, duplicate, and
cross-scope aliases are rejected locally. Durable UIDs appear in neither
provider payload; they remain host-side and only an eight-character prefix is
rendered in the final reference metadata.

## Provider and privacy

The Codex runner requires `Logged in using ChatGPT` and rejects API-key or
access-token environment overrides. It runs ephemerally in an empty temporary
directory, receives the prompt through standard input, and exposes no inherited
environment variables to model-proposed shell commands.

Ordinary searchable Memory content is sent to OpenAI for ranking and consumes
the user's ChatGPT Codex allowance. On an ordinary answer turn, all visible and
same-frame remainder projections are also sent to the synthesis completion.
After an `ALL_CONTEXTS` plan receives the separate exact confirmation, direct
ordinary content collected from other stored Contexts is sent as well.
Query-only evidence remains limited to its public name and label; its concealed
source is never loaded by Find.

As with `mem query`, prompt instructions and a read-only sandbox are not a
production security boundary: the Codex process retains a tool surface and may
be able to read host files. Use only approved study data. A production
implementation should use a tool-less, access-controlled ranking service.

The initial ranking call rejects a serialized search corpus larger than
200,000 characters. The follow-up synthesis has its own 220,000-character
scope ceiling. If explicitly requested other-Context evidence causes that
ceiling to be exceeded, Find retries with the frozen visible and same-frame
evidence and reports the wider check as unavailable instead of sampling an
arbitrary subset. If the same-frame payload alone exceeds the ceiling, the
turn currently fails. A later version can add explicit batching and final
reranking without changing the candidate-validation or citation contract.
