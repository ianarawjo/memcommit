# Task 1 naming contract

## Decision

Task 1's task Profile sees a top-level `campus-wiki` **view** sourced from the
switchable `task-1-campus-authority` Profile. The task is already the
experimental boundary, so `-fork` would incorrectly imply a divergent copy
and publication workflow.

| Role | Canonical identifier | Kind and authority |
| --- | --- | --- |
| campus authority Profile | `task-1-campus-authority` | owns the ordinary campus source trees and can be selected for full CRUD |
| editable campus view | `campus-wiki` | task-side `READ+CREATE+UPDATE` grant over the authority Context graph |
| construction detail view | `campus-wiki/construction-details` | narrower task-side `QUERY` grant; no `READ` |
| verified change source | `participant/construction-updates` | ordinary task-owned Context graph and task attachment |
| person in English prose | `the participant` | role label, not a personal name |

`participant` remains a literal, stable pseudonymous namespace for the
participant-facing change source. It is not a placeholder for a real name.
The ordinary wiki does not use that namespace because it represents the
campus reference collection, not the person who happens to update it.

## Task 1 object boundary

The fixture separates local evidence from authority data and derives two
task-side views:

```text
task-1 Profile                         task-1-campus-authority Profile
participant/construction-updates      campus-wiki (ordinary source)
    └── campus-wiki view ────────────>├── readable/editable wiki tree
        └── construction-details      └── construction-details tree
            query-only view
```

The current explicit query command remains:

```bash
mem profile use task-1
mem query campus-wiki/construction-details \
  "What work is planned for the Main Building?"
```

The query view is not an ordinary task-owned Context. It cannot be selected,
traversed, or used as an `impact` or `update` target. Its source is ordinary
only inside the authority Profile.

The participant performs directional operations against the ordinary wiki:

```bash
mem switch participant/construction-updates
mem ls campus-wiki
mem add "..." --context campus-wiki
mem edit MEMORY "..." --context campus-wiki
```

There is no separate `fork` object in this study fixture. The task command
writes the single authority-owned wiki through a revalidated grant. Any later
publication or synchronization workflow remains a separate design concern.

## Why this is a repository contract, not a Memory

These names determine command semantics, fixture identity, and authority
boundaries before any study Context is loaded. Storing the convention only as
a Memory would make it depend on the active Context, expose design
instructions as participant evidence, and allow tests and documentation to
drift independently. This document therefore records the source-of-truth
contract.

Generic examples that need an ordinary parent Context should continue to use
neutral names such as `facilities-reference`; they should not repurpose
`campus-wiki` or `construction-details` for an unrelated topology.

## Current prototype boundary

The implementation can list and directly edit granted wiki Memories and query
the narrower construction detail view. Context lifecycle, `impact`, and
`update` do not yet accept granted targets. Query-only remains a research UI
authority boundary rather than operating-system access control. Generated
bundle changes do not refresh already imported Profiles, so regeneration and
installed-Profile migration must be reviewed separately.
