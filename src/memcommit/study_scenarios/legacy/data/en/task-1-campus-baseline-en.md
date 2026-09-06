# Task 1 Campus Baseline Candidates

## Data Contract

- This document is synthetic material for a fictional university created for research. It does not correspond to any real university,
  building, city, address, person, or business.
- There are exactly 300 candidates, with 50 in each of the six categories.
- Only the Content of each item is a Memory candidate. The identifier, Memory Location,
  Audience, and Construction Impact are designer sidecars for design and validation and
  are not included in the Memory Content.
- Memory Location is a canonical locator in the format campus-wiki/<sub-Context>/<stable leaf>.
  A split candidate appends a semantic suffix to its original number so that
  the numbers of subsequent candidates do not change.
- Audience is an audience sidecar that indicates the intended disclosure scope. It does not mean
  that the current prototype performs role authentication or ACL enforcement.
- Update Target means an outdated baseline that a construction update actually changes; Missing Context means
  a fact required to interpret the update but absent from the existing baseline; Impact Assessment Support
  means background used to determine the direction of change; and Unaffected means a fact unrelated to this construction.
  The `Already Consistent` status, which means the same fact as the update, is not used.
- The spatial layout is a fictional model loosely informed by the compact campus of an urban comprehensive university.
  It must not be interpreted as a fact about any real place.
- All university, building, facility, parking lot, store, and stop names and relative locations used in the Content
  are research pseudonyms. They do not identify or reproduce any real institution, address, city, telephone number, business, or
  existing place.

Memory content is maintained in the Context JSON files below. This document retains the data contract and a navigation index.

- [`campus-wiki/building-access`](../native/task-1/task-1-campus-authority/en/campus-wiki/building-access/context.json)
- [`campus-wiki/event-relocations`](../native/task-1/task-1-campus-authority/en/campus-wiki/event-relocations/context.json)
- [`campus-wiki/temporary-parking`](../native/task-1/task-1-campus-authority/en/campus-wiki/temporary-parking/context.json)
- [`campus-wiki/shop-updates`](../native/task-1/task-1-campus-authority/en/campus-wiki/shop-updates/context.json)
- [`campus-wiki/facility-updates`](../native/task-1/task-1-campus-authority/en/campus-wiki/facility-updates/context.json)
- [`campus-wiki/route-changes`](../native/task-1/task-1-campus-authority/en/campus-wiki/route-changes/context.json)
