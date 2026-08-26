# Example-driven Compare format refinement in Ground

## Motivating case

The Task 2 Advisor comparison exposed a useful Ground workflow even though no
Compare-format change is being made as part of this note. A person first saw a
real Compare result, identified that the `GROUNDING CANDIDATES` cards were too
long and research-internal, and refined the desired presentation through
concrete rewrites. The emerging preference was a short `POTENTIAL CONFLICTS`
section in which each item names both sources, states their difference, and
explains the consequential tradeoff in one paragraph.

This is an example of Ground learning a rule from reviewed cases rather than a
reason to hard-code one conversation's preferred wording directly into
Compare.

## Ground case shape

The original and revised renderings should be retained as reviewable Ground
Memories. A useful case contains:

- the original Compare fragment as immutable source material;
- the person's proposed replacement as the expected rendering;
- the local rationale, such as hiding ledger-only identifiers, preserving
  source attribution, or removing a redundant disclaimer;
- a boundary case showing when the rule should not apply, for example a ledger
  view whose purpose is to expose relation identifiers and evidence.

Ground can then induce and refine Rules such as:

1. Default Compare output presents each unresolved consequential difference as
   one compact paragraph.
2. The paragraph identifies each source's position before describing the
   tradeoff or downstream constraint.
3. Internal priority labels and relation ordinals remain available in the
   ledger view but do not lead the default explanation.
4. A footer gives the next executable Meld action without repeating that
   Compare did not decide for the person.

These are candidate Rules until separately reviewed and accepted through the
normal Ground workflow. One accepted example must not silently become a global
renderer policy.

## Invariants

- Compare may summarize only differences grounded in the compared Memories.
  Presentation refinement must not manufacture a source position.
- Ground Memories preserve the exact reviewed before-and-after examples;
  rationale remains Ground-local Notes and is not materialized as an ordinary
  Context Memory.
- A later renderer change should cite the accepted Rule and include tests for
  both the default and ledger views.
- Fixture or golden-relation changes are a separate dataset decision. The
  proposed non-specialist Task 2 conflicts are not adopted by this note.

## Rejected shortcut

Directly changing the Compare prompt or renderer from a single conversation
would make the desired format difficult to audit and could accidentally turn
an illustrative rewrite into unsupported Task 2 content. Capturing the case in
Ground first keeps the example, the inferred rule, and its exceptions
independently reviewable.

## Current limitation

This note records the intended example-driven workflow only. It does not add
the example to a durable Ground, accept a Rule, change Compare output, or alter
Task 2 fixtures. Those remain explicit follow-up actions with their own review
and persistence boundaries.
