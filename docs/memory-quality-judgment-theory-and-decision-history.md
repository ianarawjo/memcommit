# Memory quality judgment: theory and decision history

Status: working design as of 2026-07-28

This document preserves the reasoning that led to:

```text
mem find-duplicates
mem find-ambiguities
mem find-conflicts
```

It complements the implementation-oriented
[`memory-quality-finders-design-rationale.md`](memory-quality-finders-design-rationale.md)
and the broader
[`memory-refinement-pipeline-design-rationale.md`](memory-refinement-pipeline-design-rationale.md).
Those documents specify the current contract. This document explains why that
contract took its present form, which alternatives were considered, and which
parts remain hypotheses rather than settled facts.

This is not a verbatim transcript. It reconstructs the decision path and
retains examples that changed the design. Labels written in uppercase are the
canonical machine-facing labels; Korean explanations preserve the nuance in
which they were discussed.

## Short outcome

The main conclusions are:

1. A Memory-quality relation is not stored as a permanent universal truth. It
   is judged on demand under a selected Context.
2. The judge considers ordinary, common-sense readings supported by that
   Context. It does not invent arbitrary hidden premises merely to make any
   sentence true, false, compatible, or incompatible.
3. Ambiguity is a unary judgment about one target Memory in a Context.
   Conflict and duplicate are binary judgments about an unordered Memory pair
   in a Context. That binary relation does not require duplicate discovery to
   enumerate every possible pair as input.
4. Ambiguity cannot be represented by one severity number without mixing two
   questions. It uses:

   ```text
   SINGLE | DOMINANT | COMPETING
   ×
   NONE | HELPFUL | REQUIRED
   ```

5. Conflict uses `YES | MAY | NO`. `MAY` is a semantic result caused by
   competing ordinary readings, not a statement that the model lacks
   confidence.
6. Duplicate means mutual substitutability without information loss under the
   same scope. Entailment, overlap, and relatedness are not enough.
7. The three `find-*` commands only detect and explain. Future `dedup` and
   `reconcile` operations may consume their results, but detection does not
   silently mutate Memory.
8. Atomization precedes these judgments in the intended refinement pipeline.
   The finders can inspect raw intake, but their result then describes the
   current raw Memory boundaries rather than a completed atomic representation.

## 1. How the question developed

### 1.1 From storage structure to semantic operations

The initial discussion concerned the physical and logical structure of
memcommit: Memory, Context, child Contexts, references, order, checkpoints, and
where a task-specific store should live. Once raw Task 1 notes were pasted as
51 Memories, a different problem became visible. The store could preserve the
notes, but preservation alone did not answer:

- which lines were really one atomic commitment;
- which lines repeated the same fact;
- which lines only partly overlapped;
- which lines could be read in several ordinary ways;
- which lines could not jointly govern without another distinction;
- which information applied to students, staff, visitors, or facilities
  operators.

That moved the design from “how is Memory stored?” to “what read-only
judgments should be available over stored Memory?”

### 1.2 Why atomize came before quality judgment

The pasted notes used one non-empty line as one intake Memory. That behavior is
useful because it is deterministic and lossless, but it is not a semantic
claim that every line is atomic. A line can contain a closure, an alternative
location, an operating time, and a reason. Conversely, two lines can be two
occurrences of the same commitment.

The resulting intended order became:

```text
raw intake
→ atomize
→ find-duplicates
→ confirmed dedup
→ find-ambiguities
→ find-conflicts
→ reconcile
→ audience
→ normalize
→ duplicate verification
→ place
```

Atomization preserves occurrences and exposes independently revisable
commitments. It does not remove a repeated occurrence merely because it looks
duplicated. Duplicate detection must remain visible as a later operation.
Confirmed deduplication comes before the ambiguity and conflict scans only to
remove repetitions that have already been shown to be mutually substitutable.
This reduces repeated downstream findings without allowing a merely
overlapping pair to be collapsed.

The current `mem chunk` command was not treated as an atomizer. Structural
splitting by headers, paragraphs, or sentence boundaries cannot decide whether
a condition, exception, transition, or causal relation belongs with a focal
commitment. The separate
[`mem atomize` rationale](mem-atomize-design-rationale.md) records that
contract. Its saved preview and explicit apply paths are now implemented; an
independent second semantic validation pass remains future work.

### 1.3 Why detection was separated from resolution

An early pipeline draft placed ambiguity and conflict inside one
`reconcile` operation. This captured a useful intuition: many apparent
real-world contradictions disappear once audience, time, place, access method,
or exception is supplied.

