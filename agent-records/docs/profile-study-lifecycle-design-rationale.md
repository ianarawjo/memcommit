# Current Study lifecycle and split-Study retirement

## Motivation and scope

The 1,152-line `profile/model/study.py` combined current pair topology, legacy
split-Study validation, archive filesystem transactions, rename/removal,
provider-policy migration, and aliases for initialization code already moved
elsewhere. The user approved retiring split-Study administration before
separating the remaining responsibilities. This supersedes the earlier decision
to keep all Study administration in one Profile-model module.

A split Study used `STUDY_RUN_TASK`/`STUDY_RUN_AUTHORITY` records for three Task
Profiles and optional matching Authority Profiles. A current Study uses one
`STUDY_RUN` participant and one `STUDY_RUN_GRANTED_MEMORY` authority. The
maintained `init-study --scenario legacy` debugging scenario creates the latter
pair; its scenario data is not retired by this change.

## Ownership and dependencies

- `profile/study/model.py` owns `StudyRunProfilePair`, `StudyRenameResult`, and
  `StudyRemovalResult`.
- `profile/study/topology.py` validates pair provenance and resolves one Study
  display label to its stable member identities. It performs no filesystem I/O
  and imports neither storage nor lifecycle.
- `profile/study/lifecycle.py` owns `rename_study` and `remove_study`, including
  lock acquisition, review preconditions, registry construction, and receipts.
- `profile/study/provider_policy_migration.py` retains the explicit pilot
  policy migration and its result type. It is independently callable from
  `scripts/migrate_study_fast_mode.py`; ordinary topology does not load it.
- `profile/errors.py` owns the shared `ProfileError` class. `_storage.py`
  re-exports that same class. Locating the error outside the aggregate model
  package lets pure topology load without starting storage or creating an
  import cycle through ordinary Profile lifecycle.
- `profile/model/_storage.py` continues to own shared registry and destructive
  store primitives. No transaction primitive is duplicated in Study code.
- Init-study task/authority constants belong to `init_study/profile/model.py`;
  package UUID/digest validation belongs to `init_study/profile/package.py`.

Production callers import these narrow owners. The old physical
`profile/model/study.py` is removed. The aggregate `profile.model` lazily
preserves current Study public objects and existing init-study aliases with one
init-study alias map. Retired grouping/archive names are no longer exported.
The current `profile/study/__init__.py` is deliberately lightweight.

## Retired behavior

`profile archive-study`, legacy group projection, split-specific name
reservation, whole-group rename, and archive manifest publication/retry are
removed together with their tests. The picker accepts only the current two
Study roles; it no longer carries Task ordinals or an instruction to rename
legacy member Profiles. Study rename results no longer report a legacy-only
member-name update count.

This change performs no registry migration, archive cleanup, or user-store
mutation. Existing arbitrary source metadata remains readable under the
ordinary Profile contract. A persisted split record is no longer grouped,
name-reserved, or addressable as a Study; its individual managed Profile remains
an ordinary Profile. Historical archive manifests and stores remain untouched,
and no restore command is introduced.

## Preserved contracts

- A current pair requires exactly one participant and one authority, consistent
  shared provenance, and a unique case-insensitive Study name. Removed member
  records remain available for grouping the surviving visible member.
- Study selection resolves the shared Study label, independently of member
  Profile names. Both stable member UIDs are preserved across Study rename.
- Rename updates only `source.study_name` in one registry generation. Member
  names, stores, Grants, active Profile, and prior action-ledger events remain
  unchanged. Exact no-ops publish nothing; case-only renames remain real changes.
- Picker mutations revalidate the reviewed UID and registry generation under
  the same registry lock used for publication.
- Removal rejects an active member, validates stores, prepares deletion,
  publishes registry/grant/tombstone updates, and uses the existing rollback
  and final-destruction boundary. Partially removed current pairs remain removable.
- A visible rename followed by a durability failure remains renamed; an error
  before replacement preserves the old registry. Failure receipts keep this
  distinction instead of claiming a rollback that did not happen.
- Provider-policy migration retains its original accepted-source, complete-pair,
  all-or-nothing update, and removed-tombstone exclusion behavior.

## Alternatives and limits

Moving the old file into several modules while retaining archive and split
support was rejected because those features were explicitly retired. Removing
all code or fixtures named `legacy` was rejected because the current debugging
scenario and old provider-policy pins are independent contracts. Provider-policy
migration remains separate until support for historical policies is explicitly
retired; a current local registry alone cannot establish that boundary for other
installations.

No universal Study persistence abstraction or general transaction framework is
introduced. The existing Profile storage primitives remain authoritative. This
change does not retire older scenario package formats, policy versions, or
arbitrary historical Profile provenance.

## Verification

Focused tests cover pair integrity, target identity, current import identity and
import order, storage-free topology imports, absence of the archive command,
current rename/removal, initialization of both scenarios, migration, and picker
interaction. Retired split-only tests are removed rather than silently adapted
into tests of a different feature. A real color PTY replay records the retained
current Study rename/removal flows and read-only verification in the companion
[snapshot record](screenshots/profile-study-lifecycle-20260906/README.md).

Validation completed in the primary checkout with `PYTHONPATH=src`: 233 distinct
tests passed across Profile/Study regression, initialization and fixture,
provider-policy, shared picker, package import, Help, and callable-catalog suites.
AST comparison confirms that current pair grouping, removal, and provider-policy
migration function bodies are unchanged. Ruff import/name checks, focused diff
whitespace checks, `verify_operation_evidence.py --check`, and
`generate_callable_catalog.py --check` passed. The 11-step PTY replay verified
rename identity/content preservation and complete removal in an isolated store.

The isolated commit snapshot also passes all 146 Profile/Study and picker tests.
Its additional callable-catalog suite has five passes and one existing failure:
Meld is authored as `MIXED`, while the test expects `CLOSED`. Both values already
exist in the parent commit; this Study change does not alter that route judgment.
Evidence and callable-catalog generation checks pass for the commit snapshot.
