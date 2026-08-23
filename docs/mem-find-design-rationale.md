# `mem find` design rationale

## Decision

`mem find` uses the same temporary, ChatGPT-authenticated Codex runner as
`mem query`. Its initial ranking call does not ask the model to answer the
user's query: the model may select only opaque candidate IDs. memcommit
validates those IDs and renders the corresponding local Information objects
itself. The command renders static grouped results and exits in both TTY and
non-TTY execution.

This separation keeps the model in the role of semantic ranker:

```text
visible local items
→ short per-run candidate IDs
→ temporary Codex ranking
→ strict ID validation
→ canonical local rendering
```

Model-generated content, names, explanations, and replacement text are never
accepted as find results. The retained compatibility controller can still be
tested independently, but it is no longer reachable from ordinary `mem find`.

When no candidate materially satisfies the query, the same ranking completion
may return a separate related tier. The CLI keeps the primary count at zero,
labels the fallback as a broader search, and renders only canonical local
items. Related items aid discovery; they are not evidence that the original
query was satisfied.

## CLI contract

```bash
mem find "accessible entrance during construction"
mem find "parking changes" --context facilities-reference
mem find "parking changes" --limit 5
mem find "parking changes" --direct
```

The default search frame contains the selected Context, every materialized
ordinary or effectively READ-granted Context whose canonical public name
begins with `SELECTED/`, and every explicitly embedded Context reachable from
any of those roots. The unified readable Context catalog is frozen once for
the invocation, while every granted node retains its exact authority binding.
Grant attachment authorizes the view but does not become a namespace edge. A
namespace descendant
that is also explicitly embedded is visited once by Context UID, and no
missing prefix is synthesized as a Context. `--direct` searches only direct
items in the selected Context and excludes both namespace descendants and
embedded Contexts.

This scope makes Find agree with the hierarchy a person can inspect through
`mem ls -R`. In particular, an intentionally empty topology root such as
`task-3` can search materialized descendants such as
`task-3/local/personal-memory` without requiring the import process to persist a
redundant embed solely for Find. The rejected alternative was to repair only
Study Profile imports with synthetic embeds: that would leave the same empty
result for ordinary namespaced Contexts and would conflate lexical navigation
with persisted composition differently in each importer.

The broader default is also a provider-disclosure boundary. Invoking Find on
a namespace root may send ordinary and READ-granted Memory content from that
entire materialized public subtree, plus its explicit embeds, to the ranking
provider. A person who wants
the former narrow scope can use `--direct`. Query-only sources remain outside
the ordinary catalog and are never opened; only a QueryContextRef's public name
can become a candidate.

`--context` selects a search root without changing the active Context.
`--limit` accepts values from 1 through 20 and defaults to 5.

The first ranking remains global. If a recursive result fills its bounded
limit from only a subset of the root's canonical first-level namespace
branches, Find performs one bounded supplemental ranking over the omitted
branches. Only material primary matches from that second ranking may replace
up to three tail results, with at least half of a small result set retained
from the global ranking. This preserves baseline/modification or other sibling
coverage without forcing an irrelevant branch into the result. Artifacts and
direct root items do not create synthetic namespace branches, `--direct`
never performs the supplemental pass, and the total visible count still obeys
`--limit`.

One-shot `mem find QUERY` is read-only. It does not save the query, matches, a
Memory, or a checkpoint, and it prints the same grouped static result rows in
TTY and non-TTY execution before exiting. Operand-free interactive Find keeps
search and selection process-local by default, but offers one explicit checked
result Save As boundary: `COPY` creates independent Memories in a new
local Context, while `REFERENCE` creates the same live pointers as
`mem reference`. Neither changes Source or the current Context. The detailed
selection, freshness, authority, and require-new rules are recorded in
`mem-find-search-workbench-design-rationale.md`.

Find does not open a composer, accept a refinement turn, synthesize an answer,
or print a dialogue-closed message. A person can run another `mem find` for a
revised query or use an explicit `mem show` for detail. This keeps Find as a
retrieval-and-explicit-curation command without retaining a full-screen
application merely to offer optional follow-up dialogue.

