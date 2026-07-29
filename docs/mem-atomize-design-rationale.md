# `mem atomize` design rationale

## Design prompt

The refinement pipeline needs an explicit atomization stage before
deduplication. The intended model combines:

- the Zettelkasten intuition that one note should contain one addressable idea;
- the semantic distinction between a proposition and a compound proposition;
- a practical size boundary for Memories;
- rules that can be tested rather than an instruction to “split this
  appropriately”;
- the source-first question/answer regression style used by the local
  `clozemaking` project.

This note fixes the semantic contract. `mem impact atomize` produces and saves
a Context-scoped preview; `mem atomize --save` and `--save-as` explicitly apply
that locally validated preview. A second, independent semantic validator remains
future work, so application is a deliberate research-prototype action rather
than a claim of semantic proof. The later quality-finding stages intentionally
use a different evidence boundary: atomization protects one source occurrence
and does not borrow neighboring Memories as hidden source evidence, while
quality finding reads all direct Memories in the selected Context as a local
interpretation frame. The reason for that asymmetry is documented in
[`memory-quality-judgment-theory-and-decision-history.md`](memory-quality-judgment-theory-and-decision-history.md).

## Decision

An atomic Memory is one **focal-commitment occurrence** together with every
qualifier needed to preserve that occurrence's meaning.

A focal commitment is the smallest unit that should be independently:

- corrected or superseded;
- withdrawn;
- referenced;
- assigned to an organizational Context;
- assigned an audience or disclosure boundary.

For an assertion, this is normally one focal event, state, action, policy, or
relation. Subject, place, time, audience, modality, negation, condition, and
exception remain attached when they determine when that commitment is true.
A directive may also be atomic when it expresses one action rule. A heading,
open question, or process note is addressable content but is classified as
non-propositional rather than forced into a factual claim.

This is deliberately not the strict logical definition of an atomic formula.
An operational rule such as `if C, do P`, a transition from an old value to a
new value, or a quantified policy with an exception can be one revision unit
even though its sentence contains several clauses. The purpose is stable
memory identity and safe independent revision, not maximal syntactic
fragmentation.

Occurrence identity and semantic equivalence are different. If a raw Memory
says `P. P.`, it contains two explicit occurrences even though both express
the same commitment. Atomization exposes both occurrences as children so the
dedup stage can later show why one is absorbed. It must not silently convert
two source occurrences into one.

The semantic class and the proposed action are kept separate:

| Semantic class | Meaning | Proposed action |
|---|---|---|
| `ATOMIC` | one focal-commitment occurrence with its required scope | `KEEP` |
| `COMPOSITE` | two or more clearly bounded focal-commitment occurrences; occurrences may later prove equivalent | `SPLIT` |
| `UNCERTAIN` | atomicity or qualifier scope cannot be decided from the declared source | `RECONCILE` |
| `NON_PROPOSITIONAL` | heading, question, fragment, or process note that should not be converted into a claim | `KEEP_CLASSIFIED` |

Only `COMPOSITE` produces child Memories. Uncertainty is not permission to
guess, and non-propositional content is not permission to delete.

## Atomicity rules

### One focal predicate, not one sentence

Sentence boundaries, commas, bullets, and coordinating words are candidate
signals only. One sentence can contain several commitments, while several
clauses can express one scoped policy.

The main split test is:

> Does this clause assert another focal predicate or directive that should be
> independently corrected, withdrawn, referenced, placed, or disclosed?

Changing a value inside one commitment does not by itself imply another atom.
For example, changing the closing time edits the time slot of one opening-hours
commitment. It does not require a separate “time Memory.”

### Named logical rules

The first ruleset should expose stable reason codes so a preview, regression
case, and checkpoint can say why a boundary was chosen.