The turning point was noticing that the judgments do not have the same arity:

- ambiguity targets one Memory;
- conflict targets two Memories;
- each positive duplicate relation connects two Memories, although duplicate
  discovery scans the whole Context rather than receiving pair targets.

Combining all three inside one opaque operation would hide what was judged and
would make regression cases difficult to state. The design therefore retained
their common *resolution* path but separated their *detection* paths:

```text
find-ambiguities ─┐
                  ├─→ future reconcile
find-conflicts ───┘

find-duplicates ─────→ future dedup
```

This is why `reconcile` no longer replaces `find-conflicts`. It may later
combine ambiguity and conflict findings, identify their shared missing
dimension, and propose a question or edit.

The information flow between the separate judgments is still important.
Ambiguity analysis identifies the ordinary readings available for one Memory.
Conflict analysis compares the ordinary, scope-aligned joint readings of two
Memories. When alternate readings of one Memory change whether the pair can
jointly govern, the pairwise conflict result is `MAY`. Separation preserves
the judgment units; it does not pretend the phenomena never interact.

## 2. The epistemic boundary: local ordinary reading

### 2.1 The problem with arbitrary possible worlds

A recurring concern was that almost any sentence pair can be made compatible
or incompatible by inventing enough hidden premises. “The entrance is closed”
and “the entrance is open” can both be true if they concern different
entrances, dates, audiences, meanings of “open,” or hypothetical worlds.
Conversely, apparently unrelated statements can be forced into conflict by an
artificial story.

That observation is useful as a warning, but it is not a usable operational
judge. If the system always searches for some imaginable premise that saves a
pair, it will almost never report a conflict. If it assumes every omitted
coordinate is identical, it will report too many conflicts.

The chosen boundary is:

> Judge only the ordinary readings available to a competent reader from the
> selected Context and common linguistic knowledge. Do not create rare,
> adversarial, or merely logically possible premises just to change the
> result.

This was often described as the “상식 선.” It is deliberately weaker than a
complete legal ontology and stronger than literal string comparison.

### 2.2 Why every premise is not written down

The discussion used the word “정문” as a representative case. A complete
formal account might define the university, building, entrance, orientation,
construction phase, audience, and every relevant exception. Legal documents
sometimes define terms this way because their purpose requires controlled
interpretation.

A Memory system cannot feasibly define every presupposition of ordinary
language. Attempting to do so would turn every note into a contract and would
still fail to reach complete closure. The working principle is instead:

> Make explicit the smallest distinction that changes the reading, judgment,
> or downstream action.

“정문” needs no definition when the Context makes one main entrance salient.
“그 문” needs clarification when both a main entrance and a staff entrance are
ordinary candidates and the choice changes an access rule. Definitions and
questions are therefore local repairs, not an attempt to encode the whole
world.

### 2.3 Context as a local interpretation frame

Let `K` be the selected Context and its directly owned Memories. The core
judgments can be written as:

```text
A(K, m)        = ambiguity judgment for Memory m
D(K, mi, mj)   = duplicate judgment for unordered pair {mi, mj}
C(K, mi, mj)   = conflict judgment for unordered pair {mi, mj}
```

The target cardinality and the interpretation frame are separate:

- `A` is unary because it has one target Memory, but it still reads that
  Memory in `K`;
- `D` and `C` are binary because they compare a pair, but they also use `K` to
  interpret terms and scope.

Binary relation arity is not an execution plan. `C` currently receives
explicit pair targets, while `D` is discovered from a whole-Context set of
mechanically distinct representatives and returned as positive relation
evidence.

This design avoids storing every inferred relation as a permanent graph edge.
The same Memory pair may be judged differently in a different legitimate
Context because the salient referent or operational frame differs. The
Context is part of the operation, not incidental metadata.

Version 1 limits `K` to directly owned Memories. It does not recursively open
embedded Contexts, dereference `memory_ref`, or open query-only sources.
Recursive judgment would need an explicit identity, provenance, cycle, and
disclosure contract.

The local frame can resolve a referent or narrow an ordinary scope, but it is
not permission to copy an unrelated exception from a neighboring Memory into
the target merely to repair it. A neighboring Memory affects the judgment only
when ordinary reading actually connects their subjects and scopes. The finder
must continue to identify which meaning came from the target and which
distinction was supplied by the surrounding Context.

### 2.4 A deliberate asymmetry with atomization

The atomization and quality-finding stages use different evidence boundaries:

- Atomization protects source lineage. It does not silently use neighboring
  Memories to repair a deictic expression unless an explicit source frame is
  declared.
