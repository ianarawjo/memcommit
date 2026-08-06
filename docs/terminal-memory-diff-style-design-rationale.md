# Shared terminal Memory-diff style rationale

## Problem

Semantic Impact and the checkpoint detail opened by `mem diff` present the
same directional Memory transition.  Defining red, green, neutral, and report
colors independently in each screen allowed the two views to drift even though
their `- before`, `+ after`, and unchanged-line meanings are identical.

## Contract

Both projections use the shared `memory-diff.remove`, `memory-diff.add`, and
`memory-diff.equal` roles, with the corresponding `.changed` role used only to
emphasize mechanically changed spans.  Report prose and metadata use shared
neutral and label roles.  The common style definition is the only owner of the
palette, so a future color change reaches both screens together.

Direction remains the primary cue: removal lines are red, addition lines are
green, and unchanged lines are neutral.  Bold distinguishes changed spans
without introducing a separate operation-specific color grammar.

## Boundary

Sharing presentation does not merge the screens' behavior or authority.
History remains read-only checkpoint inspection, while Impact retains its own
navigation and operation handoff rules.  Neither viewer derives semantic
equivalence from styling; both consume the same frozen mechanical Memory diff.
