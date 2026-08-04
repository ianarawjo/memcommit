# Meld-created symmetric result Context

## Problem

Symmetric Meld previously used the active Context as its empty result. A person
had to create that Context, switch to it, and only then repeat both peer names.
The active global pointer was incidental to the operation and made the common
Compare-to-Meld handoff longer and easier to misroute.

## Command contract

```bash
mem meld LEFT_PEER RIGHT_PEER --to RESULT_CONTEXT
```

`LEFT_PEER` and `RIGHT_PEER` remain equal-authority existing Context locators.
`RESULT_CONTEXT` is a new ordinary Context identifier, not an existing-Context
locator. The command creates an empty local result, binds the symmetric Meld
session to it, and leaves the active Context unchanged.

`--to` is deliberately distinct from directional `--into`:

- `--into BASELINE` treats an existing baseline as authoritative and may
  update it after acceptance.
- `--to RESULT_CONTEXT` creates a separate result without making either peer
  authoritative.

The two options cannot be combined.

## Invariants

- Both peer sources must exist and be distinct from each other and the result.
- The exact ordered Compare analysis must already exist and still match both
  sources before the result is created.
- The result name must not already identify a Context. `--to` never adopts or
  overwrites an existing Context.
- The result is empty until an explicitly accepted Meld proposal is applied.
- Context creation and initial Meld-session publication share one command
  boundary. A session-write failure rolls back the exact unpublished Context.
- Creating the result does not change the active Context pointer.
- Granted peers retain the same combination, derivation, export, and result
  retention checks as the existing symmetric Meld path.

## Alternative considered

Automatically running `mem init RESULT_CONTEXT`, switching globally, and then
invoking the old symmetric command would reproduce the visible outcome but
would expose intermediate global state and leave an empty Context if the Meld
preconditions failed. Keeping result creation inside Meld makes the intended
three-frame operation explicit and allows failure before publication.

## Compatibility boundary

The existing `mem meld LEFT_PEER RIGHT_PEER` form continues to use the active
empty Context and resumes its target-bound session. `--to` is a creation form;
later work on its result uses the established target-bound Meld session rather
than silently reusing an unrelated pre-existing Context name.
