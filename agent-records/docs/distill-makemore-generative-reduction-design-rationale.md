# Distill and Makemore generative reduction design rationale

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

Last updated: 2026-08-23.

## Motivating failure

Distill and Makemore originally formed only a loose topical pair. Distill
asked for conditional policies or durable constraints, so it recovered
behavioral advice while discarding repeated actor phrases, grammatical
transitions, event order, and narrative form. Makemore then linked each Case
to exactly one Rule. A `CONTRAST` proposition could violate that Rule while the
correct handling survived only in checkpoint metadata; standalone Add stored
the violating proposition as an ordinary Memory.

The concrete failure used three Korean café-order Example Memories. The old
Distill output recovered clarification, minimal change, and final confirmation,
but omitted the repeated third-person sequence beginning with `한 고객이` and
transitioning to `바리스타는`. The old Makemore output assigned three Cases
to source Rules 5, 3, and 6 rather than treating each Case as one joint model
of all seven Rules. Its CONTRAST Case skipped the required clarification.

## Operation meanings

Distill is an evidence-bound generative reduction:

```text
Example Memories --Distill--> reusable Rule Memories
```

It recovers the smallest complete set of independently reviewable invariants
needed to generate, recognize, or distinguish another Example from the same
family. Relevant invariants may be behavioral, relational, sequential, or
presentational. Presentation includes the shared language and language-mixing
pattern, register, tone, formality, person, viewpoint, tense, voice, exact
opening or closing expression, labels and their order, sentence structure,
markup, placeholders, delimiters, capitalization, and punctuation. These are
not cosmetic when another family member must reproduce them. Instance-specific
values become slots; an exact repeated actor phrase or subject transition is
retained when it is part of the recurring family structure. A topic label such
as “these are about writing” is not a Rule by itself because it cannot generate
or distinguish an Example.

A surface-form Rule has a stricter evidence boundary than a semantic summary.
Every cited support must literally exhibit an asserted exact form in the
claimed position. If a particle, inflection, label, or punctuation form varies,
the Rule records the observed alternatives. It may state a conditioning
relationship only when the Source frame itself supports that relationship;
Distill must not infer a hidden linguistic cause or assign a form to a Source
that does not literally contain it. A majority pattern is not universal, and
one Source cannot be both support and boundary for the same Rule. A mechanical
consequence of another Rule is omitted unless it independently constrains
generation or recognition.

Makemore is whole-Rule-set generation:

```text
Rule Memories --Makemore--> suggested Example Memories
```

Every generated Case is a positive Example Memory. Individually applicable
Rules constrain that member directly; family-level seeds, ordering, position,
and recurrence instead constrain the ordered collection. Cases vary legitimate
slots while preserving required roles, relations, order, boundaries, and form.
`FIT`, `BOUNDARY`, and `CONTRAST` remain proposal roles, but the complete
collection must comply with every Rule and no stored proposition may be a Rule
violation. A CONTRAST may make a tempting alternative visible in its rationale
or expected handling; the stored proposition itself is never the alternative.

These operations are not mathematical inverses. A later Distill turn may split
or combine equivalent invariants differently. The required property is
semantic family preservation: reviewed anchors remain recoverable and every
Makemore Example visibly implements the full input frame.

## Quoted three-family reference corpus

`memcommit/eval/fixtures/distill_makemore.json` is the authored calibration
and prompt-reference source. It stores complete Rule and Example Memory texts
for three unrelated families:

- English café orders with one constrained adjustment and clarification;
- English lost-property reports with successful and unsuccessful branches; and
- language-mixed Cloze entries with exact labels and wrapper notation.

The Distill case maps three English café Example Memories to seven reviewed Rule
Memories covering viewpoint/order, opening actor, base attributes, one scoped
adjustment, barista subject transition, two-option clarification plus customer
selection, and final confirmation before preparation. The Makemore case maps
those seven Rules to three complete café Example Memories, each of which
implements all seven.