| Code | Rule | Consequence |
|---|---|---|
| `A01_ONE_FOCUS` | One child owns one focal-commitment occurrence. | Independent `P` and `Q`, and repeated source occurrences, receive separate child occurrence mappings. |
| `A02_SCOPE_ATTACHED` | Subject, audience, place, time, modality, negation, condition, and exception stay with the commitment they scope. | Do not create qualifier fragments. |
| `A03_RELATION_PRESERVED` | Conditional, exception, alternative, transition, comparison, and causal relations are commitments in their own right when they are focal. | Do not split a relation into claims that change its meaning. |
| `A04_SOURCE_GROUNDED` | Every child assertion must be supported by an explicit source occurrence or declared frame. | No invented facts or silent resolution. |
| `A05_MINIMAL_EXPANSION` | Repeating an explicit subject or qualifier and repairing grammar are allowed only as needed to make a child stand alone. | No stylistic normalization during atomization. |
| `A06_NO_HIDDEN_CONTEXT` | Neighboring Memories and undeclared Context assumptions are not evidence. | Deictic content without an explicit frame becomes `UNCERTAIN`. |
| `A07_RETAIN_NON_CLAIMS` | Headings, questions, and process notes remain addressable. | Classify and retain; do not fabricate propositions. |
| `A08_PRESERVE_OCCURRENCES` | Atomization preserves every source occurrence, including repeated claims. | Duplicate removal belongs to `mem dedup`. |
| `A09_SIZE_IS_LINT` | Length can request review but cannot prove atomicity. | Never split solely because a threshold was crossed. |
| `A10_STAGE_BOUNDARY` | Atomization does not deduplicate, reconcile, normalize, classify audiences, or place. | Later stages remain observable. |

### Operators and relations

These rules make the proposition/compound-proposition distinction concrete.

- Independent conjunction `P and Q` is split when `P` and `Q` have separate
  focal predicates.
- Negation `not P`, modality `may P`, and a time or audience restriction stay
  attached to `P`.
- `if C then P` remains one conditional policy. Splitting `C` into a factual
  Memory would assert something the source did not assert.
- `P except E` remains one policy with an exception when the exception limits
  the policy's scope.
- `P or Q` remains one alternative or permission rule. Splitting the options
  would incorrectly assert both independently.
- An old-to-new change can be represented as one transition relation. For
  example, “the entrance closing time changes from 10 p.m. to 5 p.m.” is one
  hours-change commitment, not two timeless fragments.
- `P because Q` remains one causal relation when the reason is part of the
  focal commitment. If disclosure or placement requires a split, the reason
  child must still say “the reason for P is Q”; a bare `Q` child would lose
  the relation.
- A coordinated list with one predicate is not automatically atomic. A joint
  “integrated commissioning test” may be one event, while separately
  replaceable electrical and fire systems are separate commitments. The task
  profile determines whether the members are independently addressable.

Rule precedence is conservative:

1. `A04_SOURCE_GROUNDED` and `A02_SCOPE_ATTACHED` prevent invention or scope
   loss.
2. `A03_RELATION_PRESERVED` protects the meaning of an explicit relation.
3. `A01_ONE_FOCUS` then separates remaining independent occurrences.

Thus relation preservation dominates a syntactic conjunction or a generic
independent-addressability cue. The default representation of focal
`P because Q` is one causal-relation atom. If a declared task profile requires
the closure `P` to be separately addressable, an allowed split is `P` plus
“the reason for P is Q”; `P` plus bare `Q` is never allowed.

## Source and Context boundary

The current base Memory contains only `uid` and `content`. It has no semantic
frame inherited from its neighbors. Consequently:

- `해당 기간`, `앞서 말한`, `같은 NFC`, `여기`, and similar expressions are
  not resolved from the preceding Memory by default;
- an explicit qualifier inside the source may be copied to every child it
  clearly scopes;
- an explicit antecedent inside the source may be repeated with the smallest
  grammatical repair needed for a stand-alone child;
- a source-external frame may be used only if the import or atomize request
  declares it, gives it a stable ID, and binds its content fingerprint into
  the plan;
- if the frame is missing or its scope is ambiguous, the source is
  `UNCERTAIN` and remains unchanged.

This boundary matters because placement and `memory_ref` can later separate a
child from its original neighbors. A Memory that is understandable only by
physical adjacency is not independently addressable.

## Source-first Q/A ledger

The local `clozemaking` project does not have an automatic semantic theorem
prover. Its useful pattern is:

