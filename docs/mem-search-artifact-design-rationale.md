# Searchable activity artifacts and ordinary Query

## Problem

An applied Meld can produce correct target Memories without leaving the
selected conflict resolutions inside those Memories. A later question such as

```text
mem query "what changed when I merged advisor 1 and advisor 2?"
```

therefore cannot be answered by ranking current Memories alone. Hard-coding a
Meld dump into Query would be equally wrong: unrelated questions would receive
irrelevant operation data, and Query would acquire a different evidence model
from Find.

## Decision

Find and ordinary Query share one searchable candidate frame. It contains the
visible ordinary Memory graph plus bounded, active-Profile projections of:

- saved visible query-session questions and answers;
- saved Compare and Meld work relevant to a Context in the searched frame;
- Context checkpoints as recorded trace events; and
- validated cached rationale inferences for Memories in the frame.

The semantic ranker decides whether an artifact materially satisfies the
question. No command injects a Meld, trace, rationale, or prior session merely
because one exists. `mem find` renders selected artifacts as compact results;
interactive inspection retains their bounded detail. Ordinary `mem query
"QUESTION"` ranks the same frame and synthesizes a citation-backed answer from
primary matches only.

The original query-only form remains valid:

```text
mem query QUERY_ONLY_VIEW "QUESTION"
```

A recognized query-only selector keeps its concealed-source provider and grant
contract. An unrecognized single operand is instead a question for the Context
selected by `--context` or the current Context.

Bare `mem query` in a terminal composes the same candidate frame with the
shared Profile/Context range controls. It freezes the exact checked readable
Contexts before ranking; query-only Views remain a separate typed Source mode.

## Authority and privacy invariants

- Artifact discovery is rooted in the active Profile's stores, so Profiles do
  not share sessions, checkpoints, trace evidence, or rationale caches.
- A granted `READ` Context exposes the granted Memory projection but does not
  grant the authority Profile's private activity artifacts. Separate artifact
  sharing would require a future explicit permission.
- Checkpoint-derived trace candidates follow the same ownership boundary as
  `mem trace`: every locally owned Context may contribute its retained history,
  independent of Study task numbering, while a granted READ view never exposes
  the authority Profile's private history artifacts through Find or Query.
- Query-only source bodies never become Find candidates. Existing public
  query-only names remain name-only candidates, and the concealed Query path
  still opens source content only after its normal authorization boundary.
- Query sessions contribute only Q/A already visible to the participant. Their
  concealed source, provider prompt, and source digest are not search text.
- Meld and Compare projections exclude complete source Memory frames. They may
  include saved overview, issues, reviewed comments, target identity, and
  application receipt because those are the operation artifact the user saw or
  approved.
- Rationale search reuses only a validated current cache record. It does not
  trigger a fresh rationale inference.

## Presentation boundary

Ranking receives the bounded artifact detail needed to distinguish decisions.
The Find list shows a one-line summary. Query citations show compact evidence
excerpts and do not reproduce the complete artifact or every Memory in the
Context. Query answer synthesis also receives only primary semantic matches;
the broader same-Context expansion remains an explicit capability of the
interactive Find dialogue.

The common citation renderer also retains a typed document containing the
answer body and each numbered used Reference. Plain Find and Query output still
uses the document's stable text rendering, while Query's terminal Answer uses
the retained Reference boundaries for block navigation and focus presentation.

## Limitations

The initial operation-session adapters cover durable Compare, Meld, query
transcripts, checkpoint-derived trace events, and rationale caches. Other
workbenches can join the same `SearchArtifact` boundary later, but each needs a
purpose-built safe projection; serializing arbitrary session JSON is not an
accepted fallback. Temporal Find retains its existing specialized history
pipeline rather than mixing current artifact ranking into temporal relation
calculation.