The grouped stdout can be redirected or copied by the shell. It is a
presentation format, not a durable or supported structured selection for
another memcommit operation. Temporal Find retains its separate history picker
when an interactive terminal is available; removing the current-state chat
surface does not change that historical selection contract.

The CLI groups results by their primary owning Context instead of repeating
the Context name on every item. Context groups appear in the order of their
first ranked result, and results within a group retain their relative model
order. This presentation deliberately gathers interleaved results from the
same Context, so the rendered order across different Contexts is group-oriented
rather than one flat global ranking. Memory content begins on the same line as
its type and UID; later content lines align beneath the first.

Primary and related relevance are deliberately separate from `--direct`.
`--direct` controls which Contexts enter the candidate frame; `PRIMARY MATCH`
describes relevance to the query. When the primary tier is empty and a
defensible fallback exists, non-interactive output first prints
`(no primary matches)`, then a `RELATED RESULTS` section naming the original
query with no matches and the provider's bounded broader query. Rows remain
labeled `related`, and a final disclaimer after all rows makes clear that they
may not satisfy the original query. If neither tier has results, the established
`(no matching items)` output remains.

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
visits through cycles, diamond-shaped graphs, or a Context reached through
both a namespace root and an explicit embed.

### QueryContextRef

Only the public query-only Context name and containing Context name are sent
for ranking. The provider key, target source UID, hidden path, and concealed
source content are not sent or loaded. A matching result prints the public
name and a `mem query` usage hint.

## Logical identity and provenance

Per-run candidate IDs such as `c000001` avoid ambiguity when the same Memory
UID exists in multiple legacy or independently imported Contexts.

Logical deduplication uses:

- owned Memory: owning Context UID plus Memory UID;
- resolved MemoryRef: target Context UID plus target Memory UID;
- QueryContextRef: provider key plus target source UID.

Branch Contexts and their direct Memories now both have fresh occurrence UIDs,
so independently editable copies remain distinct candidates while their
ancestry stays in checkpoint lineage. Repeated occurrences of one logical
candidate retain their visible Context names as provenance.

## Retained compatibility controller

The sections below document the no-longer-launched chat controller so its
security boundaries remain reviewable while compatibility code and focused
tests still exist. They are not part of the current CLI interaction contract.

### Same-frame follow-up refinement

A natural-language follow-up that supplies a concrete new topic, keywords,
constraints, or a broader or narrower description returns a strict `REFINE`
plan with one standalone query. This includes a concrete follow-up after an
initial zero-result search; for example, “related to health, healthcare, or
medicine” is a search refinement rather than an ambiguous request that needs a
clarifying question.

The host sends that query through the ordinary ranking contract again, using
the same candidate frame frozen when the interactive view opened and the same
`--limit`. It validates returned candidate IDs locally, replaces the visible
results and their process-local `mN` aliases, updates the displayed query, and
resets the process-local kept count. It does not enumerate or load a new
Context, expand to other Contexts, mutate storage, or create a checkpoint.
Failure leaves the prior committed query and results visible through the
shell's ordinary failed-turn receipt.

This extra ranking completion sends the same already-disclosed ordinary
candidate projections to the provider again. Query-only candidates continue to
expose only their public names and labels. The design deliberately rejects
using a follow-up phrase as answer text or letting the intent provider return
results directly: the ranking response must still pass the existing opaque-ID
allowlist validation.

## Related-result fallback

The ranker returns one of three locally enforced states:

1. one or more primary matches, with no related query or related matches;
2. no primary matches plus one nonblank broader query and one or more related
   matches; or
3. neither primary nor defensible related matches.

It cannot mix tiers. Related candidates must come from the same frozen
candidate frame, use the same opaque-ID allowlist, and are limited to the
smaller of the requested result limit and five. They may share a broader topic,
workflow, or domain, but the prompt explicitly says they do not satisfy the
original query and must not be forced merely to avoid an empty screen. The
broader query is provider-authored presentation text, bounded to 2,000
characters and terminal-escaped; it is not executed automatically.

