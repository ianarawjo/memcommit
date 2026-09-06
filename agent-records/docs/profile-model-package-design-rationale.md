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
  publication, deletion staging, and shared inventory/result types.
- `grants.py` owns Authority Grant lifecycle and grant-backed read/share
  resolution.
- `../study/` owns current Study pair values, pure topology, rename/removal,
  and the separate explicit provider-policy migration. Split-Study grouping and
  archive support were retired on 2026-09-06.
- `../errors.py` owns the shared Profile operation error independently of storage.
- `lifecycle.py` owns ordinary Profile listing, selection, creation, import,
  rename, and removal.

Current Study construction belongs to
`memcommit.application.operations.init_study.profile`: its model, package,
composition, and publication modules own the initialization-only data flow.
The former Profile-model names resolve lazily to those canonical objects for
compatibility, but Profile lifecycle no longer contains their implementation.

Ordinary Profile lifecycle imports the pure current Study topology. Study
lifecycle uses the existing shared storage primitives. The topology imports
configuration, value types, and `profile.errors`, so it does not load the
aggregate model or storage. Current Study exports from the aggregate model are
lazy to preserve object identity without introducing initialization cycles.

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

The initial package extraction preserved all 132 original definition bodies.
The subsequent Study retirement intentionally removes split-only behavior; its
current boundaries and verification are recorded in the
[Study lifecycle rationale](profile-study-lifecycle-design-rationale.md).

## Alternatives and limitation

Keeping exactly three implementation files was rejected because lifecycle,
Grant, and Study operations all depend on the same registry lock and atomic
store primitives; assigning those helpers to one public domain would either
create a cycle or obscure their shared safety role. `_storage.py` is therefore
an internal fourth module rather than duplicated code.

The former `study.py` is now removed. Task/authority identity constants and
package validators used by the maintained legacy debugging scenario now belong
to `init_study/profile/model.py` and `package.py`. They no longer require an
import from Study administration. Existing init-study aliases remain only in
the aggregate Profile model; the duplicate direct-study alias map is retired.
