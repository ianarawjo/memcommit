# Profile model package design rationale

## Motivation

`memcommit.application.operations.profile.model` combined ordinary Profile
lifecycle, Authority Grant resolution, Study import and publication, and the
filesystem primitives shared by all three. The 4,143-line module had no single
large execution function; it had grown because 132 top-level definitions with
different change reasons shared one physical file. This made it difficult to
identify the owner of a Profile behavior or review a focused change.

## Package contract

The canonical import remains `memcommit.application.operations.profile.model`.
The former module is now a package whose `__init__.py` re-exports the existing
public and compatibility names. Existing CLI, Python API, application, and test
callers therefore retain their import spelling and receive the same class and
function objects from the narrower owning modules.

The implementation is grouped as follows:

- `_storage.py` owns validated store inspection, registry locking and durable
  publication, deletion staging, and shared failure/result types.
- `grants.py` owns Authority Grant lifecycle and grant-backed read/share
  resolution.
- `study.py` owns Study grouping, migration, archive, rename, and removal.
- `lifecycle.py` owns ordinary Profile listing, selection, creation, import,
  rename, and removal.

Current Study construction belongs to
`memcommit.application.operations.init_study.profile`: its model, package,
composition, and publication modules own the initialization-only data flow.
The former Profile-model names resolve lazily to those canonical objects for
compatibility, but Profile lifecycle no longer contains their implementation.

The dependency direction is `_storage` toward no sibling, `grants` toward
`_storage`, `study` toward `_storage` and the shared Grant scope constructor,
and `lifecycle` toward `_storage` plus Study classification. Ordinary Profile
lifecycle consults Study classification so it can preserve reserved names and
whole-Study boundaries; it does not perform Study publication.

## Preserved invariants

- Profile registry writes remain lock-protected and durable.
- Store trees are validated before copying, publishing, or deleting.
- Profile deletion retains its prepare, registry publication, rollback, and
  final destruction sequence.
- Grant identity, attachment, permission, and frozen Context-scope validation
  are unchanged.
- Study Profile and Grant batches remain all-or-nothing publications.
- Selecting a Profile continues to affect the next process rather than
  redirecting a store already opened by the current process.

The move intentionally changes no function or class body. Structural
verification compares all 132 original top-level definitions with their new
ASTs, and compatibility verification covers every name imported from the old
module path by production code and tests.

## Alternatives and limitation

Keeping exactly three implementation files was rejected because lifecycle,
Grant, and Study operations all depend on the same registry lock and atomic
store primitives; assigning those helpers to one public domain would either
create a cycle or obscure their shared safety role. `_storage.py` is therefore
an internal fourth module rather than duplicated code.

The remaining `study.py` retains the validators and stable task/authority
identity constants used when reading legacy Study provenance. Init-study
package parsing imports those narrow compatibility contracts; moving them into
a third shared schema module would add indirection without separating another
independent behavior. The transaction bodies themselves now live with the
init-study operation.