1. preserve the original input;
2. classify the task before transforming it;
3. keep named rules in a human-reviewable guide;
4. record known-wrong `x>` outputs beside one canonical `->` answer;
5. run an explicit self-check;
6. treat every curated case as a regression that must pass.

The relevant sources are the sibling repository's `guide_universal.md`,
`AGENT.md`, `test_with_answer`, and
`scripts/extract_test_from_test_with_answer.py`. The extraction script only
derives an input view; it is not a semantic validator. Memcommit should reuse
the test method without claiming that Q/A comparison proves natural-language
equivalence.

Before proposing children, the atomizer builds a claim-occurrence ledger from
the source. Each entry contains:

```text
occurrence ID
source span
speech act
focal predicate or relation
scope slots:
  subject, audience, place, time, modality, condition, exception, cause
canonical retrieval question
canonical answer
```

The question must be discriminating. “What does this Memory say?” and “What
are all the relevant facts?” are invalid omnibus questions. A valid focal
question names the anchor and asks for one event, state, action, policy, or
relation. Several facet questions about the who, where, or when may support
the same focal commitment, but they do not create additional atoms by
themselves.

### Target independent validation pass (future)

The checks in this subsection describe the intended second semantic pass, not
the currently implemented apply gate. The implemented preview rejects malformed
schemas, incomplete candidate coverage, invalid identities or positions,
ungrounded literal source-span citations, and stale Context frames. Apply
repeats those local checks, then deliberately consumes the same one-shot
semantic proposal. It does not yet emit the `validation_status` or per-check
`PASS`/`UNKNOWN` ledger below, and it does not make a second model or human
approve the proposal.

The target design separates proposal generation and semantic validation. The
same unexamined model response must not both propose and approve its own split.

Every proposed split must pass:

1. **Occurrence coverage** — every source claim occurrence maps to at least
   one child, including a repeated occurrence.
2. **No invention** — every child commitment and qualifier maps to a source
   span or a fingerprinted declared frame.
3. **Single focus** — each child owns one focal commitment group.
4. **Self-contained answer** — the child and declared frame answer its focal
   question without unresolved deixis.
5. **Scope preservation** — negation, modality, audience, time, condition,
   exception, and causal relation remain on the correct child.
6. **Occurrence necessity** — removing a child loses coverage of at least one
   source occurrence assigned to that child.
7. **Reconstruction** — the ordered child commitments jointly support the
   same ledger as the source, without strengthening or weakening it.

Under that future contract, any `UNKNOWN` check blocks application. It does not
automatically overwrite a known semantic class: the validated plan records
`validation_status=UNKNOWN` and `action=BLOCKED`. The class is `UNCERTAIN` only
when the unknown result actually concerns atomicity, antecedent identity, or
qualifier scope.

Two children may answer the same semantic question when the source repeated
the same claim. That is reported as `DUPLICATE_CANDIDATE`, not rejected and
not collapsed. Otherwise the atomizer would perform deduplication before the
dedup stage and erase source-occurrence provenance.

Q/A is therefore a conservative rejection and regression mechanism, not the
definition of truth. Human-reviewed golden cases remain the semantic oracle
for the research prototype.

## Size rule

Size is a lint signal, not an atomicity condition.

The current `temp/task-1` intake has 51 Memories:

```text
Unicode characters: minimum 10, median 32, maximum 150
whitespace tokens:  minimum 2,  median 8,  maximum 36
```

A 56-character source already contains clearly independent commitments.
Conversely, a long conditional with a subject, audience, time, credential
method, and exception may still contain one focal policy. Character or token
limits therefore create both false negatives and false positives.

The initial Task 1 profile uses this review lint:

```text
SIZE_REVIEW when:
  content has more than 80 Unicode characters, or
  content has more than 2 sentence-like segments
```

For this lint, `sentence-like segments v1` is a deterministic surface
counter:

1. normalize CRLF and CR line endings to LF;
2. split at one or more non-empty line boundaries;
3. within each line, split after a run of `.`, `?`, `!`, `。`, `？`, or `！`
   when the run is followed by whitespace or the end of the line;
4. ignore empty results.

