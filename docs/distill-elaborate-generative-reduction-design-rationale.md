# Distill and Elaborate generative reduction design rationale

Last updated: 2026-08-20.

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

## Café calibration artifact

`memcommit/eval/fixtures/distill_elaborate.json` is the authored calibration
source. It contains actual, complete Korean Memory texts rather than labels
such as “three Examples” or “seven Rules.” Each operation has one regression
case with:

- the exact input Memory set;
- a known-wrong `x>` equivalent captured from the former contract; and
- the reviewed `->` equivalent.

The Distill case maps three café Example Memories to seven reviewed Rule
Memories covering viewpoint/order, opening actor, base attributes, one scoped
adjustment, barista subject transition, two-option clarification plus customer
selection, and final confirmation before preparation. The Elaborate case maps
those seven Rules to three complete café Example Memories, each of which
implements all seven.

Exact prose is the deterministic decoder fixture, not the live-provider quality
oracle. Live evaluation checks semantic anchors and complete Rule coverage.
This distinction permits equivalent wording without accepting the former
three-Rule behavioral subset as complete.

## Typed Elaborate coverage

The former scalar `source_rule_index` is replaced by ordered `rule_checks`.
Every Case must provide exactly one nonempty evidence statement for every
source Rule index, in input order. JSON Schema fixes the array length to the
input count, and the local decoder independently rejects omissions,
duplicates, reordering, and unavailable indexes. The evidence must identify
observable content in the proposition according to the provider instruction.

This is structural coverage, not independent truth verification. A provider
can still make a mistaken semantic claim, so Cases remain `SUGGESTED` and
`UNVERIFIED`; the calibration fixture and configured-provider trial supply the
review evidence. Provider contract version 3 prevents prepared version-2
single-Rule Cases from replaying under the joint-coverage meaning. The public
agent contract advances to version 2 because its Case projection now contains
`rule_checks` rather than one scalar source index.

## Configured-provider observation

Against the reviewed seven café Rules, the first configured-provider run after
the contract change returned three Cases (`FIT`, `BOUNDARY`, and `CONTRAST`).
Every Case was a complete Korean Memory and contained seven ordered Rule checks.
All three began with `한 고객이`, moved to `바리스타는`, supplied a concrete
base order, changed one attribute after a two-option clarification, preserved
the remaining attributes, and ended with confirmation before preparation.

After the mandatory surface-form audit was added, a configured-provider run
over the three reviewed café Examples returned eight Rules. The provider
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
- Making Elaborate its own verifier was rejected. Rule checks expose coverage;
  reviewed fixtures and later judgment establish quality.
- Goal-to-Rules Elaborate, Distill authority, whole-frame planning, target
  freezing, Add atomicity, and unverified storage status are intentional
  non-goals of this semantic revision and remain unchanged.

The café corpus is consumed calibration, not an independent holdout. A future
campaign should add unrelated domains before claiming broad generalization.

## Cloze surface-form calibration

The same fixture contains a compact, unrelated Cloze family. Each complete
Memory has `EXAMPLE`, `CLOZE`, and `뜻 설명` sections. The first two sections
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
