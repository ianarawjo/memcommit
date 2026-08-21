# Memory quality finders

This note specifies the implemented command and data contract. For the
reconstructed discussion that led to the labels, the rejected alternatives,
the ambiguity `3 × 3` matrix, the relationship to the earlier `fit` idea, and
the limits of the ordinary-reading judge, see
[`memory-quality-judgment-theory-and-decision-history.md`](memory-quality-judgment-theory-and-decision-history.md).

## Decision

The quality-analysis surface consists of four explicit read-only finders and
one applying complete-DUN operation:

```text
mem find-duplicates
mem find-redundancies
mem find-ambiguities
mem find-conflicts
mem dedun
```

`dedun` is a deliberate product term: `dup` denotes exact stored duplicates,
while `dun = dup + semantic dun`. `find-redundancies` owns the frozen
read-only complete DUN analysis and never exposes an Apply action. Dedun
deliberately reuses that same analysis and treats the invocation as immediate
Apply intent, retaining the earliest existing UID in each eligible connected
group. `find-duplicates` is a separate provider-free exact-DUP report. There is
no singular
`find-redundancy` command. The existing
`mem find <query>` is separate literal text lookup, not a quality or
relationship judge.

The implemented [`mem review ambiguities`](memory-review-shell-design-rationale.md)
is a separate consumer of an ambiguity report. It persists selected readings
and one freeform reviewer annotation, but it does not change the finder's
read-only/mutation contract or apply those annotations to Memories.

## Direct relation reports and explicit judgment workbench

Flagless and explicit Context forms use the stable one-shot report contract:

```text
mem find-redundancies --context NAME
mem dedun --context NAME
mem find-ambiguities --context NAME
mem find-conflicts --context NAME
```

In a TTY, invoking a read-only finder without flags immediately analyzes the
command-start current Context, exactly like its non-TTY route.
`find-duplicates` and `find-redundancies` are deliberately direct-only relation
reports: neither command exposes an initial selector or a process-local review
workbench. The current Context is the implicit exact Source, and a positional
Context or `--context` compatibility form supplies one other exact Source.
This preserves the useful distinction between `dup` as a deterministic exact
scan and `dun` as the complete exact-plus-semantic scan without inserting a
second approval step before either read-only report.

Ambiguity and Conflict retain an explicit `--select` capability because their
judgment review can span a deliberately composed readable frame. That screen
contains three top-to-bottom controls:

1. `TARGETS`, the common `PROFILE` plus readable Context namespace tree;
2. `SCOPE`, with `SINGLE TARGET` versus `MULTIPLE TARGETS` and `THIS CONTEXT
   ONLY` versus `INCLUDE DESCENDANTS`; and
3. `TO DO`, the exact operation-labelled Run action for the visible checked
   set.

Setup starts in `MULTIPLE TARGETS` and `THIS CONTEXT ONLY`, with the current
Context checked and marked for orientation. This keeps one-Context execution a
fast path while making comparison breadth explicit. Moving the cursor does not
change checked values. Enter or Space toggles one row; under descendant reach
it checks or clears the row's complete lexical subtree. The common range state
permits an empty multiple selection while editing, but `TO DO` rejects it
rather than inventing a fallback. `PROFILE` expands only to the frozen readable
catalog and never becomes a storage locator or persisted preference.

`SINGLE` versus `MULTIPLE` controls selected-root cardinality independently
from lexical reach. One selected root plus `INCLUDE DESCENDANTS` can therefore
produce several effective Contexts. Execution freezes the exact visible
checked set; it does not repeat a hidden descendant expansion that could
re-include an independently unchecked row. Cancellation creates no provider
connection, finding artifact, Context write, or checkpoint.

The finder kind is fixed by the command and therefore is not another setup
choice. Embedded Context edges remain excluded: descendant reach follows the
public lexical namespace only. The explicit `--context NAME` forms retain
their original exact, direct, one-Context behavior.

Dedun does not expose the multi-target selector because Apply owns
one exact Context. Its flagless route uses the current Context; `--context`
selects another exact readable Context. Eligible EXACT, SURFACE_EQUIVALENT,
and SEMANTIC_EQUIVALENT evidence is grouped; the earliest stored UID survives each
group, and the operation applies one checkpoint immediately. OVERLAP stays
unchanged. If no eligible group exists, Dedun prints a no-change receipt and
creates no checkpoint. Detailed terminal evidence is recovered later through
the checkpoint-backed `mem review dedun --receipt UID` route.