It intentionally does not try to understand abbreviations. A false-positive
lint only requests review and can never create a split. The implemented profile
covers Korean and English terminators, Markdown bullet lines, abbreviations,
decimals, and mixed newlines with pure-function tests.

Crossing this threshold adds a reason to inspect the source. It never changes
`ATOMIC` to `COMPOSITE`. There is no hard minimum: a very short complete claim
may be atomic, while a short fragment may be `UNCERTAIN` or
`NON_PROPOSITIONAL`.

The threshold is profile configuration and must be recalibrated against the
golden corpus. Storage byte limits and provider input limits are separate
safety constraints; they must not be presented as semantic atomicity.

At least one `LONG_BUT_ATOMIC` and one `SHORT_BUT_COMPOSITE` case are permanent
regressions.

## Plan contract

### Implemented impact report

The implemented first slice is intentionally smaller than the validated plan
described below:

```bash
mem impact atomize
mem impact atomize --context temp/task-1
mem impact atomize --all
```

It loads the selected Context without resolving embedded Contexts or
`memory_ref` targets, then sends every directly owned Memory once under opaque
call-local IDs. The local Context name is omitted from the provider payload
because it is neither source evidence nor necessary routing information. One
provider completion must return exactly one
`ATOMIC`/`COMPOSITE`/`UNCERTAIN`/`NON_PROPOSITIONAL` classification for every
candidate. Context name, item order, neighboring Memories, and calibration
examples are explicitly not evidence frames. Version 1 supplies no declared
external frame.

The provider receives the definitions of A01-A10, not just their names. The
provisional response contains the candidate ID, classification, selected
reason codes, concise reason, and—in the `COMPOSITE` case only—ordered child
contents with literal source spans. Local code rejects missing, duplicate, or
unknown candidates; extra or duplicate JSON fields; invalid classes or reason
codes; a composite with fewer than two children; children on any other class;
and source spans absent from that same Memory. This check establishes that
each child cites literal evidence; it does not prove that every word in a
model-generated child is entailed by that evidence. That stronger semantic
grounding remains part of independent validation. Size lint and its profile
fingerprint are checked locally and lint never decides the semantic class.

The preview's source spans are strings rather than occurrence-addressed
offsets. This permits an explicit shared qualifier to support several children,
but it also means local parsing cannot prove A08 occurrence coverage: two
children can structurally cite the same single occurrence. A future validated
ledger must distinguish occurrence IDs or offsets and separately identify
copied scope spans. Until then, repeated-occurrence preservation is a prompted
and human-reviewed proposal property, not a mechanically proven invariant.

All direct Memories are classified in one call. The default terminal view
hides unchanged `ATOMIC` details for readability, while `--all` shows them;
the summary always accounts for every input. No child UID is allocated during
preview. Context JSON, ordering, checkpoints, active state, the directional
`impact-plan.json`, and query-only sources are not written or opened. The
latest digest-bound preview is written separately to
`~/.mem/atomize-analyses/<context-uid>.json`.

There is intentionally only one such slot per Context UID. A later preview
atomically replaces the earlier artifact rather than building an analysis
archive. If the earlier preview was applied, its checkpoint retains the
operation/analysis UID, source-to-result relation, result contents, reason, and
reason codes. Preview-only fields such as its creation time, lint, and literal
source spans are not all copied into the checkpoint, so they can no longer be
recovered after the slot is overwritten. Retaining a complete sequence of
analyses is future work.

This result is named `AtomizeImpactReport`, not `AtomizePlan`. It is a proposal
with locally verified evidence-span citations that is safe to inspect, but
local structural validation is not independent semantic approval. In
particular, the same one-shot model response cannot mark its own reconstruction
or single-focus judgment `PASS`. The command therefore ends with:

```text
This inspection applied no changes and created no checkpoint.
Analysis saved [<uid>] for mem trace/rationale.
```

The saved artifact is intentionally separate from directional update state.
`mem atomize` consumes it, and `mem trace`/`mem rationale` attach it without
mislabeling it as content history. Loading repeats local schema, count,
source-span grounding, and Context-digest validation.