Exact prose is the deterministic decoder fixture, not the live-provider quality
oracle. Live evaluation checks semantic anchors and complete Rule coverage.
This distinction permits equivalent wording without accepting the former
three-Rule behavioral subset as complete.

Every production generation prompt quotes all three complete bidirectional
families. Distill reads each pair as `Example Memories -> Rule Memories`.
Rules-to-Cases Makemore reads the same pairs in reverse. Goal-to-Rules
Makemore uses the Rule sides as examples of independently reviewable,
generative Rule form and the paired Examples as a demonstration of why those
Rules are operational. The reference block is therefore present in every
Distill and Makemore generation call rather than existing only in tests.
Strict Makemore's later Conformance and Fit turns instead receive the exact
current Source Rule frame, materially referenced Target Memories, and generated
Cases required by those shared judgment contracts. Best-effort stops after the
generation turn.

Prompt reference and execution evidence remain distinct. The authored
reference families have no current-run Memory aliases. Distill may populate
`support_memory_ids` and `boundary_memory_ids` only from the explicitly
selected Source; Makemore `rule_checks` refer only to its current input
Rules. This permits literal few-shot quotation without fabricating provenance
or treating the café, lost-property, or Cloze corpus as evidence about an
unrelated current Context. The complete reference block is included in
whole-frame input budgeting.

## Existing Target as Makemore ambient context

The packaged three-family corpus and an existing command Target serve different
roles. The corpus is fixed method calibration quoted in every turn. An exact
Makemore Target is run-specific ambient context: it can teach the next Rule or
Example the destination's already established terminology and form, but it is
not another Goal or Rule and cannot satisfy a current `rule_checks` obligation.
Every proposal separately reports the Target aliases it materially used.
For an ordered family, those referenced Target Memories are the existing
prefix and the proposed Cases are the suffix. Generation must continue after
the final applicable member rather than replay seeds. Exact normalized content
equality with any frozen Target Memory is rejected locally before validation or
publication; this does not attempt general semantic deduplication.

Only the exact Target graph is eligible. Profile-wide automatic injection was
rejected because unrelated readable Contexts would change generation, consume
the one-shot budget, and cross downstream authority boundaries without a
selection. Direct Memories and local embeds are frozen recursively with cycle
and logical-Memory deduplication. QUERY-only routes contribute a public name
only. Granted embedded content additionally requires effective `READ`, `EMBED`,
`DERIVE`, and `COMBINE`; a revocation, narrower override, identity replacement,
or content drift fails closed. Direct Add additionally requires `EXPORT` and
`SAVE_ANALYSIS` before provider connection, while read-only Impact and Ground
proposal routes do not claim those retention capabilities. If Source and
Target are the same Context, the direct Source Memories are not repeated in
the ambient role.

This behavior is intentionally asymmetric with Distill for now. Distill still
asks what the selected Example Source supports. Existing destination Rules may
later guide novelty or reconciliation, but suppressing a supported Rule merely
because a similar Target Rule exists would combine reduction with Dedun. That
separate decision is deferred and recorded rather than being introduced as a
hidden side effect of this Makemore change.

## Typed Makemore coverage

The former scalar `source_rule_index` is replaced by ordered `rule_checks`.
Every Case must provide exactly one nonempty evidence statement for every
source Rule index, in input order. JSON Schema fixes the array length to the
input count, and the local decoder independently rejects omissions,
duplicates, reordering, and unavailable indexes. The evidence must identify
observable content in the proposition or that member's observable position and
contribution within the ordered collection.

Structural coverage alone is not acceptance evidence because the generator
can make a mistaken semantic claim. Default Rules-to-Cases intentionally treats
that output as best-effort: it stops after one complete generation turn,
retains `rule_checks` as generator-authored rationale, and publishes the exact
count as `SUGGESTED` and `UNVERIFIED`. It does not run a judgment that it then
hides or ignores.

