# Memory Issue Analysis design rationale

## Problem

Duplicate, redundancy, ambiguity, and conflict judgment was physically owned
by `application.capabilities.reviewing.memory_issue`. That path described one
possible presentation phase rather than the capability's actual responsibility.
Find, Audit, Atomize validation, and semantic classification all need the same
typed judgment without entering a review conversation or calling another named
operation. The nested `finding` and `resolution` directories also made an
immutable issue look like the beginning of one mandatory repair workflow.

## Decision

`application.capabilities.memory_issue_analysis` is the sole physical owner of
the shared judgment. `reading_analysis` exposes Context-aware ambiguity;
`relation_analysis` exposes redundancy and conflict. Each caller selects only
the analysis required by its operation. Models, provider mechanics, Source
freezing, report projection, process-local workbench state, and typed handoff
remain narrow peer modules under that capability.

Ambiguity must receive the complete frozen Context frame supplied by its caller.
A Memory is not ambiguous merely because it is unclear in isolation: ordinary
antecedents, shared scope, or neighboring Memories in that frame may determine
one reading. Multi-Context Find and Audit therefore preserve original public
Context provenance while judging the complete authorized aggregate frame.

Named operations continue to own request validation, authority, persistence,
presentation, and effects. Find and Audit consume the capability directly;
they do not invoke each other. A workbench response or handoff is typed evidence
for a subsequent operation, never permission for this capability to mutate a
Context.

## Alternatives and boundary

A monolithic call that always ran every issue check was rejected because a
caller asking only about ambiguity should not pay for unrelated pair analysis.
Duplicating detectors inside each operation was rejected because it would let
the same judgment drift across Find, Audit, and validation consumers. A
compatibility alias for the former reviewing hierarchy was also rejected: it
would preserve the misleading dependency direction for new internal imports.

This change preserves the existing provider contracts and serialized type
vocabulary. It does not yet make one unified provider turn for all issue kinds.
Compare's exhaustive ledger remains the current basis for Meld, and Update's
existing verification path is unchanged. Moving Meld and Update onto Memory
Issue Analysis requires a separate review of their source frames, disposition
coverage, proposal semantics, and pre/post-materialization boundaries.
