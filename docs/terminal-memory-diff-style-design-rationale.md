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

Before/after Memory content and line markers are white so long bodies remain
readable without flattening identity and content into one lavender block.
Only text absent from the result is red and underlined; only text newly present
in the result is green and underlined. This classification comes from the
mechanical span diff rather than vertical placement, so wrapped continuation
lines and paired before/after lines cannot change its meaning. One-sided ADD or
REMOVE content is wholly changed and therefore receives the corresponding
directional treatment.

A one-sided ADD or REMOVE receives one empty row after its sole content side.
This gives the entry comparable visual separation to a two-sided EDIT without
inventing an empty before or after line or changing the underlying diff model.

The compact operation marker and tag retain a mutation-specific color: EDIT is
green for updating an existing Memory, ADD is blue for introducing a new
Memory, and REMOVE is red. This keeps all three mutations distinct without
using warning-like yellow. The located Context and Memory identity remain
lavender. Focus does not recolor that identity or the complete Memory body.

## Boundary

Sharing presentation does not merge the screens' behavior or authority.
History remains read-only checkpoint inspection, while Impact retains its own
navigation and operation handoff rules.  Neither viewer derives semantic
equivalence from styling; both consume the same frozen mechanical Memory diff.
