# Evaluation application ownership

## Decision

The evaluation package is owned by `memcommit.application.evaluation`. The
relocation preserves its existing modules, fixtures, command behavior, study
prewarm integration, and evaluation result contracts without attempting to
redesign the package internally.

## Motivation

The former top-level `memcommit.eval` package combined executable evaluation
campaigns, scoring, study bundle preparation, prewarm tooling, and packaged
fixtures. Although those responsibilities may later deserve smaller owners,
they all coordinate application use cases rather than define a peer
architectural layer beside `application`, `adapters`, or persistence.

Moving the package as one unit establishes that coarse ownership before making
finer judgments about individual study tools. This keeps the current
reorganization mechanical and makes a later split reviewable independently.

## Compatibility boundary

There is no `memcommit.eval` compatibility facade. Internal callers, tests,
packaged-resource lookups, and maintained study scripts use the canonical
`memcommit.application.evaluation` path directly. Published command behavior
and fixture contents are unchanged; the Python import path is intentionally
not retained as a second source of ownership.

## Deferred work

This change does not decide whether individual `study_*` modules should remain
in the distributable application package or move to repository-only research
tooling. It also does not separate fixtures by operation. Those decisions need
their own dependency review because runtime rules and study prewarm preparation
currently consume some of these resources and types.