The temporary provider follows the existing semantic-operation boundary: one
ephemeral Codex session authenticated by the local ChatGPT login, with user
configuration ignored. The atomize command does not pin a model name; model
selection is currently owned by the Codex provider default. A study that
requires exact model reproducibility must add an explicit allowlisted model
setting and record it with the report before treating runs as comparable.

### Saved analysis and explicit prototype application

The current commands separate destination choice from semantic analysis:

```text
mem atomize --save                 # modify the selected Context
mem atomize --save-as NEW_CONTEXT  # preserve source; create and switch
```

Both require the latest preview to match the Context UID, name, ordered
direct-Memory digest, and current source contents. `COMPOSITE` sources are
replaced in place with fresh child UIDs. `ATOMIC`, `UNCERTAIN`, and
`NON_PROPOSITIONAL` items preserve their existing UID and content. The apply
checkpoint records the analysis UID and explicit `KEEP`, `PRESERVE`, and
`SPLIT` relations for later trace.

Saved source positions are ordinals within the direct-Memory frame, not slots
among every pointer in the Context. A read-only direct load may intentionally
leave an embedded `context_ref` unresolved while a mutating load restores it;
the unchanged Memories on either side must retain the same atomize identity
and order in both views.

In-place save creates one checkpoint and blocks only an inbound `memory_ref`
whose target Context UID is the selected Context and whose target Memory UID is
one of the sources that would be split. References to unchanged Memories do not
block it. Save-as does not remove those source Memories: it creates a fresh
Context UID, first records an init-like source baseline, then records the
atomized state, so references to the unchanged source Context remain valid.
The new Context is selected only after both states and the copied analysis have
been persisted. Ordinary failures remove the exact partial destination,
although no lock or crash-safe transaction journal spans all files.

Atomize also depends on two store-wide mutation invariants. A mutating load
must resolve every directly embedded Context pointer; otherwise saving the
partially loaded parent could silently erase an unavailable `context_ref`, so
the operation fails before changing the parent. When a normal Context write
raises after creating an automatic checkpoint, the store removes that exact
checkpoint and prunes only the empty namespace directories created by the
failed save. This is ordinary exception rollback, not a crash transaction: a
process or machine failure between the checkpoint and Context replacement can
still leave recovery work for a future transaction journal.

Saved atomize previews use the canonical Context UUID as their derived-artifact
key. Contexts created by current commands satisfy this requirement. A legacy
Context with a noncanonical identity can still be inspected and deleted, but
it cannot persist an atomize preview until its identity is migrated.

The actual apply path trusts the same one-shot semantic proposal after strict
local revalidation. It does not pretend that the proposal has passed an
independent semantic judge.

### Future independently validated plan

The semantic provider returns opaque call-local IDs. Real Context and Memory
UIDs remain in a local allowlist. Ruleset and profile identity are both part
of staleness: the plan fingerprints the named rules, locale profile, lint
thresholds, and sentence-like segmenter version. A validated immutable plan
records:

```json
{
  "ruleset_version": "atomize-v1-draft",
  "profile": {
    "id": "task1-campus",
    "version": "1",
    "locale": "ko-en",
    "segmenter_version": "sentence-like-v1",
    "fingerprint": "<canonical profile fingerprint>"
  },
  "context_uid": "<local context uid>",
  "context_fingerprint": "<content fingerprint>",
  "declared_frame": {
    "id": "<optional frame id>",
    "fingerprint": "<optional frame fingerprint>"
  },
  "items": [
    {
      "source_uid": "<local source uid>",
      "source_fingerprint": "<content fingerprint>",
      "source_position": 4,
      "classification": "COMPOSITE",
      "action": "SPLIT",
      "validation_status": "PASS",
      "reason_codes": ["A01_ONE_FOCUS", "A04_SOURCE_GROUNDED"],
      "ledger": ["<claim occurrence 1>", "<claim occurrence 2>"],
      "children": [
        {
          "content": "<source-grounded child 1>",
          "source_spans": ["<source span 1>"],
          "copied_scope_spans": []
        },
        {
          "content": "<source-grounded child 2>",
          "source_spans": ["<source span 2>"],
          "copied_scope_spans": []
        }
      ],
      "checks": {
        "coverage": "PASS",
        "no_invention": "PASS",
        "single_focus": "PASS",
        "self_contained": "PASS",
        "scope_preservation": "PASS",
        "occurrence_necessity": "PASS",
        "reconstruction": "PASS"
      }
    }
  ]
}
```

