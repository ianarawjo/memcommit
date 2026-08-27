# Root module layout design rationale

## Problem

At baseline commit 885e62c0, all 249 top-level Python modules in memcommit
shared one flat directory. Operation implementations, public package
boundaries, reusable concepts, and historical import facades therefore looked
equally authoritative during repository exploration.

The immediate goal is navigability, not a behavioral redesign. A later reader
must be able to open an operation package or a named shared concept and find
the implementation that owns it without first knowing the repository history.

## Invariants

- Function and class bodies do not change as part of relocation.
- Existing root import paths remain available through module-identity aliases
  unless a later ownership decision explicitly removes that historical path.
- Internal implementation imports point at canonical owner modules after each
  relocation batch.
- New package initializers remain dependency-neutral. Public convenience
  exports may load lazily when eager loading would make a foundational module
  depend on a higher-level adapter merely because both now share a package.
- One source implementation has exactly one canonical path.
- Public Context, bootstrap, and the documented Context locator remain at the
  package root. Store belongs to persistence, while the in-memory operation API
  belongs to application orchestration.
- Existing behavioral failures are not silently converted into new contracts.
  Baseline failures remain a comparison set during path-only work.
- Operation evidence state remains authored only in the existing evidence
  registries; this layout record does not classify route closure.

## Classification

Every baseline root module has one role:

- compatibility-facade: an already migrated historical import path;
- operation-implementation: code named for and consumed by one operation
  family;
- shared-concept-implementation: reusable code with a narrower named owner;
- retired-prototype: a frozen baseline name whose canonical implementation and
  compatibility alias were deliberately removed with the feature;
- root-boundary: one of the deliberately retained public or composition
  boundaries.

The complete frozen classification is in
root-module-relocation-plan.json. Its Markdown projection exists for reading,
while the JSON preserves exact paths for mechanical checks.

## Compatibility boundary

Physical root facades defeated the navigation goal even after their
implementations moved: a file browser still presented 242 historical names as
peers of the original seven real root boundaries. The facades are therefore consolidated
into the exact generated map in
`memcommit.compatibility._legacy_alias_map` and one process-local finder in
`memcommit.compatibility.legacy_submodules`.

The finder recognizes only the frozen historical names. It imports a target on
first use, returns the exact canonical module object, and restores the
canonical import metadata that Python temporarily projects while resolving an
alias. This preserves legacy imports, monkeypatch identity, reload behavior,
and serialized global lookup without eagerly importing 242 implementations or
leaving 242 physical files at the package root.

A package `__getattr__` was insufficient because it does not implement
`import memcommit.legacy_submodule`. Eagerly populating `sys.modules` would
restore that syntax but would assemble the entire application whenever the
root package loaded. Deleting compatibility outright would be simpler but
would unnecessarily break historical imports and saved global references in a
pass whose stated boundary is physical layout rather than behavior.

The alias catalog does not promise that every historical name is permanently
public. On 2026-08-26 `memcommit.flow_placeholder` became the first retired
baseline entry when the per-Memory Query catalog, canonical renderer, font
assets, and runtime dependency were removed together. The frozen plan keeps
that name and reason visible but deliberately omits it from the generated alias
map. This makes retirement an explicit compatibility decision rather than a
missing target or an untracked deletion.

On 2026-08-27 the executable Typer registry moved from the package root to
`memcommit.adapters.console.entrypoint`. The `memcommit.cli` import was removed
without an alias because the console now has one explicit adapter owner and no
compatibility intent was retained for the former internal module path. The
installed `mem` script and internal subprocess launchers use the canonical
entry point directly; this relocation does not move any registered command or
change command behavior.

On 2026-08-27 the mixed in-memory operation API moved intact from
`memcommit.ops` to `memcommit.application.ops`. The module still contains
structural Context rules, operation wrappers, and the legacy Integrate
implementation; placing the unchanged mixture under application is an
intentional staging boundary that avoids making a core package depend upward
on application operations. The `memcommit.ops` path and root-package `ops`
re-export were removed without compatibility aliases. Separating the
structural rules and Integrate implementation remains later work.

On 2026-08-27 the existing `memcommit.reviewing` package moved intact to
`memcommit.application.reviewing`. Its dominant responsibility is coordinating
quality analysis, review state, and operation handoff, so application is the
clearest provisional owner. This is deliberately a physical staging move: it
does not claim that persistence-backed Audit storage or console navigation and
rendering belong permanently to application. Those narrower responsibilities
remain candidates for later extraction after their contracts are reviewed.

On 2026-08-27 the existing `memcommit.interfaces` tree moved intact to
`memcommit.adapters.interfaces`. This deliberately redundant name is a temporary
staging boundary: it establishes that the CLI, console, TUI, agent, MCP, and
presentation implementations are outward adapters without prematurely splitting
their 53,000-line shared dependency graph. No compatibility facade retains the
former package path. Later changes may move one reviewed surface at a time into
`memcommit.adapters.console`, `memcommit.adapters.agent`, or another explicit
adapter owner; this relocation itself changes neither behavior nor interface
contracts.

On 2026-08-27 the provider implementations moved from the generic
`memcommit.infrastructure` container to the explicit top-level
`memcommit.providers` owner, while global configuration moved to
`memcommit.configuration.config`. Providers are a named external dependency
family in the intended architecture, and configuration owns how their routes
and presets are selected; neither needs an additional `infrastructure` layer.
The two moves remain in one change because provider configuration imports the
provider contracts and provider connectors consume that configuration. No
compatibility facade retains either former infrastructure path.

The same decomposition places the command-attempt and Study-action ledgers at
`memcommit.persistence.command_ledger`. Their defining contract is durable,
profile-scoped recording with atomic file replacement and recovery-safe
publication, so persistence is their owner even though application operations
and console instrumentation initiate records. The existing modules move as a
unit to preserve their privacy and lifecycle invariants; separating the
prompt-toolkit input wrapper inside `study_actions` is deferred. No facade
retains the former `memcommit.infrastructure.command_ledger` path.

## Verification

The pre-relocation full suite and its exact failing node IDs form the behavioral
baseline. Each relocation batch must collect successfully, keep focused tests
passing, and introduce no new behavioral failure. Static ownership tests and
generated callable catalogs may change because their subject is the path
layout itself; those records are updated only after the canonical moves settle.
The layout check requires exactly four root Python files, rejects every
physical compatibility facade and internal legacy import, and imports every
retained compatibility alias (currently 241) in fresh
interpreters in both legacy-first and canonical-first order. It separately
rejects the removed `memcommit.cli`, `memcommit.ops`, and
`memcommit.provenance` paths, and
verifies exact module identity and canonical `__spec__` ownership so an earlier
test import cannot mask a package-initialization cycle or metadata regression.

## Non-goals

The original physical-layout pass did not rename callables, split large
modules, consolidate duplicate policies, remove historical names, or resolve
known functional failures. A later feature-removal change may retire one
historical name only when it records that state in the frozen plan and removes
the canonical implementation in the same change.
