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
- Historical root import paths are intentionally unavailable; implementation,
  tests, tools, and capture scripts import the canonical owner directly.
- Internal implementation imports point at canonical owner modules after each
  relocation batch.
- New package initializers remain dependency-neutral. Public convenience
  exports may load lazily when eager loading would make a foundational module
  depend on a higher-level adapter merely because both now share a package.
- One source implementation has exactly one canonical path.
- The package root retains only its public package surface. Public Context
  values remain re-exported by `memcommit`, while their defining module belongs
  to core; existing-Context operand resolution belongs to application
  orchestration.
- Existing behavioral failures are not silently converted into new contracts.
  Baseline failures remain a comparison set during path-only work.
- Operation evidence state remains authored only in the existing evidence
  registries; this layout record does not classify route closure.

## Classification

Every baseline root module has one role:

- historical-compatibility-facade: a forwarding path retained in the frozen
  baseline inventory but removed from the executable package;
- operation-implementation: code named for and consumed by one operation
  family;
- shared-concept-implementation: reusable code with a narrower named owner;
- retired-prototype: a frozen baseline name whose canonical implementation and
  compatibility path were deliberately removed with the feature;
- root-boundary: one of the deliberately retained public or composition
  boundaries.

The complete frozen classification is in
root-module-relocation-plan.json. Its Markdown projection exists for reading,
while the JSON preserves exact paths for mechanical checks.

## Compatibility boundary

Physical root facades defeated the navigation goal even after their
implementations moved. The first relocation pass therefore centralized the
historical paths in generated maps and one process-local import finder. On
2026-08-27 that compatibility decision was explicitly withdrawn because no
external Python-path consumer or continuing compatibility intent remained.
The finder, generated maps, and forwarding package were removed together, and
repository-owned imports were migrated to canonical owners.

This deliberately breaks imports and Python serialized globals that name the
removed modules. It does not remove CLI commands, change command options, or
reinterpret durable memcommit data schemas. Retaining a package `__getattr__`,
eager `sys.modules` entries, or thin forwarding files was rejected because
each would keep an unsupported second module vocabulary alive and allow new
internal dependencies to drift back to historical names.

On 2026-08-26 `memcommit.flow_placeholder` became the first retired baseline
entry when the per-Memory Query catalog, canonical renderer, font assets, and
runtime dependency were removed together. The frozen plan keeps that name and
reason visible but assigns no canonical target, making retirement explicit
rather than a missing target or an untracked deletion.

On 2026-08-30 `memcommit.bootstrap` was retired with the generic console
presentation-mode router it existed only to compose. Complete command argv now
select one semantic execution and result projection independent of terminal
interactivity, so a package-root composition object choosing between plain and
TUI presenters would recreate a concept the console no longer exposes. The
same frozen plan was synchronized with earlier completed retirements and
splits for Atomize Grounding, legacy Ground sessions, federated Review report
adapters, and translation catalogs; those entries record already-established
owners rather than introducing new behavior here.

On 2026-08-27 the executable Typer registry moved from the package root to
`memcommit.adapters.console.entrypoint`. The `memcommit.cli` import was removed
without an alias because the console now has one explicit adapter owner and no
compatibility intent was retained for the former internal module path. The
installed `mem` script and internal subprocess launchers use the canonical
entry point directly; this relocation does not move any registered command or
change command behavior.

On 2026-08-27 the mixed in-memory operation API moved intact from
`memcommit.ops` to `memcommit.application.capabilities.ops`. The module still contains
structural Context rules, operation wrappers, and the legacy Integrate
implementation; placing the unchanged mixture under application is an
intentional staging boundary that avoids making a core package depend upward
on application operations. The `memcommit.ops` path and root-package `ops`
re-export were removed without compatibility aliases. Separating the
structural rules and Integrate implementation remains later work.

On 2026-08-27 the existing `memcommit.reviewing` package moved intact to
`memcommit.application.capabilities.reviewing`. Its dominant responsibility is coordinating
quality analysis, review state, and operation handoff, so application is the
clearest provisional owner. This is deliberately a physical staging move: it
does not claim that persistence-backed Audit storage or console navigation and
rendering belong permanently to application. Those narrower responsibilities
remain candidates for later extraction after their contracts are reviewed.