The profile fingerprint is SHA-256 over canonical sorted-key JSON of the
profile fields other than `fingerprint`. The ruleset itself receives a
separate digest when its rules move from this rationale into a loadable
artifact.

The stored child UIDs are allocated locally only after approval. Preview
creates no checkpoint. For an in-place application, the target design reloads
the Context, verifies every UID and fingerprint, checks all Contexts for an
inbound `memory_ref` that targets a planned split source in this Context, then
replaces each confirmed composite at its original position with contiguous
fresh children. Save-as preserves the source Context and therefore does not
need to retarget its inbound references.

One approved direct-Context batch creates exactly one checkpoint. The
checkpoint records the shared operation ID and:

```text
source UID and fingerprint
source position
ordered child UIDs and contents
source spans and copied qualifier spans
ruleset version and reason codes
```

Version 1 blocks an in-place application if any `memory_ref` targets a split
source in the selected Context. A one-to-many replacement has no single safe
automatic retarget. It does not block references to Memories that remain
unchanged, and save-as leaves all source targets intact. The first apply path
is explicitly single-writer. The current store has no global compare-and-swap
or lock spanning the inbound-reference scan, checkpoint, and Context
replacement, so it cannot promise concurrent safety. Multi-writer support
requires such a transaction boundary and a race test; it must not be inferred
from the stale-plan check alone.

## Golden regression contract

The machine-readable seed corpus is
`memcommit/eval/fixtures/atomize.json`. It adapts the clozemaking one-view
format as:

```text
source                      = original input
known_wrong                 = x> false split or under-split
expected.classification     = canonical semantic class
expected.result             = -> canonical ordered result
expected.qa                 = canonical source-occurrence Q/A ledger,
                              including source spans, predicate, speech act,
                              scope slots, and declared-frame IDs
```

The fixture includes:

- short but composite content;
- long but atomic content;
- an old-to-new transition that must not be split;
- condition, negation, alternative, and exception scope;
- a clear multi-claim split;
- unresolved deictic scope;
- non-propositional content;
- an explicit duplicate that atomization must preserve for deduplication.

The fixture-schema test is mechanical. Semantic regression later runs a
provider or agent on each source independently. Version 1 comparison is
deliberately deterministic:

- parse JSON with duplicate-key rejection and an exact schema;
- compare class, ordered reason codes, occurrence IDs, source spans, speech
  acts, focal predicates, scope slots, frame IDs, and child mapping exactly;
- compare result strings after only CRLF-to-LF conversion and Unicode NFC;
- accept another rendering only when a human reviewer adds it explicitly as
  an allowed golden variant.

No model grades another model's semantic equivalence. That would be circular.
Exact comparison is intentionally strict; a valid but differently worded
minimal repair first fails visibly, then a human decides whether to replace
the canonical rendering or add a narrow allowed variant. Every curated case
must pass; a percentage score does not make a known boundary failure
acceptable.

Implemented operation tests cover the current preview-and-apply boundary:

- all direct items receive exactly one semantic class and none disappear;
- for `n` inputs, `s` split sources, and child counts `c_i`, the result count is
  `n - s + sum(c_i)`;
- every child gets a fresh unique UID;
- split children are contiguous at the source position;
- unchanged UIDs, contents, and relative order remain stable;
- source-to-child UID lineage is recorded;
- preview creates zero Context checkpoints but updates one per-Context analysis
  artifact;
- in-place apply creates exactly one checkpoint;
- save-as leaves the source unchanged and creates exactly two destination
  checkpoints: source-based `init`, then `atomize`;
- stale Context identity/digest, source UID/content/position, or saved ruleset
  data causes zero mutation;
- an in-place apply is blocked when an inbound `memory_ref` targets a split
  source in the selected Context, while save-as leaves the source reference
  valid;
- embedded Contexts, `context_ref`, `memory_ref`, and query-only Context
  references are excluded from provider candidates in direct-only version 1;
