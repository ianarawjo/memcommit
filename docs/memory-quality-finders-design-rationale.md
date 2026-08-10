# Memory quality finders

This note specifies the implemented command and data contract. For the
reconstructed discussion that led to the labels, the rejected alternatives,
the ambiguity `3 × 3` matrix, the relationship to the earlier `fit` idea, and
the limits of the ordinary-reading judge, see
[`memory-quality-judgment-theory-and-decision-history.md`](memory-quality-judgment-theory-and-decision-history.md).

## Decision

The first quality-analysis surface consists of three explicit, read-only
commands:

```text
mem find-duplicates
mem find-ambiguities
mem find-conflicts
```

The names are intentionally parallel and plural. Each command can return zero
or more findings, and the `find-` prefix promises inspection rather than
mutation. Shorter alternatives such as `duplicates`, `ambiguities`,
`conflicts`, or `dupes` save a few characters but do not state whether the
command lists, changes, or resolves anything. The existing `mem find <query>`
remains a separate operation for ranking Memories relevant to a user-supplied
query; it is not a quality or relationship judge.

These three commands are the smallest useful analysis layer. `reconcile`,
`dedup`, editing, and deletion are later consumers or mutation stages. A
finder never chooses a winner, rewrites a Memory, removes a UID, or claims that
an identified problem has been resolved.

The implemented [`mem review ambiguities`](memory-review-shell-design-rationale.md)
is a separate consumer of an ambiguity report. It persists selected readings
and one freeform reviewer annotation, but it does not change the finder's
read-only/mutation contract or apply those annotations to Memories.

## Units of judgment

The judgments and their public evidence deliberately have different arities:

| Command | Discovery input and result unit | Primary labels |
|---|---|---|
| `find-duplicates` | whole direct Context; positive evidence links identify unordered Memory pairs | emitted: `EXACT`, `SURFACE_EQUIVALENT`, `SEMANTIC_EQUIVALENT`; rejection boundaries: `OVERLAP`, `UNKNOWN`, `DISTINCT` |
| `find-ambiguities` | one Memory interpreted inside its Context | `SINGLE`, `DOMINANT`, `COMPETING` crossed with `NONE`, `HELPFUL`, `REQUIRED` |
| `find-conflicts` | one unordered pair of Memories | `YES`, `MAY`, `NO` |

Consequently, a Context with `n` direct Memories has `n` unary ambiguity
targets and admits up to `n(n-1)/2` possible binary relations. That
cardinality does not prescribe the execution strategy. `find-conflicts`
currently names every unordered pair as an explicit target.
`find-duplicates` instead discovers equivalence components from a
whole-Context input and emits only a linear set of positive pair-shaped
evidence links. It never materializes the candidate-pair space.

`find-ambiguities` uses “ambiguity” as the public quality category while
preserving two independent judgments. `interpretation` describes whether
ordinary reading yields one reading, a dominant reading plus alternatives, or
several competing readings. `clarification` describes whether more information
is unnecessary, useful, or required for safe use. These axes must remain
separate: a sentence can have one reading but still omit contact information
required to carry out its instruction, and intentional wordplay can have
competing readings without needing clarification.

For conflict, `MAY` is a semantic result, not model confidence. It means that
ordinary readings supported by the current Context include both a conflicting
and a jointly explainable interpretation. A missing entrance, audience, time,
or other scope coordinate is a typical cause. The judge returns `YES` when all
materially ordinary scope-aligned readings conflict, `NO` when all such
readings are jointly explainable, and `MAY` only when both outcomes occur
among those readings.

Duplicate relations likewise preserve boundaries that a removal stage needs:

- `EXACT` means the two stored content strings are identical.
- `SURFACE_EQUIVALENT` means conservative comparison normalization yields the
  same key without changing stored content.
- `SEMANTIC_EQUIVALENT` means either Memory can replace the other without
  information loss under the same scope.
- `OVERLAP` means the pair shares a claim but at least one Memory contains
  unique information.
- `UNKNOWN` means missing scope prevents an equivalence decision.
- `DISTINCT` means the Memories are not substitutable.