On 2026-08-29 the Audit-specific slice crossed that staging boundary.
Its durable model, complete three-or-four-check execution, private CAS session
store, and Resolution compatibility projection moved to
`memcommit.application.operations.audit`. Shared finder, report, and workbench
contracts first lived under a provisional reviewing namespace. They now live
directly under `application.capabilities.memory_issue_analysis`. Audit is a named
operation that consumes those reusable capabilities; it is not itself a shared
analysis capability. The narrower name records that Duplicate, Ambiguity, and
Conflict results are model-assisted Memory-issue candidates for review rather
than an open-ended quality subsystem. No compatibility facade retains either
the provisional `application.capabilities.reviewing.quality.audit` paths or the
former shared reviewing paths.

On 2026-08-27 the Context, Memory, reference, and checkpoint values moved
intact from `memcommit.context` to `memcommit.core.context`. The stable
`from memcommit import Context`-style value exports remain part of the package
surface, but the former submodule path is intentionally unavailable. The
existing-Context locator moved separately from `memcommit.context_locator` to
`memcommit.application.capabilities.context_locator`: it interprets an operand against
captured application state and is shared by console and Python routes, so it
is neither a core entity rule nor a console-only parser. Consolidating it with
the broader `core.context_targeting` family remains later work.

On 2026-08-27 the existing `memcommit.interfaces` tree moved intact to
`memcommit.adapters.interfaces`. This deliberately redundant name is a temporary
staging boundary: it establishes that the CLI, console, TUI, agent, MCP, and
presentation implementations are outward adapters without prematurely splitting
their 53,000-line shared dependency graph. No compatibility facade retains the
former package path. Later changes may move one reviewed surface at a time into
`memcommit.adapters.console`, `memcommit.adapters.agent`, or another explicit
adapter owner; this relocation itself changes neither behavior nor interface
contracts.

Later on 2026-08-27 the reviewed machine-callable slice crossed that staging
boundary: `memcommit.adapters.interfaces.agent` moved to the canonical
`memcommit.adapters.agent` owner without a compatibility facade. The dormant
MCP projection and stdio server were retired instead of moving with it because
the repository no longer supports an MCP transport. The agent registry remains
the host-neutral in-process discovery and invocation boundary.

The reviewed console-common slice then crossed the same staging boundary:
`memcommit.adapters.interfaces.console` moved to the existing canonical
`memcommit.adapters.console` owner without a compatibility facade. Reusable
route, terminal, text, theme, progress, Response, and selection contracts stay
outside `commands`, so CLI and TUI consumers do not depend on Typer command
assembly. The emptied `adapters.interfaces.cli` and
`adapters.interfaces.tui.operations` trees are retired without compatibility
facades; the remaining `adapters.interfaces.tui` Viewer and Workbench trees
remain temporary staging surfaces pending their own ownership review.

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

Finally, system clipboard access moved to
`memcommit.adapters.console.clipboard`. The operating-system clipboard is an
outward console device rather than storage or application policy. The original
move also carried List's private structured staging file, digest, locking, and
redaction contracts into that adapter. Those staging contracts were later
removed when List became plain-text copy only; the adapter now owns only exact
UTF-8 system-clipboard reads and writes. With providers, configuration,
command ledgers, and clipboard assigned to explicit owners, the empty
`memcommit.infrastructure` package is removed rather than retained as a
facade.

On 2026-08-28 the application package gained one explicit scope split:
operation-owned vertical slices remain under `application.operations`, while
all other staged application owners moved mechanically beneath
`application.capabilities`. The move does not endorse broad provisional names
such as `semantic`, claim evaluation or console-command state as final
application capabilities, or resolve existing reverse dependencies. The
focused
`application-operation-capability-layout-design-rationale.md` record owns that
staging decision and its next-review boundary.

## Verification

The pre-relocation full suite and its exact failing node IDs form the behavioral
baseline. Each relocation batch must collect successfully, keep focused tests
passing, and introduce no new behavioral failure. Static ownership tests and
generated callable catalogs may change because their subject is the path
layout itself; those records are updated only after the canonical moves settle.
The layout check requires exactly two root Python files, rejects every
physical compatibility facade and internal historical import, verifies every
canonical target, and proves in a fresh interpreter that no removed root or
semantic-execution package path is restored by a runtime hook.

## Non-goals

This change does not rename callables, split large modules, consolidate
duplicate policies, remove canonical implementations, or resolve known
functional failures. Historical Python paths are removed as a class; operation
behavior and durable compatibility remain separate decisions.
