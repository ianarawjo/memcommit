# Task 1 campus-wiki · construction-details Query-Only Construction Data Candidates

## Data Contract and Fictional Boundary

- All 78 candidates in this document are synthetic information created for user research.
  They do not correspond to any real university, building, construction plan, inspection result,
  reporting status, material, or schedule and must not be presented or reused as real data.
- The counts for the six categories are, in order, 32 / 7 / 11 / 9 / 5 / 14.
- Do not use real school names, building names, city names, addresses, personal names,
  company names, or product names. Names such as Main Building also have meaning only
  within this fictional scenario.
- Only the Content of each record is a Memory candidate. The identifier, Memory Location,
  Audience, and synthetic status are designer sidecars for design and validation and must
  not be included in the Memory Content.
- A Memory Location has the format
  campus-wiki/construction-details/<coarse dir>/<stable leaf>.
  A split candidate adds a semantic suffix to the original number so that the numbers of
  subsequent candidates do not change.
- Audience is an audience sidecar indicating the intended disclosure scope. Query-only
  routing is the actual prototype boundary; the current implementation does not provide
  role authentication or ACL enforcement by audience.
- This data is configured for research use so that its original text is not shown through
  general listings or general retrieval and is used only through the query path.
- This data is the query-only construction-details source attached to the ordinary
  campus-wiki Context. Do not mix it with the 300 Memories in the generally accessible
  campus-wiki. campus-wiki · construction-details is a review-only affiliation label,
  not an ordinary Context locator, and the actual query target name is
  construction-details.
- The synthetic status of every record below is: entirely fictional and created for research.

Memory content is maintained in the Context JSON files below. This document retains the data contract and a navigation index.

- [`campus-wiki/construction-details/work-bundles`](../native/task-1/task-1-campus-authority/en/campus-wiki/construction-details/work-bundles/context.json)
- [`campus-wiki/construction-details/dependencies`](../native/task-1/task-1-campus-authority/en/campus-wiki/construction-details/dependencies/context.json)
- [`campus-wiki/construction-details/report-status`](../native/task-1/task-1-campus-authority/en/campus-wiki/construction-details/report-status/context.json)
- [`campus-wiki/construction-details/material-control`](../native/task-1/task-1-campus-authority/en/campus-wiki/construction-details/material-control/context.json)
- [`campus-wiki/construction-details/verification`](../native/task-1/task-1-campus-authority/en/campus-wiki/construction-details/verification/context.json)
- [`campus-wiki/construction-details/query-policy`](../native/task-1/task-1-campus-authority/en/campus-wiki/construction-details/query-policy/context.json)