After Ambiguity or Conflict setup, every effective Context is loaded directly through the same
frozen readable catalog. Its directly owned Memories are copied into one
temporary aggregate analysis Context in visible Context order and direct
Memory order. The finder makes one provider turn over that complete aggregate
frame: Conflict can therefore report cross-Context relations, while Ambiguity
interprets each Memory using the same combined local frame.
The provider payload records the original public Context name beside every
candidate, and the local workbench preserves that owner for each evidence
source. The temporary aggregate is process-local, has a deterministic frame
identity, and is never saved or exposed as a new Context.

The validated report is projected into the common Resolution Session
presentation. Its Scope section records Context count, direct-Memory count,
target mode, and lexical reach; every selected Context is listed as a source
location. The complete report starts focused, followed by the finding Items
list and To Do. Opening an item uses the shared
`VIEWER → RESPONSES → ITEMS → TO DO` topology. Ambiguity keeps its proposed
reading choices, while Conflict keeps its exact pair and question.
Responses in this first rollout are process-local review state: they do not
alter the report, persist a new artifact, imply resolution, or mutate Memory.
Dedun does not consume process-local notes from another finder: its own
invocation accepts every eligible finding in the newly frozen exact frame and
enters its deterministic Apply boundary. Sharing the analyzer does not share
Apply authority. The individual judgment workbenches retain that compatibility
boundary. Durable
multi-session retention is instead explicit through `mem audit`, which records
all three reports, each finder ruleset, and provider/model provenance without
silently changing a one-shot `find-* --context` invocation into a stored
artifact. The older ambiguity Review singleton remains independently readable.

The one-shot `find-redundancies` report projects the evidence forest as
connected `DUN GROUP` blocks. Each Memory appears once per group in frozen
direct order: `SURVIVOR` names the deterministic earliest-UID choice and every
other member receives its own `ABSORB` row. This is the same cleanup grammar as
the applied Dedun receipt and naturally extends from two members to any larger
connected group. The group is explicitly `PROPOSED · NOT APPLIED` because Find
remains read-only. Typed `EVIDENCE` rows retain every relation and reason.
Pair-internal `LEFT`/`RIGHT` and order-only `FIRST`/`LATER` labels are not shown:
the former repeat shared members in multi-edge groups, while the latter hide
the cleanup disposition the report is meant to preview.

The provider-free exact-Duplicate report uses the same disposition grammar but
makes every member row self-contained. It prints one `SURVIVOR` row and any
number of `ABSORB` rows, each with that member's UID and complete content. For a
two-member exact group this is exactly two rows; it does not add a separate
shared-content or cleanup-map row. Repeating byte-identical content is
intentional here: the small repetition removes cross-row lookup and makes every
kept or removed identity understandable on its own. The earlier generic
`CONTENT` plus UID-only `FIRST` and `LATER` projection was not losing stored
data, but made the relationship easy to miss. Compact UIDs are resolved against
the complete group and expand past eight characters when needed, so two members
never appear to have the same visible identity.

In both reports only the disposition token is colored. `SURVIVOR` uses the
shared ADD blue as the member retained in the proposed result, while `ABSORB`
uses the shared REMOVE red as a member that would leave it. UIDs, Memory bodies,
evidence, and `PROPOSED · NOT APPLIED` remain neutral, and ANSI-free output keeps
the identical labels and ordering.

Ambiguity and Conflict deliberately reuse two existing component families
rather than creating a finder-specific full-screen grammar: common Context
targeting owns setup selection, while the common Resolution Session owns
finding inspection and response mechanics. The receipt between them is the
semantic boundary; the setup UI never calls a finder merely because a cursor
moved or a Context was checked. The direct Duplicate and Redundancy reports do
not enter either component. When more than one effective Context crosses authority domains,
the operation applies the normal `DERIVE`/`COMBINE` Grant boundary before
loading content or connecting the provider. Local Contexts need no additional
Grant authority.

## Durable three-finder Audit

The three quality finders remain the unconditional Audit base. Audit schema
version 2 may additionally retain one typed Context Conformance report when an
explicit Rules Context is supplied with `--against`. Conformance is not a
fourth quality finder: it has a Rule-versus-Target frame, its own exhaustive
coverage contract, and no fabricated quality-review items. The standalone
`mem check-conformance` adapter and Audit call the same core. Legacy schema
version 1 records remain readable as exact three-check snapshots. See
`docs/mem-check-conformance-design-rationale.md`.