Explicit strict Rules-to-Cases follows generation with two independent judgment
turns over complete frames. Context Conformance must classify every Source Rule
as `CONFORMS` over referenced Target Memories plus generated Cases, and every
new Case must be a conforming governed member even when different Rule subsets
apply to different positions. General Fit must return one `YES` for the complete
Source/Target-prefix/generated-Case frame. Any partial conformance, violation,
non-applicability, insufficient evidence, Fit `NO`, or Fit `MAY` fails strict
publication. Neither policy silently drops or regenerates Cases.

Neither judgment establishes truth or evidential support. A concrete value may
be absent from Source and still pass when it legitimately instantiates the
Rules and introduces no contradiction. Cases therefore remain `SUGGESTED` and
`UNVERIFIED`. Provider contract version 10 prevents earlier generation-only
analyses from replaying without accepted Conformance and Fit evidence.
Provider contract version 11 records the collection-level validation unit and
Target-prefix continuation boundary. Version 12 teaches generation to
distinguish conjunctive record schemas from sibling, conditional, diagnostic,
and collection parents. Version 13 makes best-effort the explicit default and
binds optional strict evidence to the analysis. Agent contract version 5
exposes the quality policy and nullable per-Case evidence.

## Configured-provider observation

Against the then-Korean reviewed seven café Rules, the first
configured-provider run after
the contract change returned three Cases (`FIT`, `BOUNDARY`, and `CONTRAST`).
Every Case was a complete Korean Memory and contained seven ordered Rule checks.
All three began with `한 고객이`, moved to `바리스타는`, supplied a concrete
base order, changed one attribute after a two-option clarification, preserved
the remaining attributes, and ended with confirmation before preparation.

After the mandatory surface-form audit was added, a configured-provider run
over the then-Korean three reviewed café Examples returned eight Rules. The provider
recovered the behavioral sequence and separately recovered Korean language,
past-tense third-person indirect narration, the exact
`한 고객이 → 바리스타는 → 고객은 → 바리스타는` actor sequence, the
three-sentence single-paragraph shape, absence of headings and direct quotation,
formal neutral service-report tone, and repeated event verbs. Seven Rules cited
all three Examples as support; the customer-selection surface variant used two
supports and one boundary. No Source was outside and Impact left both endpoints
unchanged.

The balanced Cloze fixture initially exposed a second literal-grounding failure:
the provider correctly proposed the observed `은`/`는` alternative but then
assigned `shelter` the unobserved form `shelter은`. After conditioning claims
were limited to conditions present in the Source frame, a configured-provider
rerun returned six Rules. It recovered section order and blank lines, exact
single-wrapper transformation, part-of-speech and position variation,
English/Korean section language, contextual Korean declarative explanation, and
the observed `은`/`는` alternatives without inventing a target-specific mapping
or a redundant subject-preservation Rule. Impact again left three Source and
zero Target Memories with no checkpoint.

## Boundaries and rejected alternatives

- Keeping `source_rule_index` and relying on prompt prose was rejected because
  partial Cases remained structurally valid to every adapter.
- Treating presentation form as always incidental was rejected because it made
  reviewed Example families unreconstructable.
- Requiring byte-identical Distill output was rejected because equivalent Rule
  decompositions can split or combine anchors without semantic loss.
- Treating generator-authored `rule_checks` as verification was rejected.
  Best-effort retains them only as rationale; explicit strict mode composes the
  shared Conformance and general Fit contracts after generation. Both policies
  retain `UNVERIFIED` for truth and evidence.
- Allowing reference Memories to appear as current evidence was rejected
  because a demonstration cannot establish a Rule about the selected Source.
- Injecting all readable Profile Contexts into Makemore was rejected; only the
  exact frozen Target is destination context.
- Treating Target ambient Memories as current Rules was rejected; Source inputs
  remain authoritative and Target use has its own typed trace.
- Distill authority, target freezing, Add atomicity, and unverified storage
  status remain unchanged.

