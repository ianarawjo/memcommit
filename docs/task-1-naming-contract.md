# Task 1 naming contract

## Decision

Task 1 uses stable role names rather than a fictional participant identity.
The canonical identifiers are:

| Role | Canonical identifier | Kind and authority |
| --- | --- | --- |
| organizational origin | `campus-wiki` | opaque query-only upstream represented by a `QueryContextRef` |
| local wiki fork | `participant/campus-wiki-fork` | ordinary writable Context graph scoped to the participant's responsibility |
| verified change source | `participant/construction-updates` | ordinary readable local Context graph |
| person in English prose | `the participant` | role label, not a personal name |

`participant` is a literal, stable pseudonymous namespace in the study
fixture. It is not a placeholder to replace with a participant's real name.
Participant-facing prose likewise uses “the participant” instead of inventing
a character name.

The hyphen and slash have different meanings. `campus-wiki` is deliberately a
flat public name for an opaque upstream. A slash denotes ordinary Context
namespace structure, as in `participant/construction-updates`; it must not be
introduced into the upstream name merely for visual grouping.

## Task 1 object boundary

The names preserve three different authority-bearing objects:

```text
participant/construction-updates
    verified local evidence

participant/campus-wiki-fork
    writable direct Memories in the participant's assigned scope
    └── QueryContextRef: campus-wiki
        opaque organizational origin; query access only
```

The query-only pointer may be addressed explicitly:

```bash
mem query campus-wiki \
  "What is the approved visitor route during construction?" \
  --context participant/campus-wiki-fork
```

It is not an ordinary Context that can be selected, traversed, or used as the
target of `impact` or `update`. The participant performs the directional
operation against the writable fork:

```bash
mem switch participant/construction-updates
mem impact --to participant/campus-wiki-fork
mem update --to participant/campus-wiki-fork
mem diff
```

A later `push` or PR is the separate publication boundary from the local fork
toward `campus-wiki`.

## Why this is a repository contract, not a Memory

These names determine command semantics, fixture identity, and authority
boundaries before any study Context is loaded. Storing the convention only as
a Memory would make it dependent on the active Context, expose design
instructions as participant evidence, and permit tests and documentation to
drift independently. This document is therefore the source-of-truth contract.
Fixture builders and regression tests should consume shared constants or
otherwise check these exact identifiers as the implementation is migrated.

Generic documentation that needs an ordinary parent Context must use a neutral
name such as `facilities-reference`. It must not reuse `campus-wiki` as both an
ordinary readable parent and the Task 1 query-only upstream.

## Current prototype boundary

This naming contract records intended Task 1 semantics; it does not imply that
all underlying mechanics exist. The current query-only implementation can
store and query the pointer, and `update` can now materialize a validated plan
in the already-provisioned local fork. The prototype still does not create
that fork, bind it to an upstream revision, refresh it, or publish it.
Multi-Context local application provides exception rollback but not a durable
crash-recovery journal. Fixtures and tests that predate this contract require
migration rather than reinterpretation as evidence that the old names remain
canonical.