- a query-only source loader patched to fail is never called during atomize;
- referenced target Memories are neither split nor checkpointed through the
  reference view;
- provider responses with unknown IDs, missing fields, extra fields, duplicate
  keys, or ungrounded spans are rejected as a whole.

Future independent-validator and semantic regression tests must additionally
cover:

- source occurrence coverage, reconstruction, single-focus, and scope
  preservation as independently judged checks rather than properties asserted
  by the proposal itself;
- an independently produced `UNKNOWN` validation result causes zero mutation;
- re-running the same ruleset on already applied children proposes no new clear
  split under a pinned provider/model contract.

Future metamorphic tests should verify:

- whitespace-only surface changes preserve the classification;
- swapping two independent conjuncts swaps child order but not membership;
- adding an explicit shared time qualifier propagates it to all children it
  clearly scopes;
- replacing that qualifier with undeclared `해당 기간` produces
  `UNCERTAIN`;
- adding negation, modality, a condition, or an exception does not detach that
  scope into a child fragment.

## Task 1 anchors

The following current sources are useful human-review anchors. Their UIDs are
not part of the portable fixture.

### Keep or protect from false splitting

- `정문은 원래는 10시까지 개방 - 5시로 단축.` is one old-to-new
  opening-hours relation.
- `시간 이후 출입증 학생카드 필요하다.` keeps the after-hours condition
  on the credential requirement.
- `엘리베이터는 내부에서는 계속 한 개씩 돌아가면서 운영할 수 있다.`
  keeps `한 개씩` as the operating constraint.
- `에어컨 잠시 차단될 수 있음. 5-10분 정도 안에 돌아올 예정이니 괜찮음.`
  is a candidate single outage commitment with modality and expected duration;
  two sentence boundaries alone are not enough to split it.
- A staff-access rule with an explicit underground-stairwell exception should
  retain the exception on the rule.

### Clear under-splitting signals

- Store closure, alternative-store guidance, and alternative-store extended
  hours are independently addressable.
- Restroom closure and the nearest alternative restroom are separate
  commitments.
- Stopping venue reservations and directing requesters to another building are
  separate commitments.
- Requesting item removal, confirming removal, and moving lost property are
  separate states or actions.
- Visitor eligibility, member guidance, public restroom guidance, and an
  urgent-use exception contain several audience-specific commitments.
- Outdoor-parking closure, the access reason, and the planned reopening are
  separately addressable, although a causal relation must not be reduced to a
  bare reason.

### `UNCERTAIN` or `NON_PROPOSITIONAL`

- `Main Building 여름방학 시설개선 공사 리스트` is a heading and is
  retained as `NON_PROPOSITIONAL`.
- `어떤 부분이 리포트되었는지 등등 말야.` is a process question, not a
  fact to invent.
- `수업 관련 이유로 오는 학생들은 적절히 말한다?` does not specify an
  action.
- `Main building cafe.` is an unresolved fragment even when a neighboring
  Memory mentions dining closure.
- `같은 nfc` requires an external antecedent; the atomizer must not take it
  from the preceding Memory silently.

Some long current sources also contain `해당 기간` or `앞서`. They may be
obviously composite to a human but are not safe to apply without a declared
frame. The preview can show the candidate commitments while the final class
remains `UNCERTAIN`.

### First live Task 1 preview observation

The first completed local run of:

```bash
mem impact atomize
```

against the 51 direct Memories in `temp/task-1` returned:

```text
51 direct Memories -> 68 projected
13 atomic, 10 composite, 13 uncertain, 15 non-propositional
10 proposed splits -> 27 children
```

These counts are an observation, not a golden expectation. The provider model
is not pinned and semantic results may vary between runs.

Several useful boundaries worked: the run proposed separate vehicle and
pedestrian-access claims, separated item-removal/request/confirmation/lost-item
occurrences, separated venue-booking closure from redirection, separated
restroom closure from its alternative location, and marked many sources with
`앞서`, `같은 NFC`, or missing antecedents `UNCERTAIN`.

The same run also exposed why that particular report should not be applied
without human review:

- the long Campus Store source was classified `COMPOSITE` even though one
  proposed child retained unresolved `해당기간`; under A06 the entire source
  should remain `UNCERTAIN` until that scope is declared;