The three-family corpus is consumed calibration, not an independent holdout.
`memcommit/eval/fixtures/distill_makemore_holdout.json` therefore freezes four
prompt-unseen families: mixed English/Korean subfamilies, ordered Fibonacci
continuation, operational cleanliness hierarchy, and diagnostic cleanliness
hierarchy. Production reference loading never reads that file, and regression
tests assert that neither its case identifiers nor its authored parent texts or
acceptance readings enter the quoted prompt. This supplies a repeatable
generalization check; four families are still not evidence of broad domain
coverage.

## Parent/child prompt-generalization observation

The motivating failures were semantic rather than missing domain branches in
Python. Before the prompt change, mixed-subfamily Distill already recovered
separate English and Korean Rules, and Fibonacci Distill recovered recurrence,
but cleanliness Distill produced only lower formatting and item Rules. A
Fibonacci continuation Makemore over the existing prefix `0 ... 34` generated
a proposal but failed collection validation with recurrence Rule 2 marked
`INSUFFICIENT_EVIDENCE`. A combined cleanliness Rule frame also failed because
a generated dish-mark diagnostic child correctly conformed to the diagnostic
Rule while violating the independent normative clean-dish Rule.

The revised prompt teaches relationships, not answers. Distill treats each Rule
as a parent relative to cited children, audits supported subsets and ordered
collections, and performs one final governing-parent audit for a coherent
normative Source. Makemore distinguishes conjunctive record schemas from
sibling parents, keeps every parent visible in `rule_checks`, and requires an
ordered prefix's references to establish the proposed suffix's lineage. No
Fibonacci values or cleanliness fixture sentences appear in the production
reference corpus.

On 2026-08-24, the configured `codex_chatgpt` Study provider produced these
prompt-unseen results through the real Impact application paths:

- Fibonacci continuation changed from a failed 20.27-second run to a completed
  29.12-second run proposing exactly `55, 89, 144, 233, 377` after `34`. The
  final run used the clean ten-Memory `fibonacci/holdout-prefix`; a separately
  modified interactive prefix was not treated as holdout evidence.
- Mixed-subfamily Makemore completed with three new English and three new
  Korean children, without replaying its six-member Target prefix.
- Operational cleanliness Distill retained the three criteria and added one
  parent supported by all three; its final prompt produced three focused
  sibling children rather than repeating every criterion inside every child.
- Diagnostic cleanliness Distill joined dish residue and insect observation
  under one inadequate-cleanliness parent, and Makemore produced conforming
  negative-state children for each condition.
- Elaborating the newly distilled operational parent produced new focused
  children for visible-residue removal, contamination prevention, and
  pre-threshold waste removal. Their wording did not reproduce the original
  children, preserving the intentional non-inverse boundary.

The interactive inputs were retained under
`practice/eval/{mixed,fibonacci,cleanliness}`. Cleanliness deliberately has
separate `operational-rules`, `positive-examples`, `diagnostic-rules`, and
`diagnostic-examples` Contexts in addition to the combined failure frame. These
Context paths organize reproducible inputs; lexical Context ancestry is not a
parent/child proposition edge.

The combined normative-plus-diagnostic cleanliness frame remains a deliberate
limitation. Prompt changes cannot make one dish-mark proposition both conform
to "dishes must be mark-free" and serve as its counterexample. Supporting that
single-frame graph requires a typed counterexample or diagnostic relation in
the Conformance-under-Fit model. The current public projection also still says
`ALL N RULES` because typed validation retains the complete Rule-index set even
when the provider and Conformance judgment used applicable subsets. Both are
structural follow-ups rather than reasons to hard-code the holdout domains.

## Goal-selected reduction topology

A later real-review evaluation exposed a tension in the version-9 instructions:
the prompt called the Goal a relevance focus while also requiring every audited
surface-form axis in the output and preferring that completeness over Rule-count
minimization. Five full Korean café reviews therefore produced useful global and
subset assessment parents, but also returned date, first-person, and platform
metadata Rules under a semantic customer-experience Goal. The complete nine-Rule
output was only 1.62:1 smaller by characters, although its single governing
parent was 9.64:1 smaller.