- Quality finding asks how the already stored Memories read together inside
  the selected Context. It therefore uses the other direct Memories as a local
  interpretation frame.

This is intentional rather than contradictory. Atomization asks, “What did
this source occurrence explicitly commit to?” Quality finding asks, “Given
this selected body of Memory, how would an ordinary reader understand and
compare the stored items?”

### 2.5 Why use an LLM for the ordinary-reading judge

The rationale for using an LLM is not that it provides objective truth.
The operations need a proxy for ordinary linguistic and pragmatic reading:
which referent is dominant, which alternate remains live, and which unstated
scope distinction a reader would normally consider.

A language model trained to predict language across many usage contexts is a
plausible instrument for that task. It can apply pragmatic expectations that
would be expensive to enumerate as rules. For example, “eat it all” ordinarily
does not instruct someone to eat packaging, while an ice-cream cone may be
part of what is eaten. The judge should reflect those ordinary distinctions
without enumerating every absurd literal possibility.

This is an empirical justification, not a guarantee:

- the model can omit findings;
- wording and language can shift its judgment;
- model revisions can change results;
- calibration examples can teach a boundary without proving generalization;
- confidence is not the same thing as a semantic label.

The implementation therefore uses strict structured output, local opaque IDs,
fixture-backed calibration cases, and read-only findings. The fixtures contain
version fields, but the current operation does not yet propagate or record
that metadata. Held-out evaluation and repeated-run stability are still
required.

## 3. Ambiguity: two independent axes

The public name `find-ambiguities` is intentionally broader than the narrow
linguistic sense of ambiguity. The operation also reports operational
underspecification: a Memory can have one ordinary reading yet omit the phone
number, date, destination, or other information needed to use it. Both
problems are included because the same read-only workflow can expose the
ordinary reading, explain why use is impaired, and ask the smallest
clarification question. The finding still records whether the cause is
multiple readings or missing operational information rather than claiming
they are the same linguistic phenomenon.

### 3.1 Why one severity scale was rejected

The discussion initially considered an ambiguity scale such as `1–3` or
`1–5`, including rough categories like “있으면 좋음” and “있어야 함.”
That appeared simple but mixed several different quantities:

- how many ordinary readings exist;
- whether one reading is dominant;
- how likely a secondary reading is;
- whether clarification changes a downstream action;
- how serious the consequence of a wrong reading is.

A single number would create false precision. Two sentences could receive the
same score for entirely different reasons, and the system would not know which
question to ask or which behavior to trigger.

The design separated:

1. **reading structure**: how ordinary interpretations relate;
2. **clarification need**: what operational value clarification has.

### 3.2 Reading structure

The canonical `interpretation` labels are:

- `SINGLE`: one ordinary reading is available in the local frame.
- `DOMINANT`: one reading is clearly the ordinary default, but at least one
  secondary reading remains genuinely live.
- `COMPETING`: two or more ordinary readings remain and no single reading
  clearly dominates.

These labels do not count every logically possible interpretation. A remote
pun, technical meaning, or invented situation does not become a competing
reading merely because it can be imagined.

### 3.3 Clarification need

The canonical `clarification` labels are:

- `NONE`: clarification is unnecessary for the intended use, or resolving the
  ambiguity would destroy an intentional effect.
- `HELPFUL`: the reader can proceed with reasonable reliability, but an
  explicit distinction would improve reuse, routing, search, explanation, or
  reduce delay.
- `REQUIRED`: the available Memory is insufficient for a reliable action,
  compliance decision, target selection, or other material outcome.

`NONE` means that clarification is unnecessary; it does not mean that the
Memory has only one reading. This distinction is what permits an intentional
`COMPETING / NONE` double reading.

The criterion is not simply whether a clarification can be written. Almost
every sentence can be made more explicit. The criterion is whether the
clarification changes the reliability or usability of the Memory for the
declared task.

### 3.3.1 Turning the two axes into an actionable explanation

The later review-shell discussion rejected a bare `REQUIRED` or `HELPFUL`
badge followed by generic affected topics. The explanation should combine the
reading structure and clarification need in ordinary language:

- `REQUIRED`: identify the competing, dominant, or missing reading and say
  what cannot be determined reliably;
- `HELPFUL`: identify the reading distinction, state that the current action
  remains possible, and say what would become more precise;
- `NONE`: identify the readings and say why no operational decision depends
  on resolving them.