`mem audit` is the user-facing orchestration operation for running Duplicate,
Ambiguity, and Conflict analysis together. It is not a fourth semantic finder
and it does not merge the three judgments into one provider prompt. Its help
text names all three finders explicitly.

Audit defaults to the command-start current Context in every environment.
`--context NAME` selects another exact Context, while explicit `--select`
opens the common single-Context selector. All routes freeze the same
direct-Memory frame, then run the existing finder contracts in
the stable order Duplicate, Ambiguity, Conflict. Each finder retains its own
operation name, schema, ruleset, provider call, report type, and cardinality.
The first result is not passed to the second or third. A progress screen may
show the three host-owned stages, but no partial combined report is published
if any finder fails.

Audit reports the stable Duplicate, Ambiguity, Conflict, and optional
Conformance host stages through the shared transient one-line
`CommandProgress` renderer. It does not allocate a full-screen progress box or
publish partial report content. Persistence still occurs only after every
typed check forms one valid snapshot.

After all three checks validate, Audit creates one new UID-addressed artifact
under the Profile's private Audit session directory. It never overwrites a
latest-by-Context slot: repeated runs are separate evidence because a semantic
provider can return different valid judgments for the same Source. The
artifact freezes:

- the canonical Context UID and name;
- every direct Memory UID, content string, and order supplied to all checks;
- the direct-frame digest;
- all three typed reports, including zero-finding reports;
- the ruleset and available provider/model provenance for each independent
  finder run; and
- the creation time and immutable Audit UID.

The completed snapshot is saved before its compact receipt is printed. A
disconnect therefore cannot discard the provider result.
Reviewer responses are the only mutable portion of the session and use CAS
persistence. Every response target is namespaced by its finder kind and must
still exist in the immutable snapshot; a response save cannot replace or
rewrite the report it claims to annotate.

Durable Audit requires retained-analysis authority before provider connection.
An ordinary local Context satisfies that ownership boundary. A granted Source
must authorize `DERIVE` and `SAVE_ANALYSIS`; READ alone remains sufficient only
for the non-retained individual finder route.

### Audit report composition

The report deliberately has no overall quality score and no `PASS` result.
Absence of findings is a model-assisted production result, not proof that the
Source is clean. The complete Viewer is composed from five neutral report
sections:

1. `AUDIT SUMMARY`, stating that all three checks completed over one saved
   direct Context snapshot and giving the total positive finding count;
2. `CHECKS`, listing Duplicate, Ambiguity, and Conflict separately as
   `COMPLETE`, including an explicit zero count;
3. `AUDITED SOURCE`, recording the exact direct Context snapshot captured when
   the Audit ran;
4. `PROVENANCE`, retaining each finder ruleset and provider/model identity; and
5. `BOUNDARY`, stating the non-proof and non-mutation limits.

The Items frame contains review targets only, in the stable group order
Duplicate, Ambiguity, Conflict. A zero-finding check remains visible in
`CHECKS` but does not become a synthetic Item. Each positive result keeps its
operation-owned detail and response mechanics: Duplicate retains its emitted
evidence pair and confirm/reject/defer disposition, Ambiguity retains its
classification, readings, and clarification question, and Conflict retains
its exact pair, scope dimensions, and free-form response without fabricated
resolution choices. A `REQUIRED` ambiguity remains finding priority rather
than becoming a mandatory reviewer answer; Audit does not conflate the need
for source clarification with an obligation to submit a response.

Saved Audits appear in the aggregate `mem review` launcher and reopen exactly
through `mem review audit --session UID`. Review renders the saved audited
Source snapshot and never reruns a finder. It does not fail merely because the
live Context later changes or disappears: the reviewed object is the
historical snapshot, not a claim about the current Context. Review and Audit
never mutate a Context, Memory, or checkpoint.

Ordinary `mem audit` does not open Review automatically. It prints the Audit
session UID and exact Review command. `--snapshot` explicitly prints the full
new report, and `mem review audit --session UID` owns interactive response
work. This keeps execution, durable evidence, and later inspection distinct.

## Units of judgment

The judgments and their public evidence deliberately have different arities:

