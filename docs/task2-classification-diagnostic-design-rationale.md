# Task 2 oracle-group classification diagnostic

Task 2 relation discovery combines two different questions: whether a provider
recovers the same 138 reviewed groups from 150 versus 150 Memories, and whether
it assigns the same semantic relationship after a group has been found. A
single end-to-end score cannot identify which stage failed. The diagnostic
therefore supplies the reviewed group structure but withholds every reviewed
band, pair ID, and fixture ID.

The provider returns only two bounded evidence fields for every opaque group:

- `overlap`: `SAME_ADVICE`, `SAME_PRINCIPLE`, or `DIFFERENT_ADVICE`;
- `coordination`: `JOINT`, `CONTEXT_CHOICE`, or `INCOMPATIBLE`.

The host projects this evidence deterministically. For `JOINT`, the three
overlap values map respectively to `Near Duplicate`, `Same-Principle Variant`,
and `Compatible Complement`. `CONTEXT_CHOICE` maps to
`Context-Dependent Variant`, and `INCOMPATIBLE` maps to `Conflict`. This keeps
the provider from merely echoing fixture-native labels and makes the semantic
decision inspectable in the retained raw response.

There is an unavoidable evidence ambiguity: the reviewed sidecar records one
final band, not independent overlap and coordination annotations. In
particular, a contextual variant or conflict does not establish which overlap
value a reviewer would have chosen. The projection is therefore intentionally
many-to-one when coordination is not `JOINT`. Scores judge only the projected
band against reviewed Gold, retain the evidence distribution for inspection,
and explicitly report that evidence-axis Gold is unavailable. A canonical
evidence witness used by tests is a replay aid, not a newly invented Gold
label.

Every selected opaque group ID must appear exactly once. The host rejects an
unknown, omitted, or repeated ID and never fills a missing result from Gold or
another provider. Group and Memory aliases are independently salted and input
order is deterministic but detached from sidecar order. Campaign ledgers retain
the raw response; prompt, schema, response, corpus, input, alias-map, and
group-map digests; and separate connection, corpus, input, prompt, completion,
validation, scoring, campaign, and total durations.

This is a read-only evaluation diagnostic. Supplying reviewed structures is an
oracle intervention for failure localization, not evidence that a provider can
discover those structures and not a production Compare or Meld behavior.