For example, “same NFC” can mean the same authentication mechanism or the same
credential/permission rule. A `COMPETING / REQUIRED` explanation should state
that distinction and then name the concrete unresolved decision, such as which
credential a door accepts. If the same uncertainty prevents several decisions,
the reason may add a sentence for each. This does not make `REQUIRED` a
numeric severity score, and `HELPFUL` or `NONE` must not be rewritten as
“cannot determine” when action remains possible or no action depends on the
distinction.

The implemented ambiguity review displays English proposed readings and one
combined freeform field. A selected reading plus reviewer text is stored as
clarification evidence; the shell does not decide whether the text is a
refinement, comment, or replacement, and it does not silently turn that
evidence into Memory content. See
[`memory-review-shell-design-rationale.md`](memory-review-shell-design-rationale.md).

### 3.4 Why all nine combinations are possible

The two axes form a real cross-product:

| Reading structure | `NONE` | `HELPFUL` | `REQUIRED` |
|---|---|---|---|
| `SINGLE` | A defined main entrance closes at 5 p.m.; the rule is directly usable. | Visitors check in at the one reception desk; its location would help but can be found on arrival. | Visitors must call the event coordinator, but no contact route exists. |
| `DOMINANT` | At an office reader, “Use your card” ordinarily means the access card; other literal cards do not affect action. | “Get my prescription from the pharmacy” ordinarily means the dispensed medicine, while a document reading remains live but still leads to the shared pharmacy. | At border control, “hold a valid entry permit and show it” favors a physical document reading, but compliance depends on whether original physical possession or valid electronic status is accepted. |
| `COMPETING` | At a blocked road, “No way” intentionally carries both the literal-path and disbelief readings. | At a venue, “Ask the person in charge” can mean the event coordinator or facilities representative; either can probably route the visitor, but naming the role avoids delay. | During a hotel reservation with no preceding referent, “It’s 216” can identify a room, price, or confirmation number, and the action changes. |

The matrix prevents two common mistakes:

- `SINGLE` does not imply `NONE`; a sentence can have one reading but omit an
  indispensable phone number, date, or destination.
- `COMPETING` does not imply `REQUIRED`; intentional wordplay can preserve
  several readings without requiring resolution.

### 3.5 How the representative examples were chosen

The examples were not selected only because they sounded ambiguous. Each one
was used to isolate a boundary between labels.

#### `DOMINANT / HELPFUL`: prescription

Several location and university-name examples were considered, including
local uses of “the city,” London, and overlapping university abbreviations.
They demonstrated context dependence, but their classification could hinge on
geography, institutional convention, or social identity.

The final example became:

```text
(At home) “Could you get my prescription from the pharmacy?”
```

The dispensed medicine is dominant. A prescription order, record, or document
remains a possible secondary object. The phrase “the pharmacy” is intentionally
shared so the example does not introduce a separate pharmacy-referent problem.
Whichever object is meant, the immediate route is the same pharmacy.
Clarification is useful but normally not required to begin the task.

This example helped define `HELPFUL`: the alternate reading is real, but the
current action is robust enough to proceed.

#### `DOMINANT / REQUIRED`: entry permit and “hold”

Government-certified documents, visa review, and the country whose government
must certify a document were considered. Some versions produced genuinely
competing readings rather than a dominant one.

The final example became:

```text
(At border control)
“You must hold a valid entry permit and show it to the officer on arrival.”
```

“Show it” makes a presentable document the dominant reading. However, “hold”
can also describe possessing a legal entitlement or status. Some regimes
accept electronic proof; others require an original physical document.
Because the compliance outcome changes, the dominant reading does not remove
the need for clarification.

This example established that dominance and required clarification are not
opposites.

#### `COMPETING / NONE`: intentional double reading

The discussion explicitly asked whether deliberate ambiguity should be
allowed. It should. Treating every double entendre as a defect would erase
jokes, slogans, literary effects, and deliberate parallel meanings.

The final compact example became:

```text
(While walking, someone reaches a blocked road and jokes)
“No way.”
```

The literal lack of a way forward and the exclamation of disbelief are both
active. Asking which one is intended would make the utterance worse, not
better.

#### `COMPETING / HELPFUL`: person in charge

The final example became:

```text
(At a venue shared by an event team and facilities staff)
“Ask the person in charge.”
```

The event coordinator and facilities representative are both ordinary
referents. Either person can probably route the visitor to the right answer,
so the instruction is not unusable. Naming the intended role would still
reduce delay.

#### `COMPETING / REQUIRED`: 216

The final example became:

```text
(During a hotel reservation, with no preceding question or referent)
“It’s 216.”
```