`OVERLAP`, `UNKNOWN`, and `DISTINCT` are calibration and rejection boundaries,
not positive `find-duplicates` output. In particular, related information and
missing scope must not be presented under a command whose positive result says
that a pair is duplicate.

## Local interpretation boundary

Version 1 analyzes only Memories directly owned by the selected Context. The
whole set of those direct Memories forms the local interpretation frame for
each quality judgment. This implements the project assumption that
conflict and ambiguity are judged under ordinary reading of the knowledge
actually present in the selected Context, rather than against every imaginable
outside premise.

The initial implementation does not recursively analyze embedded Contexts,
dereference `memory_ref` values, or open query-only sources. A reference is a
view of a Memory owned elsewhere, not a second candidate. Recursive analysis
is deferred until traversal has a canonical logical identity, cycle handling,
owner-aware results, and an explicit disclosure policy.

## One-shot Context execution

When semantic targets exist, each finder makes exactly one semantic-provider
call for the selected direct Context; an empty semantic candidate set returns
locally without opening a provider session. The operations use different
target contracts:

- ambiguity sends every direct Memory once as a unary target;
- conflict sends every direct Memory plus every canonical unordered pair as an
  explicit target;
- duplicate first builds deterministic `EXACT` and `SURFACE_EQUIVALENT`
  components with hash keys, then sends one representative per component.
  The model returns disjoint `SEMANTIC_EQUIVALENT` groups of representative
  IDs. The local program converts each group into a canonical spanning tree of
  pair evidence instead of its quadratic pair clique.

Duplicate discovery has no `pairs` or `unresolved_pairs` payload. Its
representative reduction removes only equivalence already established by
local exact or conservative surface comparison; it is not a similarity
heuristic. Version 1 otherwise performs no embedding prefilter, similarity
cutoff, or multi-call batching.

The fixtures carry `ruleset_version` fields, but the current operation does
not validate, forward, or record that metadata in its provider payload or
finding report. Reproducible semantic evaluation therefore remains future
work; fixture versioning should not be mistaken for end-to-end ruleset
provenance.

This choice favors an inspectable research contract:

- conflict includes every pair explicitly, including lexically dissimilar
  statements;
- duplicate supplies every mechanically distinct representative once without
  repeating it in a quadratic pair table;
- all judgments use the same local Context frame;
- one invocation cannot combine silently different provider calls or partial
  prompt contexts;
- duplicate discovery does not depend on an undocumented retrieval heuristic.

All one-shot operations still have a finite input boundary. Quality finders use
the shared 1,000,000-character effective provider capacity and have no separate
Memory-pair count gate. Conflict still materializes every explicit pair and is
therefore ultimately bounded by the encoded provider payload rather than an
arbitrary fixed pair count. Duplicate remains linear: its keyed grouping,
representative payload, and returned spanning evidence are linear in the
number and total text of the supplied Memories.

This removes quadratic duplicate request construction; it does not make one
provider call suitable for one million Memories. A million Memory bodies
cannot fit in the current one-shot context. True million-scale semantic
discovery requires deterministic indexing plus a separately specified
candidate-generation, sharding, or batching mode whose recall and coverage
are visible. The current command never silently truncates or presents such a
partial scan as complete.

The semantic finders reuse the same temporary ChatGPT-authenticated Codex
provider as the existing `find`, `impact`, and `update` operations. They do not
introduce a second provider path or a per-finder model router. The isolated
provider ignores local model configuration and uses Codex's current
recommended model selection. This keeps the implementation consistent with the
other prototype operations, but it also means the exact model is not yet
recorded in a finding report. A reproducible evaluation harness must capture
the resolved model before comparing results across provider revisions. The
provider remains a research-prototype dependency expected to be replaced by an
MCP or internal-network provider later.

## Read-only result contract

All three commands:

- accept the current Context or an explicitly selected Context;
- validate model-returned opaque IDs against locally generated candidate IDs;
- return the affected UID or UID pair, its label, and a concise rationale;
- include an ordinary reading or a smallest useful clarifying question where
  the operation contract calls for it;
- make no Context write and create no checkpoint;
- fail closed on malformed, duplicated, or out-of-scope provider output.