- the source about a possible brief air-conditioning interruption and expected
  recovery within 5–10 minutes was split into outage, recovery, and
  `괜찮다`; this over-splits one focal outage/recovery commitment and turns an
  informal evaluation into a weak stand-alone Memory;
- a route source containing unresolved `이쪽 빌딩` was split instead of being
  blocked for local antecedent resolution.

These are semantic false approvals that pass the current structural parser.
They must become contrastive regression cases or validation checks only after
human review fixes their canonical outcomes. They are not justification for a
Korean keyword blacklist: A06 concerns whether a referent is locally resolved,
not whether a particular surface word appears. The observation instead
reinforces three existing decisions—unresolved scope takes precedence over a
visible split, focal relations must be preserved, and a separate semantic
validation pass is required before mutation.

The prompt was then strengthened with those two general precedence rules and
run again. The second observation was:

```text
51 direct Memories -> 61 projected
14 atomic, 7 composite, 15 uncertain, 15 non-propositional
7 proposed splits -> 17 children
```

This moved the Campus Store source and an incomplete ATM-guidance source to
`UNCERTAIN`, and the air-conditioning outage no longer appeared as a proposed
split. It did not solve every semantic boundary. The route source containing
`이쪽 빌딩` was omitted from the non-atomic output, indicating that unresolved
deixis can still be missed, and one item-removal split proposed the fragment
`확인했다` as a child even though it is not independently self-contained.
Prompt strengthening improves the sample but is not independent validation,
and run-to-run count changes are themselves evidence against treating one
completion as a deterministic golden result.

The first run using the implemented saved-preview/apply contract, on
2026-07-28, returned:

```text
51 direct Memories -> 54 projected
13 atomic, 3 composite, 20 uncertain, 15 non-propositional
3 proposed splits -> 6 children
```

It saved analysis `e2aceac3…` on `temp/task-1` and was explicitly applied with:

```bash
mem atomize --save-as temp/task-1-atomized
```

The original remained a 51-Memory Context with its two original checkpoints.
The new Context has 54 Memories and exactly two checkpoints: its source-based
baseline and the atomize application. The three applied splits were vehicle
versus pedestrian parking access, restroom closure versus nearest alternative,
and left-side accessible guidance versus the right-stair accessibility
constraint. Twenty incomplete or deictic items were preserved as `UNCERTAIN`
instead of being forced into children.

Trace confirmed both directions of the contract. The parking source UID
`42b4be11…` has a recorded init-from-source event followed by a recorded split
to two fresh child UIDs. The malformed student-card/app Memory
`f6fa696e…` has a recorded `ATOMIZE_PRESERVED` event, retains its UID and text,
and carries the applied `UNCERTAIN / RECONCILE` reason. This observation is not
a new golden count; it demonstrates that preview, source preservation,
application, and explanation are now connected by recorded identifiers.

## Function boundaries

The intended internal decomposition is:

```text
build_claim_ledger(source, declared_frame)
→ classify_atomicity(ledger)
→ propose_children(source, ledger)
→ validate_children(source, ledger, children)
→ immutable AtomizePlan
→ apply_atomize_plan(plan)
```

Candidate generation may use sentence boundaries, conjunctions, bullets, and
size lint. None of those heuristics may bypass the ledger and validation pass.

The implementation now separates the saved `mem impact atomize` preview from
the explicit `mem atomize --save` and `--save-as` transformations. It uses the
golden corpus as calibration and labels the absence of a second independent
semantic judge rather than silently implying one. The existing `mem chunk`
remains a deterministic text-splitting primitive; it is not renamed or treated
as this semantic operation.

## Intentional non-goals

Atomization does not:

- decide which duplicate should survive;
- resolve conflicting or missing scope;
- improve wording beyond minimal stand-alone repair;
- infer audiences or enforce access control;
- infer or choose a destination Context on the user's behalf (`--save-as`
  accepts an explicit name);
- read query-only source content;
- turn questions or headings into asserted facts;
- use neighboring Memory order as an implicit semantic graph.

These boundaries keep later stages attributable and testable.
