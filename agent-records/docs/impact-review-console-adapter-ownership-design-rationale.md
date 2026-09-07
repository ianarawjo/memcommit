# Impact and Review console adapter ownership

## Problem

`mem impact` and `mem review` are real console commands, so their launchers,
cross-operation catalogs, and common terminal presentation belong under their
own command packages. Their former command modules had also accumulated the
operation-specific work needed to open Update, Meld, Sever, Atomize, Compare,
Audit, Forget, Distill, Makemore, and Resolve artifacts. That work included
provider connection, operation session lookup and revalidation, application
model projection, and handoff to the operation's owning workflow. As a result,
finding one operation's complete console adapter required reading the central
Impact or Review implementation, and the Review application package imported
console presentation to build operation reports.

The shared command names do not make those operation-specific responsibilities
shared policy. Impact and Review coordinate a family of routes; each member of
that family still owns the meaning and lifecycle of its artifact.

## Decision

Use a federated console-adapter boundary:

- `commands/impact/` owns the `mem impact` grammar and dispatcher, the combined
  saved-artifact catalog, saved/process-local Impact presentation, and common
  read-only handoff mechanics. `projection.py` also owns `ImpactEntry`,
  `ImpactView`, and `ImpactController`: those concrete models and conversions
  describe the Impact feature even when another command embeds its preview.
  The reusable session host consumes a read-only structural effect-preview
  interface; it does not import a command package or duplicate Impact validation.
- `commands/review/` owns the `mem review` grammar and dispatcher, the combined
  saved-artifact catalog, common saved-session selection, and common Review
  report presentation.
- Each affected operation package owns its Impact or Review console adapter in
  `commands/<operation>/impact.py` or `commands/<operation>/review.py`. That
  adapter loads and revalidates the operation's artifact, projects its typed
  application model, connects a provider when that route calls one, and hands
  control back to the operation's existing workflow when applicable.
- Shared semantic and persistence policy remains under `application/`; moving
  a console adapter does not move an operation model into the console layer.

The central commands import the narrow operation-owned open/run functions and
route to them. Operation adapters may compose the central Impact or Review
presentation primitives, but application code must not import those console
adapters. The former
`application/operations/review/report_adapters.py` violated that direction by
owning console report projections and is therefore removed rather than kept as
a compatibility implementation.

`commands/impact/process_local.py` remains only as a temporary import facade
for the former internal helper path. Production dispatch imports the new
operation owners directly; the facade contains no implementation.

## Preserved behavior

This is a responsibility relocation, not a feature or lifecycle change. It
preserves:

- Typer command names, operands, options, help, exit behavior, and rendered
  text;
- interactive versus snapshot selection and presentation behavior;
- persisted artifact schemas, locations, identifiers, selection order, and
  stale-session checks;
- provider choice, prompt construction, call count, and failure timing;
- Context and Grant authority checks, source/target resolution, digest and CAS
  boundaries, and owning-operation Apply paths; and
- the non-mutating contract of Impact and the post-application, read-only
  contract of Review.

In particular, the move does not make Review an Apply gate, does not add
durability to process-local Impact proposals, and does not allow the central
commands to bypass an operation's normal resume or materialization route.

## Why this boundary

The operation package is the smallest place where the artifact's semantic
identity, persistence contract, and executable lifecycle are all meaningful.
The Impact or Review package is the smallest place where cross-operation
discovery and shared terminal behavior are meaningful. Keeping those two
levels explicit lets a reader start at either the public command or the owning
operation without turning either package into a second application layer.

A single generic Impact/Review adapter framework was rejected. The current
routes deliberately differ in durability, terminal-state requirements,
revalidation, provider use, and owning-workflow handoff. Abstracting those
differences during a path-only move would risk changing behavior and would
hide the boundaries the relocation is meant to expose. Leaving every adapter
in the central command was also rejected because it preserves the original
mixed ownership even if the functions are split into more central files.

## Verification and remaining boundary

Ownership tests locate the operation projections, loaders, provider
connections, and handoffs in their operation packages and reject the deleted
central Review adapter. Existing command, session, provider, authority,
snapshot, and workbench tests remain the behavioral oracle; they are updated
only where a monkeypatch or source-ownership assertion must name the new
module.

The central `impact/command.py` and `review/command.py` still contain their
public Typer grammar and dispatch branching. This decision does not introduce
a plugin registry or a common operation-adapter protocol. The compatibility
facade for process-local Impact can be removed separately after its internal
import lifetime is reviewed. These are navigation and extension concerns, not
reasons to reinterpret the preserved command contracts in this relocation.
