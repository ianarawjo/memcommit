# `mem check-conformance` design rationale

## Motivation

Distill can propose reusable Rules from examples or ordinary Context evidence,
but evidence coverage alone does not prove that the proposed Rules reproduce
the examples or that another Context follows them. The ticker evaluation made
the distinction concrete: all twenty examples were cited, yet one Rule's claim
about preserving `AI` was stronger than the example `Axiom AI Technologies →
AAT` supported.

Conformance is therefore a separate read-only semantic operation. It is
available directly through `mem check-conformance` and as an optional fifth
section of a multi-Memory `mem audit`. Both adapters call the same typed core; Audit does not
invoke the CLI command as a subprocess or reinterpret its rendered text.

## Rule/Context Conformance

```text
Rules Context + Target Context -> one Conformance judgment per Rule
```

`mem check-conformance TARGET --against RULES` treats every direct Memory in
the Rules Context as one Rule and every direct Memory in the Target as evidence.
Each Rule receives exactly one `CONFORMS`, `VIOLATES`,
`PARTIALLY_CONFORMS`, `NOT_APPLICABLE`, or `INSUFFICIENT_EVIDENCE` judgment.
Every Target Memory must be cited by at least one Rule judgment or explicitly
placed outside the judgments. Absence of evidence is not conformance.

`mem check-conformance --ground NAME` uses the same contract. It projects the
physical Ground's active Rule Memories and Example proposition Memories into
one frozen Rule/Context frame; it does not reconstruct hidden inputs or
expected outputs. Fit independently judges the same proposition-shaped
Examples with its `YES`/`MAY`/`NO` compatibility contract.

The command exposes the same Target and Rules roles through three equivalent
vocabularies:

```text
mem check-conformance TARGET --against RULES
mem check-conformance --rule RULES --example TARGET
mem check-conformance --rule RULES --case TARGET
mem check-conformance --from RULES --to TARGET
mem check-conformance --from UID_OR_PREFIX
mem check-conformance --from "literal Rule proposition"
```

`Example` is the canonical term for a concrete proposition. `--case` remains a
CLI vocabulary alias for the same Target Context slot; it does not select a
Case replay engine or a second report mode. `--from` always names the Rules
source and `--to` the Context being judged. If exactly one option-qualified
role is omitted, the command-start current Context supplies it, matching the
shared endpoint convention. The positional Target does not by itself infer a
Rules Context, so an incomplete command remains an error.

Aliases are one semantic slot rather than independent inputs. Repeating a
Rules alias or a Subject alias, or combining the positional Target with a
Subject alias, fails before Context loading or provider connection. This avoids
order-dependent last-value-wins behavior and preserves one command-start
locator snapshot for both resolved names. `--ground` remains a separate bundled
Rules-plus-Examples route and cannot be combined with any direct endpoint.

The Target side remains one complete local direct Context frame. The Rules
slot additionally accepts one direct ordinary Memory UID/prefix or one literal
Rule proposition, so a caller need not create a one-Memory Rules Context merely
to run an ad hoc check. Automatic classification follows the general Fit
grammar: `text:VALUE` forces literal text; an eight-or-more-character
UUID-shaped value or `CONTEXT:UID_OR_PREFIX` is a strict Memory selector; an
existing local Context keeps its Context meaning; and a shorter hexadecimal
value becomes a Memory selector only when the complete local direct-owner
catalog has one unique match. Remaining non-relative text is a literal Rule. A
relative locator that resolves to no local Context is an error rather than
silently becoming Rule text. A literal colliding with a Context name or matched
UID prefix must use `text:`.

Bare Memory selectors use the shared direct-Memory locator and must have one
unique owner across all ordinary local Contexts. The current Context receives
no hidden lookup priority. The selected Memory retains its real UID and is
revalidated by owner identity, exact UID, and content digest after the provider
turn. Literal text receives only a deterministic process-local Rule UUID for
typed frame linkage; this does not fabricate a durable Memory or provenance
claim. The compact source label distinguishes these forms as
`RULES MEMORY CONTEXT:UID` or `RULES TEXT VALUE`.

The preceding Context-versus-Memory classification is the common
`context_targeting` typed operand parser used by the other mixed-target CLI
routes. Conformance retains only its operation-specific `text:` escape,
literal Rule fallback, and Source-role validation.

The provider also returns the exact counterexample subset for every
`VIOLATES` or `PARTIALLY_CONFORMS` judgment. A violating judgment's cited
evidence is entirely nonconforming; a partial judgment has both conforming and
nonconforming cited Examples. The host validates those relations rather than
trying to recover counterexamples from explanatory prose.

Conformance contract version 2 strengthens two parts of that result. First,
each Rule must cite every target Memory to which it applies or plausibly
applies. Omission from one Rule judgment now means that Rule does not govern
that Example; a Memory in the report-wide outside set is governed by no
supplied Rule. Second, every clear counterexample carries its own compact
single-sentence reason. A Rule-wide reason cannot safely explain several
different failures when each Example breaks a different clause.