For ambiguity results, proposed readings, reasons, and questions are requested
in English so the review surface has one comparison language while still
showing the original Memory unchanged. The reason connects the two ambiguity
axes to a concrete outcome: what cannot be determined for `REQUIRED`, what
would become more precise for `HELPFUL`, or why resolution is operationally
unnecessary for `NONE`. It may use multiple sentences when one uncertainty
affects several decisions. These are explanations, not structured affected
result IDs or verified counterfactual counts.

The structured result contains findings only:

- ambiguity omits `SINGLE/NONE`;
- conflict omits `NO`;
- semantic duplicate detection omits `OVERLAP`, `UNKNOWN`, and `DISTINCT`.

Ambiguity and conflict instruct the provider over explicit target lists.
Duplicate instructs it to inspect every supplied representative and discover
positive equivalence groups. In all three cases, absence is a production
result rather than proof that the model considered or discovered every
positive. Golden and held-out evaluation must measure omissions. If findings
are later persisted or passed to another operation, their envelope must also
record the ruleset and resolved provider/model.

Mechanical duplicate comparison is deterministic and remains independently
checkable. It uses keyed components and emits only enough `EXACT` and
`SURFACE_EQUIVALENT` links to connect each component. The semantic call
receives the first representative of each component once. Returned semantic
groups must be disjoint and use only those known IDs; the local program emits
one representative-to-member link per remaining group member. Thus the public
pair shape is evidence, not a pre-enumerated search target.

## Relationship to atomize, dedup, and reconcile

Atomization remains the preferred first refinement stage because a composite
Memory can hide an internal duplicate or make two partly overlapping records
look wholly equivalent. It is a prerequisite that improves the units supplied
to the finders, not a fourth quality finder and not behavior silently performed
by any `find-*` command. The finders can still inspect unatomized intake, but
their labels apply to the stored Memory boundaries they receive.

`find-duplicates` reports only positive duplicate evidence links. A future
`dedup` operation will validate their connected components, turn confirmed
equivalence into a stale-safe plan, select an existing survivor UID, check
inbound references, and create a checkpoint when the plan is applied.
`OVERLAP` and `UNKNOWN` remain negative golden boundaries and must never flow
into removal.

`find-ambiguities` and `find-conflicts` remain separately callable because one
is unary and the other pairwise, and because their labels answer different
questions. A later `reconcile` operation may consume both result sets,
identify a shared missing scope dimension, and propose the smallest
clarification or edit. Reconciliation is combined reasoning over findings; it
does not replace their detection and does not silently apply a resolution.
The shared review-shell design may later render both finding types, but visual
reuse does not merge their semantic units.

## Calibration fixtures and evaluation boundary

The initial fixtures live at:

```text
memcommit/eval/fixtures/ambiguity.json
memcommit/eval/fixtures/conflict.json
memcommit/eval/fixtures/duplicates.json
```

The ambiguity fixture covers the complete `3 × 3` cross-product of
interpretation and clarification labels. The conflict fixture holds the
entrance contrast under one shared frame so that `YES`, `MAY`, and `NO` differ
only in whether the second Memory identifies the main, unspecified, or
separate staff entrance. The duplicate fixture provides one boundary case for
each relation.

These are initial, inspectable calibration cases and golden contract
regressions. If their examples or rationales are included in the provider
prompt, scores on the same cases do not measure generalization. Independent
held-out cases, paraphrased variants, multilingual variants, adversarial scope
changes, and repeated-run stability tests must be maintained separately before
making accuracy claims. Ruleset changes should version the fixture contract
rather than silently rewriting the meaning of an existing label.

## Intentional limitations

Version 1 does not:

- prove that no duplicate, ambiguity, or conflict exists outside the selected
  direct Context;
- infer a globally correct interpretation from facts absent from that Context;
- scale past the declared one-shot payload; conflict additionally retains its
  explicit pair boundary;
- turn duplicate evidence into mutation-ready survivor groups, resolve
  conflicts, answer clarifying questions, or mutate Memories;
- apply or canonically interpret responses collected by the separate ambiguity
  review shell;
- treat `MAY` or `UNKNOWN` as provider-confidence scores;
- use calibration cases as evidence of held-out performance.
