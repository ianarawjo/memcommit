# Distill and Elaborate generative reduction design rationale

Last updated: 2026-08-23.

## Motivating failure

Distill and Elaborate originally formed only a loose topical pair. Distill
asked for conditional policies or durable constraints, so it recovered
behavioral advice while discarding repeated actor phrases, grammatical
transitions, event order, and narrative form. Elaborate then linked each Case
to exactly one Rule. A `CONTRAST` proposition could violate that Rule while the
correct handling survived only in checkpoint metadata; standalone Add stored
the violating proposition as an ordinary Memory.

The concrete failure used three Korean café-order Example Memories. The old
Distill output recovered clarification, minimal change, and final confirmation,
but omitted the repeated third-person sequence beginning with `한 고객이` and
transitioning to `바리스타는`. The old Elaborate output assigned three Cases
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

Elaborate is whole-Rule-set generation:

```text
Rule Memories --Elaborate--> suggested Example Memories
```

Every generated Case is a self-contained positive Example Memory that jointly
instantiates every input Rule. Cases vary legitimate slots while preserving
required roles, relations, order, boundaries, and form. `FIT`, `BOUNDARY`, and
`CONTRAST` remain proposal roles, but all three propositions must comply with
the complete Rule set. A CONTRAST may make a tempting alternative visible in
its rationale or expected handling; the stored proposition itself is never the
Rule violation.

These operations are not mathematical inverses. A later Distill turn may split
or combine equivalent invariants differently. The required property is
semantic family preservation: reviewed anchors remain recoverable and every
Elaborated Example visibly implements the full input frame.

## Quoted three-family reference corpus

`memcommit/eval/fixtures/distill_elaborate.json` is the authored calibration
and prompt-reference source. It stores complete Rule and Example Memory texts
for three unrelated families:

- English café orders with one constrained adjustment and clarification;
- English lost-property reports with successful and unsuccessful branches; and
- language-mixed Cloze entries with exact labels and wrapper notation.

The Distill case maps three English café Example Memories to seven reviewed Rule
Memories covering viewpoint/order, opening actor, base attributes, one scoped
adjustment, barista subject transition, two-option clarification plus customer
selection, and final confirmation before preparation. The Elaborate case maps
those seven Rules to three complete café Example Memories, each of which
implements all seven.

Exact prose is the deterministic decoder fixture, not the live-provider quality
oracle. Live evaluation checks semantic anchors and complete Rule coverage.
This distinction permits equivalent wording without accepting the former
three-Rule behavioral subset as complete.

Every production generation prompt quotes all three complete bidirectional
families. Distill reads each pair as `Example Memories -> Rule Memories`.
Rules-to-Cases Elaborate reads the same pairs in reverse. Goal-to-Rules
Elaborate uses the Rule sides as examples of independently reviewable,
generative Rule form and the paired Examples as a demonstration of why those
Rules are operational. The reference block is therefore present in every
Distill and Elaborate generation call rather than existing only in tests.
Elaborate's later Conformance and Fit turns instead receive only the exact
current Source Rule and generated Case frames required by those shared
judgment contracts.

Prompt reference and execution evidence remain distinct. The authored
reference families have no current-run Memory aliases. Distill may populate
`support_memory_ids` and `boundary_memory_ids` only from the explicitly
selected Source; Elaborate `rule_checks` refer only to its current input
Rules. This permits literal few-shot quotation without fabricating provenance
or treating the café, lost-property, or Cloze corpus as evidence about an
unrelated current Context. The complete reference block is included in
whole-frame input budgeting.

## Existing Target as Elaborate ambient context

The packaged three-family corpus and an existing command Target serve different
roles. The corpus is fixed method calibration quoted in every turn. An exact
Elaborate Target is run-specific ambient context: it can teach the next Rule or
Example the destination's already established terminology and form, but it is
not another Goal or Rule and cannot satisfy a current `rule_checks` obligation.
Every proposal separately reports the Target aliases it materially used.

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
hidden side effect of this Elaborate change.

## Typed Elaborate coverage

The former scalar `source_rule_index` is replaced by ordered `rule_checks`.
Every Case must provide exactly one nonempty evidence statement for every
source Rule index, in input order. JSON Schema fixes the array length to the
input count, and the local decoder independently rejects omissions,
duplicates, reordering, and unavailable indexes. The evidence must identify
observable content in the proposition according to the provider instruction.

Structural coverage alone is not acceptance evidence because the generator
can make a mistaken semantic claim. Rules-to-Cases now follows generation with
two independent judgment turns over complete frames. Context Conformance must
classify every generated Case as conforming to every Source Rule; general Fit
must return `YES` for each Case together with the complete Source frame. Any
violation, non-applicability, insufficient evidence, Fit `NO`, or Fit `MAY`
fails the operation before result publication. The operation preserves the
requested exact count and does not silently drop or regenerate failed Cases.

Neither judgment establishes truth or evidential support. A concrete value may
be absent from Source and still pass when it legitimately instantiates the
Rules and introduces no contradiction. Cases therefore remain `SUGGESTED` and
`UNVERIFIED`. Provider contract version 10 prevents earlier generation-only
analyses from replaying without accepted Conformance and Fit evidence. Agent
contract version 4 exposes the same per-Case evidence.

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
- Relying on generator-authored `rule_checks` as verification was rejected.
  Elaborate instead composes the shared Conformance and general Fit contracts
  after generation, while retaining `UNVERIFIED` for truth and evidence.
- Allowing reference Memories to appear as current evidence was rejected
  because a demonstration cannot establish a Rule about the selected Source.
- Injecting all readable Profile Contexts into Elaborate was rejected; only the
  exact frozen Target is destination context.
- Treating Target ambient Memories as current Rules was rejected; Source inputs
  remain authoritative and Target use has its own typed trace.
- Distill authority, target freezing, Add atomicity, and unverified storage
  status remain unchanged.

The three-family corpus is consumed calibration, not an independent holdout.
A future campaign still needs independent domains before claiming broad
generalization.

## Lost-property procedural calibration

The lost-property family prevents the café demonstration from being the only
procedural pattern. Three English Examples preserve exact sentence openings,
neutral third-person past-tense narration, a log-and-item check, and a
conditional terminal outcome. Two Examples verify a concealed detail before
returning an item; one records contact details after no match. Its Rules
therefore demonstrate that Distill may recover a shared conditional branch
rather than incorrectly requiring every Example to end in the same outcome,
and that Elaborate can instantiate one valid branch while complying with the
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