These relations let the host derive one whole-Rules status per Example without
asking the provider for a second potentially inconsistent judgment list:

- any exact counterexample makes the Example `VIOLATES`;
- otherwise, any applicable `INSUFFICIENT_EVIDENCE` Rule makes it unresolved;
- otherwise, applicable conforming evidence makes it `CONFORMS`; and
- a Memory governed by no Rule is `NOT_APPLICABLE`.

Violation takes precedence because one failed applicable Rule is enough to
exclude an Example from the conforming numerator. In the absence of a
violation, unresolved applicability takes precedence over positive evidence;
the host must not count a partly undecidable Example as conforming. Rule and
Example `N/A` rows are excluded from their respective denominators and counted
separately.

Conformance schema version 4 is the sole runtime report shape. It stores each
counterexample identity together with its exact reason and has no mode or Case
judgment fields. Versions 1–3 and the exact-output Case contract were removed
rather than migrated because the prototype had not been distributed and no
durable compatibility promise existed. Historical captures remain evidence of
the discarded experiment, not readable runtime receipts.

### Asymmetric compact terminal receipt

The direct Context projection follows Fit's compact receipt grammar rather
than a result-workbench overview. A clean result is exactly one logical line:

```text
CONFORMANCE · 26/26 EXAMPLES CONFORM · 1/1 RULES MET · [EXAMPLES practice/1] · [RULES practice/2]
```

`EXAMPLES CONFORM` names the judged Target side. `RULES MET` is deliberately
asymmetric: Rules do not themselves conform; the applicable target evidence
meets them. A report-wide provider-authored overview, `WHAT MEM UNDERSTOOD`,
and `ASSESSMENT OVERVIEW` are absent from this projection because a clean
sentence such as “all 26 match” merely repeats the two fractions and verdict.
The serialized `overview` field remains as a deterministic host summary for
schema and Audit compatibility; the provider no longer authors it.

Only a nonconforming or unresolved relationship adds another logical line. A
clear counterexample is Example-first and keeps its exact reason inline:

```text
! VIOLATES · [EXAMPLE m000014] A Is apple · [RULE r1] Use lowercase letters. · WHY · “A” is uppercase; r1 requires a lowercase letter.
```

An `INSUFFICIENT_EVIDENCE` relationship uses the same one-line shape and a
`?` marker. `NOT_APPLICABLE` contributes only to the compact `N/A` counts; it
is not an issue row. Each untrusted name, body, and reason is display-escaped
so embedded newlines and controls cannot create a fabricated second result
line. A terminal may visually wrap one long logical line at its viewport edge;
the renderer itself does not add a continuation line, separate `WHY` row,
blank separator, or failure-section heading.

The typed report still retains complete Rule judgments, all applicable
evidence identities, exact outside identities, aggregate reasons, provider
identity, and case-specific reasons. Compact presentation therefore does not
weaken coverage or turn absence of a visible issue into proof of general
correctness.

The Target Context and any Rules Context locator are resolved from one
command-start snapshot and revalidated after the provider turn. Descendant,
embedded, and granted frames remain out of scope; they require explicit scope
and retained-analysis authority contracts before rollout.

## Audit composition and compatibility

Normal `mem audit --context TARGET` runs its three independent quality checks
and, when the frozen Source has at least two Memories, one whole-Context Fit
judgment. Supplying `--against RULES` or its role-named `--rule RULES` alias
adds the same Context Conformance report as an optional final saved section:

```text
Duplicate -> Ambiguity -> Conflict -> Fit -> Conformance
```

The three quality report types remain unchanged. Fit and Conformance are
distinct typed sections because forcing a set-level or Rule-versus-Target
schema into the pair/single-Memory finding union would corrupt the review
contract. Audit schema version 2 adds Fit; version-1 records remain readable
with their recorded Conformance section but are not reused for a current
multi-Memory Resolve/Meld run. A current multi-Memory Audit reopens as `4/4`,
or `5/5` with Conformance. Conformance judgments do not become fabricated
duplicate/ambiguity/conflict/Fit judgments.

## Execution and safety invariants

- Rule/Context Conformance declares `WHOLE_FRAME_ONLY` execution.
- Every frozen Rule is judged exactly once; every Target Memory is cited or
  explicitly outside.
- No partial report is published after provider, schema, coverage, or stale
  input failure.
- Neither direct Conformance nor Audit changes a Ground, Context, Rule, or
  Memory and neither creates a checkpoint.
- Audit validates optional Conformance setup before opening any provider turn;
  a multi-Memory Audit then performs three finder calls, Fit, and optional
  Conformance in that order.
- Durable Audit requires recorded provider identity and exact Source equality.
- A Ground workspace is revalidated after Rule/Context Conformance before its
  report is returned.

## Intentional non-goals

This operation does not execute a Rule as a transformation, compare an output
with a hidden expected value, enforce or rewrite Rules, repair failing
Examples, update a Ground, promote a candidate Rule, or prove general
correctness. Conformance checks whether supplied evidence meets supplied Rules,
not whether those Rules are normatively desirable or externally true.