Version 10 resolves the instruction conflict with one domain-neutral ordered
procedure. The natural-language Goal selects intended use, hierarchy, exact or
maximum Rule quantities, exclusions, and modality after the provider has read
the complete Source and enumerated supported candidates. Reconciliation removes
subsumed paraphrases and retains a lower parent only when it changes generation,
recognition, classification, or a decision boundary. Surface form remains part
of analysis and remains output-relevant for no-Goal or reproduction Goals, while
a semantic Goal may exclude it. Literal character ratio is deliberately only a
reported metric: compactness is controlled through topology and nonredundancy so
a numeric compression target cannot silently erase conditions or minority
boundaries.

The cumulative live campaign ran in a separate ordinary evaluation Profile so
the retained Study Profile's pinned `reasoning=none` route remained unchanged.
Every call used `codex_chatgpt`, `gpt-5.6-sol`, and `reasoning=xhigh`. The three
prompt-visible calibration families returned the complete reviewed café,
lost-property, and Cloze decompositions with 7, 6, and 4 Rules respectively.
The four prompt-unseen families returned the required mixed-subfamily parents,
Fibonacci recurrence and numeral form, operational-cleanliness hierarchy, and
diagnostic-cleanliness hierarchy. The interactive coffee family returned one
four-Source governing parent plus three subject-specific Rules without a
sentence-form Rule.

For the five full Korean reviews, the same Source produced different supported
topologies solely through the natural-language Goal. A general semantic Goal
returned five content criteria and no review-form Rules. A contract requesting
one assessment parent plus at most three supporting criteria returned exactly
four Rules and no unsupported duty. A reproduction Goal returned eleven content
and form Rules, including bounded optional update and platform metadata. An
operating-criteria Goal returned only food/drink, space, and staff criteria and
did not invent installation or purchasing Tasks. The 839-character Source
became 310 characters under the general five-Rule result (2.71:1) and 301
characters under the four-Rule topology (2.79:1). These are whole-result
measurements; selecting only one governing parent would report a larger ratio
but would conceal the requested supporting topology.

The cumulative Goal cases are frozen separately in
`memcommit/eval/fixtures/distill_goal_holdout.json`. This fixture records the
complete translated review Memories, their CC0 dataset provenance and sampling
seed, the exact natural-language Goals, and semantic acceptance readings. It is
not loaded by the production prompt.

## Lost-property procedural calibration

The lost-property family prevents the café demonstration from being the only
procedural pattern. Three English Examples preserve exact sentence openings,
neutral third-person past-tense narration, a log-and-item check, and a
conditional terminal outcome. Two Examples verify a concealed detail before
returning an item; one records contact details after no match. Its Rules
therefore demonstrate that Distill may recover a shared conditional branch
rather than incorrectly requiring every Example to end in the same outcome,
and that Makemore can instantiate one valid branch while complying with the
complete conditional Rule set.

## Cloze surface-form calibration

The same fixture contains a compact, unrelated Cloze family. Unlike the English
café family, it intentionally remains language-mixed because that surface form
is the calibration target. Each complete Memory has `EXAMPLE`, `CLOZE`, and
`뜻 설명` sections. The first two sections
are English, the explanation is Korean, and the only Example-to-Cloze change is
one `{{c1::...}}` wrapper. Verb, adjective, and noun targets prevent an
accidental majority pattern from becoming a false part-of-speech Rule.

The observed failure motivating the stricter surface audit produced a Rule
requiring the literal particle `는` even though one support contained
`fragile은`; it also repeated subject preservation as a separate Rule even
though exact sentence copying already entailed it. The reviewed fixture instead
requires only the observed `은`/`는` alternatives and rejects both an invented
pronunciation mapping and mechanically redundant surface Rules. This is
consumed calibration, not proof that provider claims are independently true;
local decoding still validates structure rather than natural-language
entailment.