Interactive related rows retain local `mN` aliases so the person can inspect
one through the proven read-only `SHOW_RESULT` path. They may also submit a
`REFINE` turn that reranks the frame and can promote items into a new primary
tier. `ANSWER` is absent from the allowed plan schema while only related rows
are visible, and the controller independently refuses answer synthesis from a
related tier. This prevents a clinic, medication, or sleep Memory shown near a
health-insurance query from becoming evidence about insurance.

## Evidence-backed interactive answers

An ordinary follow-up question uses two isolated provider completions around
host-side evidence collection:

```text
user follow-up
→ strict ASK / REFINE(query) / ANSWER(scope) / SHOW_RESULT plan
→ local scope collection
→ strict three-part synthesis using temporary aliases
→ host-owned citation numbering and reference rendering
```

The initial candidate corpus and visible primary matches are frozen when the
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
Memory projection below a `References` heading as one logical
`[N] content — UID prefix, Context alias` row. Reusing an alias reuses its
number, and uncited candidates are not reproduced. Every row repeats its exact
Context because one answer may cite different Sources; adjacent rows have no
blank separator. Generated sentences cannot include numeric citation markers
or line breaks, and stored content line breaks are folded so content cannot
imitate a sibling citation or `References` heading. Evidence kind remains in
the typed model even though the compact terminal row omits it.

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
  ],
  "related_query": "",
  "related_matches": []
}
```

Or, only when the primary array is empty:

```json
{
  "matches": [],
  "related_query": "health and healthcare memories",
  "related_matches": [
    {"candidate_id": "c000014"}
  ]
}
```

The schema enumerates candidate IDs created for that invocation. Local
validation additionally requires:

- exactly the three documented top-level fields;
- a primary array no longer than the requested limit and a related array no
  longer than the smaller of that limit and five;
- records containing only one string `candidate_id`;
- exact membership in the local candidate allowlist;
- no related query or related records when a primary match exists; and
- a nonblank bounded related query exactly when related records exist.

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
  "query": "",
  "selector": "",
  "scope": "CONTEXT"
}
```

`ASK` and `SHOW_RESULT` require `scope: "NONE"`; `SHOW_RESULT` may select only
an enumerated visible alias. `REFINE` requires a nonblank `query`, empty
`question` and `selector`, and `scope: "CONTEXT"`. `ANSWER` has no answer text
at this stage and may select only `CONTEXT` or `ALL_CONTEXTS`. With no visible
results, only `ASK` and `REFINE` are valid. With related results but no primary
match, `SHOW_RESULT` is additionally valid, while `ANSWER` remains unavailable.

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
the user's ChatGPT Codex allowance. A `REFINE` turn consumes an intent
completion followed by another ranking completion over that same frozen
candidate content. On an ordinary answer turn, all visible and same-frame
remainder projections are also sent to the synthesis completion.
After an `ALL_CONTEXTS` plan receives the separate exact confirmation, direct
ordinary content collected from other stored Contexts is sent as well.
Query-only evidence remains limited to its public name and label; its concealed
source is never loaded by Find.

As with `mem query`, prompt instructions and a read-only sandbox are not a
production security boundary: the Codex process retains a tool surface and may
be able to read host files. Use only approved study data. A production
implementation should use a tool-less, access-controlled ranking service.

The ranking path keeps each provider payload within the shared
1,000,000-character effective provider capacity.
When the frozen ordinary corpus exceeds that boundary, Find preserves Context
groups where they fit, ranks every batch, and globally reranks the validated
shortlist. One oversized candidate and an oversized final shortlist still fail
without truncation. Small corpora retain one provider call. Temporal Find
remains one-shot until independently planned subject/anchor relations have an
explicit reconciliation contract. Follow-up synthesis uses the same shared
capacity. If explicitly requested other-Context evidence causes that ceiling
to be exceeded, Find retries with the frozen visible and same-frame evidence
and reports the wider check as unavailable instead of sampling an arbitrary
subset. If the same-frame payload alone exceeds the ceiling, the turn currently
fails. The common planning and coverage contract is recorded in
`semantic-execution-planning-design-rationale.md`.