| Command | Discovery input and result unit | Primary labels |
|---|---|---|
| `find-duplicates` | one direct Context; exact-content groups | emitted: provider-free `DUP / EXACT` groups |
| `find-redundancies` / Dedun analysis | whole selected direct-Memory frame; positive evidence links identify unordered Memory pairs | emitted: `EXACT`, `SURFACE_EQUIVALENT`, `SEMANTIC_EQUIVALENT`; rejection boundaries: `OVERLAP`, `UNKNOWN`, `DISTINCT` |
| `find-ambiguities` | one Memory interpreted inside the complete selected frame | `SINGLE`, `DOMINANT`, `COMPETING` crossed with `NONE`, `HELPFUL`, `REQUIRED` |
| `find-conflicts` | one unordered pair of Memories | `YES`, `MAY`, `NO` |

Consequently, a selected frame with `n` direct Memories has `n` unary ambiguity
targets and admits up to `n(n-1)/2` possible binary relations. That
cardinality does not prescribe the execution strategy. `find-conflicts`
currently names every unordered pair as an explicit target.
The shared redundancy analysis instead discovers equivalence components from a
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
not positive Dedun evidence. In particular, related information and
missing scope must not be presented under a command whose positive result says
that a pair is duplicate.

## Local interpretation boundary

The quality frame contains only directly owned Memories from the exact frozen
set of effective readable Contexts. The whole combined set forms the local
interpretation frame for each judgment. This implements the project assumption
that conflict and ambiguity are judged under ordinary reading of the knowledge
the person explicitly placed in scope, rather than against every imaginable
outside premise. Context membership remains evidence: it is transmitted as
candidate ownership and retained in each result source rather than flattened
away semantically.

The implementation does not recursively traverse embedded Context edges,
dereference `memory_ref` values, or open query-only sources. A reference is a
view of a Memory owned elsewhere, not a second candidate. Lexical descendants
are ordinary independently loaded Contexts and are included only when the
visible range control selects them. Embedded traversal remains deferred until
it has a canonical logical identity, cycle handling, owner-aware results, and
an explicit disclosure policy.

## One-shot Context execution

When semantic targets exist, each finder makes exactly one semantic-provider
call for the complete aggregate direct-Memory frame; an empty semantic
candidate set returns locally without opening a provider session. The
operations use different target contracts:

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

The fixture loader validates each calibration file against the operation's
declared `ruleset_version`. Individual one-shot reports do not retain that
metadata, while durable Audit records the declared version beside each typed
report. The provider payload still sends the calibrated cases rather than a
separate ruleset field, so an Audit version identifies the host judgment
contract but is not by itself full prompt-byte provenance.

This choice favors an inspectable research contract:

- conflict includes every pair explicitly, including lexically dissimilar
  statements;
- duplicate supplies every mechanically distinct representative once without
  repeating it in a quadratic pair table;
- all judgments use the same complete selected Context frame;
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

The semantic finder commands:

- accept the current or one explicit Context directly; Ambiguity and Conflict
  additionally accept a frozen readable Context range through explicit
  `--select`, while Redundancy remains one exact Context;
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

## Relationship to atomize, dedup, dedun, and reconcile

Atomization remains the preferred first refinement stage because a composite
Memory can hide an internal duplicate or make two partly overlapping records
look wholly equivalent. It is a prerequisite that improves the units supplied
to the finders, not a fourth quality finder and not behavior silently performed
by any `find-*` command. The finders can still inspect unatomized intake, but
their labels apply to the stored Memory boundaries they receive.

`dedup` removes byte-identical direct Memories without a provider or review
screen. `dedun` instead discovers the complete exact-plus-semantic evidence
set, validates connected groups, turns confirmed equivalence into a
stale-safe plan, selects an existing survivor UID, checks inbound references,
and creates a checkpoint on Apply.
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
  direct-Memory frame;
- infer a globally correct interpretation from facts absent from that frame;
- scale past the declared one-shot payload; conflict additionally retains its
  explicit pair boundary;
- turn duplicate evidence into mutation-ready survivor groups, resolve
  conflicts, answer clarifying questions, or mutate Memories;
- apply or canonically interpret responses collected by the separate ambiguity
  review shell;
- treat `MAY` or `UNKNOWN` as provider-confidence scores;
- use calibration cases as evidence of held-out performance.
