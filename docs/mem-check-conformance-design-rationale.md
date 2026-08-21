# `mem check-conformance` design rationale

## Motivation

Distill can propose reusable Rules from examples or ordinary Context evidence,
but evidence coverage alone does not prove that the proposed Rules reproduce
the examples or that another Context follows them. The ticker evaluation made
the distinction concrete: all twenty examples were cited, yet one Rule's claim
about preserving `AI` was stronger than the example `Axiom AI Technologies →
AAT` supported.

Conformance is therefore a separate read-only semantic operation. It is
available directly through `mem check-conformance` and as an optional fourth
section of `mem audit`. Both adapters call the same typed core; Audit does not
invoke the CLI command as a subprocess or reinterpret its rendered text.

## Two contracts

### Case Conformance

```text
Ground Rules + Ground Memories(input, expected) -> PASS / FAIL / AMBIGUOUS / OUT_OF_SCOPE
```

`mem check-conformance --ground NAME` reads active proposed or accepted Rules
and active `INCLUDE` Ground Memories with nonempty expected outputs. The
provider receives each input, role, and the complete frozen active Rule set,
but **never receives the
expected output**. It must first return one exact prediction, ambiguity, or
out-of-scope disposition per case. The host then derives `PASS` or `FAIL` by
exactly comparing the frozen prediction with the frozen expected text. This
prevents answer copying and makes the current comparison boundary explicit.

Each Ground Memory still retains its single reciprocal Rule link as provenance,
but prediction is not restricted to that link. One output may compose several
Rules, as ticker generation composes normalization, base-symbol, and
share-class rules. Treating the provenance link as the complete execution
dependency was rejected because it makes compositional Rule sets untestable.

Exact comparison intentionally treats semantically equivalent but textually
different outputs as failures. A future semantic-equivalence judge would be a
separate frozen reconciliation turn, not a hidden relaxation of this contract.

The current `content` plus singleton `expected` fields are one narrow
implementation of a more general proposition contract. In the intended Ground
model, a Rule is a generalized proposition and an Example is a concrete
proposition. `Apple Inc. -> AAPL or APLE`, `Axiom AI Technologies -> AAT`, and
`on 2026-08-15 the observed sky was blue` are all valid one-line Example
propositions; only the first two happen to have an input/output projection.

Equality, membership, structural validation, and semantic criteria are
operation-owned evaluators compiled from or attached to a proposition. They
must not replace the proposition as the user-facing object. When a proposition
permits several outcomes, plurality is not itself an error. Underdetermination
instead means the current Rules do not support or contradict the reviewed
Example proposition sufficiently to settle its relation.

The current Case Conformance executor still supports only the exact
input/output projection. A proposition-oriented `fit` operation should reuse
its bounded provider and coverage mechanics, but return an explicit relation
for every Example and cite the responsible Rules. It must not add a failed
prediction to the Example proposition or revise either layer automatically.

### Context Conformance

```text
Rules Context + Target Context -> one Conformance judgment per Rule
```

`mem check-conformance TARGET --against RULES` treats every direct Memory in
the Rules Context as one Rule and every direct Memory in the Target as evidence.
Each Rule receives exactly one `CONFORMS`, `VIOLATES`,
`PARTIALLY_CONFORMS`, `NOT_APPLICABLE`, or `INSUFFICIENT_EVIDENCE` judgment.
Every Target Memory must be cited by at least one Rule judgment or explicitly
placed outside the judgments. Absence of evidence is not conformance.

The command exposes the same two Context roles through three equivalent
vocabularies:

```text
mem check-conformance TARGET --against RULES
mem check-conformance --rule RULES --example TARGET
mem check-conformance --rule RULES --case TARGET
mem check-conformance --from RULES --to TARGET
```

`Example` is the canonical Ground-v3 term for a concrete proposition; `Case`
remains an accepted user-facing alias because exact input/output replay and
older Ground material use that vocabulary. `--from` always names the Rules
Context and `--to` the Context being judged. If exactly one option-qualified
role is omitted, the command-start current Context supplies it, matching the
shared endpoint convention. The legacy positional Target does not by itself
infer a Rules Context, so an accidentally incomplete old command remains an
error.

Aliases are one semantic slot rather than independent inputs. Repeating a
Rules alias or a Subject alias, or combining the positional Target with a
Subject alias, fails before Context loading or provider connection. This avoids
order-dependent last-value-wins behavior and preserves one command-start
locator snapshot for both resolved names. `--ground` remains a separate bundled
Rules-plus-Examples route and cannot be combined with any Context endpoint.

The provider also returns the exact counterexample subset for every
`VIOLATES` or `PARTIALLY_CONFORMS` judgment. A violating judgment's cited
evidence is entirely nonconforming; a partial judgment has both conforming and
nonconforming cited cases. The host validates those relations rather than
trying to recover counterexamples from explanatory prose. This case identity
is retained in Conformance schema version 2. Version-1 saved reports remain
readable, but honestly carry no reconstructed counterexample detail because
their evidence list did not distinguish supporting cases from counterexamples.

The direct Context report keeps the Rule account compact: one
`RULE_ALIAS · RULE CONTENT · STATUS` row per Rule, followed only when necessary
by a `NONCONFORMING CASES` section. Each counterexample is one
`[MEMORY_ALIAS] MEMORY CONTENT [RULE_ALIASES]` row, so the content and the Rules
it violates can be scanned without opening a nested evidence block. Evidence
lists and provider reasons remain in the typed report but are not repeated in
this projection. The outside-judgment boundary is shown only when nonempty.
This keeps an all-conforming result scannable while making failures actionable
by case rather than by undifferentiated evidence volume.

Both Contexts are frozen from one command-start locator snapshot and
revalidated after the provider turn. The first implementation accepts local
direct Contexts only. Descendant, embedded, and granted frames require explicit
scope and retained-analysis authority contracts before rollout.

## Audit composition and compatibility

Normal `mem audit --context TARGET` retains its existing three independent
quality checks. Supplying `--against RULES` or its role-named `--rule RULES`
alias adds the same Context Conformance
report as an optional fourth saved section:

```text
Duplicate -> Ambiguity -> Conflict -> Conformance
```

The three quality report types and response ledger remain unchanged.
Conformance is a distinct optional typed section because forcing its
Rule-versus-Target schema into the pair/single-Memory finding union would
corrupt the existing review contract. Audit schema version 2 adds the optional
section; version-1 three-check records remain readable and reopen as `3/3`.
Version-2 records with Conformance reopen as `4/4` and expose the complete Rule
judgments in the report overview. Conformance judgments are read-only in this
slice and do not become fabricated duplicate/ambiguity/conflict review items.

## Execution and safety invariants

- Case and Context Conformance each declare `WHOLE_FRAME_ONLY` execution.
- Every frozen case or Rule is judged exactly once; every Target Memory is
  cited or explicitly outside.
- No partial report is published after provider, schema, coverage, or stale
  input failure.
- Neither direct Conformance nor Audit changes a Ground, Context, Rule, or
  Memory and neither creates a checkpoint.
- Audit validates optional Conformance setup before opening any of its four
  provider turns.
- Durable Audit requires recorded provider identity and exact Source equality.
- A Ground revision is revalidated after Case Conformance before returning its
  report.

## Intentional non-goals

This operation does not enforce or rewrite Rules, repair failing cases, update
a Ground, promote a candidate Rule, or prove general correctness. Replaying
the same examples checks round-trip fidelity; generalization requires held-out
Ground Memories. Context Conformance checks adherence to supplied Rules, not
whether those Rules are normatively desirable or externally true.
