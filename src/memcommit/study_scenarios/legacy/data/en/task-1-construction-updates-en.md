# Task 1 Construction Update Candidates

## Data Contract

- This document contains synthetic data for a fictional university created for research. It does not correspond to any actual university,
  building, construction project, or operational notice.
- There are exactly 75 candidates, and the counts for the six categories are, in order,
  `11 / 10 / 15 / 13 / 17 / 9`.
- Only the `Content` of each item is a Memory candidate. The identifier, Memory Location,
  Audience, Baseline Relationship, and Review Status are supplementary annotations for design and validation
  and must not be included in the Memory content.
- `Memory Location` is a stable hierarchical locator sidecar. The first segment is
  `construction-updates`, the second is one of the six subordinate Contexts, and the final leaf
  preserves the original order and atomic-splitting semantics.
- Every candidate `Content` is a concise update instruction containing the public target
  Context, an explicit modify/add action, and the content to apply. Stable target Memory IDs
  and exact before/after text remain in `task-1-update-actions-en.tsv`; they are validation
  sidecars rather than information the update planner must invent. The `Baseline Relationship`
  preserves the initial authoring context. Candidates that retain an existing fact unchanged
  or add a duplicate are not included in this update set.
- `Audience` expresses only the intended future visibility. It does not imply
  role-based access control in the current prototype.
- All place names are fictional and generic. No actual school names, city names, addresses,
  personal names, or operator names are used.

Memory content is maintained in the Context JSON files below. This document retains the data contract and a navigation index.

- [`participant/construction-updates/building-access`](../native/task-1/task-1/en/participant/construction-updates/building-access/context.json)
- [`participant/construction-updates/event-relocations`](../native/task-1/task-1/en/participant/construction-updates/event-relocations/context.json)
- [`participant/construction-updates/temporary-parking`](../native/task-1/task-1/en/participant/construction-updates/temporary-parking/context.json)
- [`participant/construction-updates/shop-updates`](../native/task-1/task-1/en/participant/construction-updates/shop-updates/context.json)
- [`participant/construction-updates/facility-updates`](../native/task-1/task-1/en/participant/construction-updates/facility-updates/context.json)
- [`participant/construction-updates/route-changes`](../native/task-1/task-1/en/participant/construction-updates/route-changes/context.json)
