# Shared `mem` Command Boundaries

## Motivation

`mem` commands present different workflows, but they operate on the same
ordinary Context identities and persistence records.  A command-local
existence check, loader choice, or final state write can therefore create a
safety gap even when its visible behavior looks correct in isolation.

The motivating failures were concrete:

- a mutator could save a tolerant resolving load and silently erase an
  unavailable embedded-Context pointer;
- a create-then-save command could overwrite a concurrently created Context;
- a destructive confirmation could approve one Context identity and delete a
  replacement that later occupied the same name;
- a source-dependent command could save a locator after that source had been
  renamed;
- a human-oriented catalog could omit a malformed record while a safety scan
  incorrectly claimed that it had inspected every Context.

This note records which lower-level boundaries commands share, and which
differences are intentional.

## Dependency map

```text
existing ordinary Context operand
└── resolve_context_locator(raw, current_snapshot)
    └── canonical Context name
        ├── navigation/read path
        │   ├── tolerant catalog + diagnostics
        │   └── load / load_direct according to the read contract
        ├── one-Context mutation
        │   ├── load_direct or load_for_update
        │   └── target UID/digest CAS at save
        ├── source-dependent mutation
        │   ├── source name/UID/digest receipt
        │   └── source recheck + target CAS under one lock set
        └── destructive approval
            ├── escaped canonical display
            └── exact UID/digest recheck under the delete lock

new ordinary Context name
└── lexical validation only (never existing-Context locator resolution)
    └── require-new publication
        ├── optional exact source/history recheck
        └── optional current-state CAS
```

`mem contexts` and the no-argument `mem switch` remain two presentations of
the same navigation catalog.  Saved-session pickers share their terminal
shell, but each operation retains its own immutable or revision-based
freshness receipt.

## Invariants

### Existing Context locators

Capture the current Context name once at command entry.  Resolve `.`, `..`,
`./...`, and `../...` against that snapshot; bare names remain canonical
global names.  Use only the resolved name for existence checks, loading,
comparison, persistence, and user-visible target confirmation.

Do not apply this resolver to new Context identifiers, Memory selectors,
query-only selectors, provider output, or names already persisted in a saved
artifact.

### Loader authority

A Context object that will be serialized must never come from tolerant
`load()`.  Commands that mutate only directly owned items use `load_direct()`
or `load_current_direct()` so every pointer is preserved without opening its
target.  Commands that require a valid embedded graph use `load_for_update()`,
which fails closed when a direct embedded Context is unavailable.

Tolerant resolving loads remain valid for read-only presentation and search.
The three load modes are separate authority contracts, not interchangeable
convenience APIs.

### Multi-Context mutations

Target CAS alone is insufficient when the result contains names or content
derived from another Context.  `merge`, `embed`, `reference`, branch
publication, and similar operations carry a source binding of canonical name,
UID, and direct-record digest.  The store reacquires every source and target
lock in deterministic order, revalidates those bindings, then saves the target
without releasing the lock set.

Meld retains its command-specific persistence entry point because its receipt
shape differs, but delegates the source name/UID/digest check to the same
binding verifier under the same graph and Context lock discipline. This avoids
two subtly different definitions of a fresh source.

If an operation also copies checkpoint history, the history digest is part of
the receipt.  Context content and history must describe the same frozen source
version.

### Creation, selection, and rollback

All new Context publication uses a require-new store boundary.  A preceding
`context_exists()` check may improve an error message but never supplies the
write precondition.

A long create-and-select flow captures the starting current Context and uses a
compare-and-swap for the final selection.  A concurrent selection is preserved
rather than overwritten.  Once a new Context has been published and the
command releases its creation lock, later failure preserves that Context for
inspection instead of deleting by name; another process may already have
observed or referenced it.

Bare interactive Init and Branch apply this rule across their name/Source
controls. Init keeps require-new creation and final selection inside the same
batch lock and rolls back its exact new identities if the frozen current
pointer changed. Branch freezes the command-start current pointer separately
from its selected local Source, then rechecks Source UID, content digest,
checkpoint-history digest, target newness, and current state in its existing
atomic branch transaction. Choosing a non-current Source never performs an
intermediate global switch.

Rollback inside one still-held creation transaction may remove only the exact
new identity created by that transaction.

### Destructive approval

Before approval, resolve and load the canonical target and freeze its UID and
digest.  Escape the displayed label without changing the raw identity bound to
the receipt.  Deletion rechecks the exact binding under the write lock.  A
deleted-and-recreated name is a different target and invalidates approval.

### Catalog modes and storage roots

All ordinary Context access shares one root safety rule: the configured
`contexts` root and namespace components must be real directories, never
symbolic links.

Catalog consumers have intentionally different completeness contracts:

- navigation returns header-valid names and diagnostics suitable for a human
  list or picker;
- global evidence collection may continue past invalid records but must report
  `PARTIAL` when diagnostics exist;
- mutation safety scans fail closed on any malformed or unsafe record;
- blank Ground discovery remains a name-only, no-record-open privacy boundary;
- Profile inspection validates an arbitrary inactive store as a complete
  import boundary.

These modes share path safety and typed diagnostics, not one permissive list
whose omissions are invisible to callers.

### Terminal display

Context, Profile, query-only, and saved-session labels are untrusted display
text.  Shared escaping makes control, bidi, and layout characters visible so
one record cannot imitate a trusted heading or another row.  Selection and
persistence continue to use the untouched raw identity.

### Revert

Checkpoint snapshots are direct persistence records.  Revert reconstructs
them without resolving Context references so unavailable pointers survive
exactly.  It prepares and validates the replacement history before mutation,
uses atomic per-file replacement, and restores the original Context and
checkpoint bytes if an exception interrupts the operation.

## Alternatives considered

### One universal loader

Rejected because resolving content, preserving opaque pointers, and requiring
a complete embedded graph are different privacy and mutation authorities.

### One universal catalog function with a boolean `strict` flag

Rejected because navigation omissions, partial research evidence, Ground
name-only discovery, and import validation have different result types and
error semantics.  Typed results make an accidental completeness claim harder.

### Command-local prechecks followed by ordinary `save()` or `delete()`

Rejected because the precheck and mutation do not share a lock or stable
identity.  Names are locators and may be reused; UID/digest receipts define the
reviewed object.

### Deleting every partially published destination

Rejected once the creation lock has been released.  Publication can be
observed without modifying the new Context itself, so name-based cleanup can
create dangling references in otherwise successful concurrent work.

## Boundaries and limitations

The locks coordinate cooperating `mem` processes; they do not make a set of
filesystem replacements crash-atomic.  Atomic replacement prevents truncated
individual records, and exception rollback restores the prior files, but a
machine failure can still interrupt a multi-file transaction.

Navigation names and the current marker are not claimed to be one atomic
read-only snapshot.  Mutating selection remains safe because it revalidates
the target and current state at the final CAS boundary.

Ground exact-command receipts retain their separate approval protocol.  This
note does not reinterpret query-only names, saved artifact bindings, or
provider output as ordinary existing-Context operands.