Room number, price, and confirmation number are all ordinary candidates.
Unlike the prescription example, selecting a different reading changes the
booking action. Clarification is required.

### 3.6 Examples that were useful but deliberately not made canonical

Some examples were valuable precisely because their label changed with the
task:

- “When people arrive, guide them” ordinarily suggests visitors in many
  service contexts. Explicitly saying “visitors” may be `HELPFUL`, but it can
  become `REQUIRED` when staff, contractors, students, and visitors receive
  different instructions.
- “Use your card” is usually clear at an access reader even though credit and
  transit cards are literal alternatives. The access setting makes one reading
  dominant. If the site supports several credentials, clarification can move
  from `NONE` to `HELPFUL` or `REQUIRED`.
- University abbreviations are useful demonstrations of local dominance, but
  they bring geographical and institutional assumptions that make a first
  golden boundary less controlled.

These cases show why an ambiguity label belongs to `(Context, Memory)`, not to
an isolated sentence forever.

### 3.7 Ambiguity includes underspecification, but records the reason

Strict linguistic terminology distinguishes lexical ambiguity, referential
ambiguity, scope ambiguity, vagueness, ellipsis, and missing operational
information. The product-level finder uses “ambiguity” broadly enough to
surface all of these when they make a Memory unclear or unusable.

Typical issue dimensions include:

```text
REFERENT | SCOPE | ACTION | TIME | CONDITION | TERM
```

For example:

- “그 문” is primarily a referent problem;
- “출입을 제한한다” can omit audience, direction, degree, and exception;
- “call the coordinator” can be `SINGLE / REQUIRED` because the action is
  clear but the contact route is absent;
- `june xx - aug xx` is not multiple reading structure, but the missing dates
  make clarification required.

The structured label should therefore be accompanied by ordinary readings, a
reason, and the smallest useful question. The label alone is not an adequate
explanation.

## 4. Conflict: pairwise fit under ordinary readings

### 4.1 From `fit` to the public `conflict` polarity

Earlier notes used the more general word `fit`, with:

```text
fit = YES | MAY | NO
```

Under that name, `YES` naturally means “the Memories fit.” The implemented
public field is instead named `conflict`, so its polarity is reversed:

```text
conflict = YES | MAY | NO
```

Here:

- `YES` means the pair conflicts;
- `NO` means the pair is jointly explainable;
- `MAY` means ordinary readings divide between those outcomes.

The field name and polarity must never be mixed. If a future API revives
`fit`, it must either invert the labels explicitly or use different names.

There was also a temporary preference for making conflict a binary `YES/NO`
decision. That would have been simpler when two statements clearly deny and
permit the same action. The “the entrance” contrast changed the decision:
ordinary readers can reasonably resolve the same expression to the main
entrance or the separate staff entrance, and those readings produce different
pair outcomes. Dropping `MAY` would force the judge either to invent one
referent or to hide a material unresolved distinction. `MAY` was therefore
retained, but only for semantic indeterminacy—not for model hesitation.

### 4.2 Formal reading of `YES`, `MAY`, and `NO`

Consider the set `ΩK(mi, mj)` of materially ordinary joint readings of pair
`{mi, mj}` in Context `K`. A joint reading is **scope-aligned** when it
compares the claims at the same subject, time, place, audience, condition, and
other operational coordinates that ordinary reading says they share.
Statements that explicitly govern different scopes are jointly explainable,
not conflict candidates merely because they use related vocabulary.

For every joint reading `ω` in `ΩK(mi, mj)`, let `x(ω)` be `1` when both claims
cannot jointly govern and `0` when they are jointly explainable:

- `YES`: `x(ω) = 1` for every ordinary scope-aligned joint reading.
- `NO`: `x(ω) = 0` for every ordinary scope-aligned joint reading.
- `MAY`: at least one ordinary joint reading has `x(ω) = 1` and at least one
  other has `x(ω) = 0`.

`MAY` is not a low-confidence `YES` or `NO`. It is a statement about the
structure of the available meanings. Model uncertainty, instability, or
insufficient performance evidence would require a separate field such as
`needs_review`; it must not be smuggled into `MAY`.

### 4.3 The controlled entrance contrast

The initial golden set fixes one shared frame:

```text
The building has a main entrance and a separate staff entrance.
All statements concern the same construction period and time after 5 p.m.
```

It then changes only the second Memory:

| Label | Memory A | Memory B | Reason |
|---|---|---|---|
| `YES` | The main entrance is closed to everyone after 5 p.m. | Staff may use the main entrance after 5 p.m. | Same entrance, time, and audience; denial and permission cannot both govern. |
| `MAY` | The main entrance is closed to everyone after 5 p.m. | Staff may use the entrance after 5 p.m. | If “the entrance” is main, conflict; if it is the separate staff entrance, compatible. |
| `NO` | The main entrance is closed to everyone after 5 p.m. | Staff may use the separate staff entrance after 5 p.m. | Explicitly different entrances. |

Using one shared frame is important. If three unrelated examples were used,
the model could learn superficial topic or tone differences instead of the
semantic boundary.

### 4.4 How conflict and ambiguity can coexist

Separating the operations does not claim that the phenomena are independent.
They can overlap in several ways:

1. A Memory can be ambiguous without participating in any conflict.
2. Two individually clear Memories can directly conflict.
3. An ambiguous expression can make a pair `MAY` when its alternate readings
   change the conflict outcome.
4. A pair can be `YES` while one Memory remains ambiguous in another respect,
   if every ordinary reading still conflicts.

For example:

```text
Every entrance closes at 5 p.m.
That entrance stays open until 10 p.m.
```

In a fixed Context where the ordinary candidates are entrances of the same
building, “that entrance” may be referentially ambiguous, but every candidate
is covered by “every entrance,” so the pair can remain `YES`. By contrast:

```text
The main entrance closes at 5 p.m.
That entrance stays open until 10 p.m.
```

is `MAY` when “that entrance” ordinarily ranges over the main and separate
staff entrances.

This distinction is why conflict must judge readings rather than simply ingest
the output label of the ambiguity finder. A future `reconcile` can compose both
reports, but the first detectors remain independently callable.

### 4.5 Logical significance and limits

The operation is deliberately closer to practical consistency checking than
to a theorem prover:

- it does not claim metaphysical inconsistency;
- it does not quantify over every possible world;
- it does not infer that one Memory is false;
- it identifies whether the selected operational knowledge can jointly govern
  under ordinary reading.

Version 1 is pairwise. A set of three or more Memories can be collectively
inconsistent even when every pair is acceptable. Such higher-arity conflict is
an explicit non-goal of the initial finder.

## 5. Duplicate: equivalence is stronger than relatedness

### 5.1 Why duplicate findings use pair evidence

Duplicate equivalence remains a binary relation:

```text
D(K, mi, mj)
```

The first implementation conflated that pair-shaped result with a pair-shaped
input and materialized every possible `{mi, mj}` target. The revised finder
discovers from the whole Context. Mechanical comparison builds equivalence
components by keyed grouping, and the semantic provider receives only the
first representative of each component. It returns provisional, disjoint
semantic-equivalence groups.

The public report expresses each component as a canonical spanning tree of
unordered pair evidence. A component with `k` Memories needs `k-1` links, not
the `k(k-1)/2` links in its pair clique. Pair-shaped evidence therefore remains
easy to inspect without making pair enumeration the search algorithm.

These provisional components are not mutation-ready `dedup` groups. Applying
them still requires additional decisions:

- has the semantic evidence been confirmed;
- which existing UID survives;
- which order and provenance are retained;
- whether inbound `memory_ref` values can be migrated safely;
- whether the plan is stale.

Those are future `dedup` responsibilities, not finding responsibilities.

### 5.2 Two trust layers

Mechanical findings are local and deterministic:

- `EXACT`: stored content strings are identical.
- `SURFACE_EQUIVALENT`: only conservative line-ending, Unicode NFC, outer
  space, or horizontal-space normalization differs.

Mechanical comparison intentionally preserves punctuation, numbers, dates,
negation, modality, list markers, and vertical structure.

Semantic comparison asks whether either Memory can replace the other without
information loss under the same:

- subject and applicability;
- predicate or operational state;
- object and place;
- audience and time;
- modality and uncertainty;
- access method, condition, exception, and relevant causal scope.

The calibration boundary is:

```text
SEMANTIC_EQUIVALENT  positive duplicate finding
OVERLAP              shared claim plus unique information
UNKNOWN              missing scope prevents equivalence judgment
DISTINCT             not mutually substitutable
```

One-way entailment is not enough. For example:

```text
The garage is closed during construction.
The garage is closed during construction because waterproofing is underway.
```

The first claim is contained in the second, but replacing the second with the
first loses the stated cause. The pair is `OVERLAP`, not a safe duplicate.

### 5.3 Why duplicate detection must not remove anything

Even deleting an exact duplicate changes UID availability, provenance, order,
history, and possibly references. A semantic model should not choose canonical
wording while it is deciding equivalence.

The finder therefore reports positive evidence links only. A future confirmed
`dedup` plan must independently:

- select an existing survivor UID;
- preserve or explicitly justify wording;
- name every absorbed UID;
- inspect inbound references;
- bind the plan to a Context fingerprint;
- reject a stale plan;
- record the mutation in one checkpoint.

## 6. Why the commands are named `find-*`

The existing command:

```text
mem find <query>
```

is semantic retrieval. It ranks stored items relevant to a user query. The new
commands are relationship and quality scans:

```text
mem find-duplicates
mem find-ambiguities
mem find-conflicts
```

The prefix was retained because all four operations are read-only discovery.
The plural nouns communicate that a Context scan can return zero, one, or many
results. Shorter names such as `dupes`, `ambiguity`, or `conflict` were rejected
because they do not say whether the command lists, changes, or resolves.

The names also preserve a clean distinction:

- `find-duplicates` reports; future `dedup` changes;
- `find-ambiguities` and `find-conflicts` report; future `reconcile` composes
  and may propose changes.

The extra characters are justified by making the mutation boundary visible in
the command itself.

## 7. Why each semantic finder is one operation call

Several implementation strategies were considered:

- call the model once per Memory or pair;
- retrieve likely candidates with embeddings and judge only those;
- split all targets into several batches;
- materialize every pair but place the complete pair list in one call;
- give one provider operation the complete direct Context without enumerating
  duplicate pair targets.

The final clarification was to follow the already implemented semantic
operation style:

```text
mem find      → one provider.complete call
impact/update → one shared update-planning provider.complete call
```

The new commands therefore use:

```text
find-duplicates  → operation="find_duplicates" once
find-ambiguities → operation="find_ambiguities" once
find-conflicts   → operation="find_conflicts" once
```

The one-shot preference also reflected the prototype discussion's qualitative
experience: giving the strongest available reader the whole local problem at
once felt more coherent than combining many small judgments. That observation
is a design motivation, not measured evidence. The implementation does not pin
a named “best” model; it reuses Codex's current recommended model selection,
so reproducible evaluation must record the resolved model separately.

### 7.1 The pair-input design was revised

The initial implementation made both duplicate and conflict payloads name
every canonical unordered pair. This looked auditable because the relation
itself is binary and the requested space was explicit. The later scalability
question exposed a conflation:

> A pair-shaped answer does not require a pair-shaped request.

At one million Memories, the possible relation space contains
`499,999,500,000` pairs. Materializing it repeats the same Memory IDs and
contents an impossible number of times before the semantic judge does any
useful work. Even at smaller sizes it spends prompt budget describing a
Cartesian product the model can infer from the candidate set.

The revision applies to duplicate discovery:

1. Local hash maps build exact and conservative surface-equivalence
   components in linear input time.
2. Each component contributes only its first Context-ordered representative
   to the semantic payload.
3. The model sees all representatives together and returns disjoint
   `SEMANTIC_EQUIVALENT` groups.
4. The local program converts each group into representative-to-member
   evidence links, so a group of size `k` produces `k-1` findings rather than a
   pair clique.

Conflict retains explicit pair targets in version 1 because its output is not
an equivalence grouping and different pairs can independently be `YES`, `MAY`,
or `NO`. Its scalability contract is therefore a separate future question.

The advantages are:

- every mechanically distinct duplicate candidate sees the same local Context
  frame;
- the command has one observable semantic operation;
- duplicate candidates are not discarded by a similarity prefilter;
- duplicate request construction and stored evidence stay linear rather than
  enumerating a clique;
- results are easier to reproduce as one study step.

The costs are:

- the one-shot prompt has a finite size;
- a positive-only discovery response cannot prove that the model found every
  semantic-equivalence group;
- one large operation may take longer than a candidate-filtered scan.

The revised duplicate input is approximately `O(total text + n)` and its
spanning evidence is at most linear in `n`. This still does not make the
current one-shot provider suitable for a million Memories: their contents
cannot fit within the 1,000,000-character effective provider payload. True million-scale
semantic duplicate discovery needs indexed candidate generation and
reproducible sharding or batching with an explicit recall and coverage
contract. The current command fails rather than silently truncating or
switching modes.

The finders reuse the same temporary ChatGPT-authenticated Codex provider as
the existing `find`, `impact`, and `update` paths. They do not introduce a
separate API-key or model-routing mechanism.

## 8. Golden examples as executable theory

The discussion repeatedly returned to examples because an abstract phrase
such as “ordinary ambiguity” does not locate a decision boundary precisely.
The clozemaking-style idea was to turn the theory into contrastive, answerable
cases:

- hold most of the scenario constant;
- change one semantic coordinate;
- record the expected label;
- record why adjacent labels are wrong;
- preserve a smallest clarification question.

The fixtures are:

- [`ambiguity.json`](../memcommit/eval/fixtures/ambiguity.json)
- [`conflict.json`](../memcommit/eval/fixtures/conflict.json)
- [`duplicates.json`](../memcommit/eval/fixtures/duplicates.json)

They serve three purposes:

1. prompt calibration;
2. a machine-readable label and boundary corpus used by structural regression
   tests;
3. a durable record of what the labels currently mean.

They are not yet an end-to-end semantic regression harness. Current tests
verify structural properties such as label sets and the ambiguity
cross-product; they do not call the provider and prove that every fixture
receives its expected semantic result.

They do not serve as held-out accuracy evidence when the same examples are
included in the prompt. Evaluation must add:

- independently written held-out cases;
- paraphrases and minimally changed contrasts;
- Korean, English, and cross-language cases;
- adversarial changes to time, audience, negation, and modality;
- repeated-run stability;
- checks for omitted positive findings as well as false positives.

Golden cases are expected to grow. The fixture already has a
`ruleset_version` field, so changing a boundary should update that value and
the rationale rather than silently rewriting an expected answer. The current
provider payload and finding report do not yet carry this version, which is an
explicit reproducibility limitation.

## 9. Task 1 run as an illustrative check

The three commands were run once against the previously pasted
`temp/task-1` Context:

```text
51 direct Memories
1,275 possible binary relationships
```

That first run used the now-superseded duplicate pair-input implementation, so
both duplicate and conflict materialized the 1,275 relationships. In the
revised implementation the number applies only to the explicit conflict
targets. Duplicate performs deterministic keyed grouping and sends each
remaining representative once.

The observed results were:

```text
find-duplicates  → 0 findings
find-ambiguities → 24 findings
find-conflicts   → 1 finding
```

After the linear duplicate-discovery revision, `mem find-duplicates` was run
again on the same Context. All 51 Memories were mechanically distinct, so the
semantic payload contained 51 representatives exactly once and no pair list.
The actual CLI result remained:

```text
Context: temp/task-1
  51 direct memories, 0 findings

  (no duplicate findings)
```

The zero remains an illustrative model result, not a claim that all possible
pairs were exhaustively judged.

A separate real-provider smoke check used two unsaved paraphrases from the
semantic-equivalence calibration boundary. The provider returned one
`SEMANTIC_EQUIVALENT` group, and the local command converted it into one
Context-ordered evidence link. This validates the new group-shaped structured
output path without treating a calibration example as held-out accuracy
evidence.

The conflict was:

```text
“nfc로 되어서 실물 카드만 필요하다.”
vs.
“학생들 - 안내해야 한다 - 실물 카드를 받고나 앱으로.”

conflict: YES
scope dimension: ACCESS_METHOD
```

This run demonstrates that the commands execute on the intended data and that
the conflict boundary can expose a material access-method disagreement. It is
not a quality benchmark or immutable ground truth:

- the raw 51 lines have not been semantically atomized;
- many ambiguity findings reflect incomplete drafting such as “시간 이후,”
  `june xx - aug xx`, or missing destinations and contact routes;
- zero duplicate findings can mean the apparent repetitions were only partial
  overlap under the current Memory boundaries;
- a one-shot model can omit findings;
- another provider revision or ruleset may produce a different result.

The Context remained unchanged with its original two checkpoints, confirming
the read-only boundary.

## 10. What remains deliberately unresolved

The following work is not hidden inside the current finders:

- strengthening `mem atomize` with an independent semantic validation pass and
  repeated-run stability evaluation beyond its implemented preview/apply
  lineage;
- creating held-out semantic evaluations rather than calibration-only tests;
- recording resolved model and ruleset metadata in reusable finding reports;
- testing multilingual and repeated-run stability;
- detecting collective conflicts that require three or more Memories;
- deciding whether and how recursive Context analysis should work;
- turning duplicate evidence components into a stale-safe `dedup` plan;
- composing ambiguity and conflict findings in `reconcile`;
- deciding how clarification answers update Memory without erasing source
  provenance;
- adding structured downstream-result identities if review priority is later
  meant to count changed required/helpful decisions rather than sort only by
  the finding's overall clarification label;
- representing audience and disclosure differences;
- replacing the temporary Codex provider with MCP or an internal-network
  provider.

These are explicit next stages. The current design should not be described as
solving them merely because it can report a related finding.
