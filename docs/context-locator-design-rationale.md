# Existing Context locator resolution

## Status

The first shared rollout is implemented in:

```text
mem switch LOCATOR
mem compare --to LOCATOR
```

Both commands use `memcommit.context_locator.resolve_context_locator`.
Additional commands should adopt the same boundary when they are next changed,
subject to the mutation and approval constraints below.

## Motivation

Slash-delimited Context names form a lexical namespace. `mem switch` already
allowed a person at `test/update/from` to select the sibling Context with:

```text
mem switch ../to
```

The implementation lived as private functions inside the Switch command.
Consequently, the equivalent Compare operand was treated as a literal invalid
Context name:

```text
mem compare --to ../to
Compare error: Compared Context '../to' does not exist.
```

This was not a meaningful operation-specific distinction. It was duplicated
locator policy: one command understood explicit relative notation and another
existing-Context lookup did not.

## Locator contract

A **canonical Context name** is a durable slash-delimited identifier such as
`test/update/to`. A **Context locator** is CLI input used to find an existing
ordinary Context. It may be either a canonical name or an explicitly relative
spelling:

| Current Context | Locator | Canonical result |
| --- | --- | --- |
| `test/update/from` | `../to` | `test/update/to` |
| `organization/wiki` | `./facilities` | `organization/wiki/facilities` |
| `test/update/from` | `.` | `test/update/from` |
| `test/update/from` | `../../archive` | `test/archive` |

Bare names remain global. From `organization/wiki`, `child` still means the
canonical Context named `child`; only `./child` means
`organization/wiki/child`. This preserves scripts and prevents the same bare
argument from changing meaning when current state changes.

Resolution is purely lexical. It never reads the shell working directory,
filesystem layout, embedded Context graph, Memory contents, or query-only
sources. One trailing slash is accepted, while repeated or interior empty
segments, namespace-root results, and attempts to escape above the root are
rejected.

The resolver does not test existence and does not choose between `load`,
`load_direct`, or `load_for_update`. Those are operation-specific authority
and privacy decisions that remain with each command.

## Snapshot, persistence, and concurrency

A command captures the active Context name once and uses that same value as
the base for every relative operand in that invocation. It must not resolve
one operand, reread global current state, and resolve another against a
different base.

After resolution, equality checks, source loading, cache lookup, session
binding, output frames, checkpoints, and durable artifacts use only the
canonical name. Thus:

```text
mem compare --to ../to
mem compare --to test/update/to
```

identify the same ordered comparison slot and the second spelling can reuse
the first analysis.

Resolution itself grants no mutation authority and replaces no existing
identity or freshness checks. Switch still compare-and-sets current state and
the selected Context UID/digest. Compare still binds the exact source
snapshots and ordered analysis slot. A later mutating command must retain its
own locks, UID/digest checks, and canonical-target confirmation.

## Reuse rule and rollout boundary

When a CLI operand locates an **existing ordinary Context**, it should use the
shared resolver rather than implement dot-segment parsing or pass explicit
relative spelling directly to `MemoryStore`.

Read or analysis operands such as `ls CONTEXT`, `show --context`, or
`rationale --context` are suitable later adopters. Mutation-oriented operands
such as `delete CONTEXT`, `embed --into`, `update --to`, and Meld sources need
an additional review: prompts or approval receipts must display the resolved
canonical name, and the command must freeze the target identity before acting.

The resolver must not be applied indiscriminately:

- `init NAME`, `branch NAME`, `checkout -b NAME`, and `--save-as` values define
  new canonical identifiers; they are not existing-Context locators.
- Memory selectors, embedded-item selectors, requirement targets, and
  query-only source selectors have different namespaces.
- Ground frame binding requires a separate approval-aware integration. A raw
  relative argument must never retain a meaning that can change with the
  global active Context after the exact-command receipt is displayed.
- Provider-returned or already persisted Context names are canonical data and
  are never reinterpreted as relative CLI input.

These distinctions make the resolver universal for one semantic role—
locating an existing normal Context—without making every string that happens
to contain a Context name depend on mutable current state.

## Current limitation

Only Switch, non-branch Checkout through its Switch delegation, and Compare
use the common locator today. Other existing-Context operands still require
canonical names until migrated under the boundary above.
