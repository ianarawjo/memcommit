# Task 1 naming contract

## Decision

Task 1 uses a top-level ordinary `campus-wiki` Context. The Task Profile is
already the isolation boundary, so adding `participant/` and `-fork` to the
wiki locator repeats ownership and publication concepts that the participant
does not need in order to browse or update the fixture.

| Role | Canonical identifier | Kind and authority |
| --- | --- | --- |
| writable campus wiki | `campus-wiki` | ordinary readable and writable Context graph |
| concealed construction detail | `construction-details` | query-only child represented by a direct `QueryContextRef` in `campus-wiki` |
| verified change source | `participant/construction-updates` | ordinary readable local Context graph |
| person in English prose | `the participant` | role label, not a personal name |

`participant` remains a literal, stable pseudonymous namespace for the
participant-facing change source. It is not a placeholder for a real name.
The ordinary wiki does not use that namespace because it represents the
campus reference collection, not the person who happens to update it.

## Task 1 object boundary

The fixture contains one readable wiki with one narrower concealed source:

```text
participant/construction-updates
    verified local change evidence

campus-wiki
    ordinary readable and writable Memories
    └── QueryContextRef: construction-details
        concealed construction details; query access only
```

The current explicit query command remains:

```bash
mem query construction-details \
  "What work is planned for the Main Building?" \
  --context campus-wiki
```

This change establishes the data topology only. Relative composite query
locators and a no-argument interactive query entry point are deferred to the
query UX implementation. The query-only pointer is not an ordinary Context:
it cannot be selected, traversed, or used as an `impact` or `update` target.

The participant performs directional operations against the ordinary wiki:

```bash
mem switch participant/construction-updates
mem impact --to campus-wiki
mem update --to campus-wiki
mem diff
```

There is no separate `fork` object in this study fixture. Any later
publication or synchronization workflow is a separate design concern and
must not be implied by the Context name.

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

The query-only implementation can preserve and query the
`construction-details` pointer, and `update` can apply a validated plan to the
already-provisioned ordinary `campus-wiki`. Query-only remains a research UI
concealment boundary rather than operating-system access control. The current
prototype does not refresh an already imported editable Task Profile when a
generated bundle changes, so bundle regeneration and installed-Profile
migration must be reviewed separately.
