# Profile soft-removal design rationale

## Motivation

Repeated Study runs register a participant Profile and a granted-memory
Profile. The Profile selector can therefore become crowded even when old runs
must remain available for later research reconstruction. People also need to
remove one visible child without accidentally removing its sibling, while a
whole Study action should target the header's complete membership.

## Command and interaction contract

- `mem profile remove PROFILE` removes only that Profile from direct selection.
- `mem profile remove-study STUDY` removes every current or legacy member of
  that Study in one registry generation.
- In the Profile TUI, Study headers are keyboard rows. `D` on a header reviews
  `remove-study`; `D` on a Profile child reviews `remove`. `A` applies only the
  exact frozen command, and Escape returns without mutation.
- Enter continues to select only Profile rows. A Study header is a grouping and
  removal target, never an implicit Profile selection.

Removal is deliberately soft. The registry retains the Profile entry, stable
UID, source provenance, store path, and Grants, while
`removed_profile_uids` controls live visibility. The list, picker, and direct
Profile switching exclude removed identities. A remaining Study child can
therefore keep using a READ Grant backed by its hidden sibling.

## Invariants

1. The fixed `authoring` and `study-baseline` Profiles cannot be removed.
2. The active Profile cannot be removed. A Study containing it cannot be
   removed; the person must select another Profile first.
3. Study membership is resolved from validated provenance and stable Study UID,
   never from a Profile-name suffix.
4. Removing one Study child does not break the validated two-Profile or legacy
   Study topology. All entries and Grants remain registered.
5. The reviewed registry generation and target UID are revalidated under the
   registry lock before a TUI action is applied.
6. A target store is validated before publishing its removal tombstone. Its
   stable path remains in place so an already-running process can finish.
7. Registry mutations unrelated to removal preserve every existing tombstone.
8. No removal path deletes Memory content, sessions, checkpoints, or external
   exports.

## Persistence and compatibility

Profile registry schema version 3 adds the ordered `removed_profile_uids`
field. Versions 1 and 2 load with an empty removed set and migrate on the next
registry write. A removed UID must still identify a registered managed Profile;
the authoring UID and active UID are rejected. Ordering follows the Profile
registry so equivalent states serialize deterministically.

`archive-study` retains its existing legacy detach behavior for compatibility.
Unlike soft removal, that command unregisters a complete legacy group after
writing an archive manifest. The new commands cover current Study pairs and
individual child visibility without rewriting the older archival contract.

## Alternatives considered

Immediate recursive deletion was rejected. A process resolves its Profile
store before a command runs, so deleting or moving that directory could break
an in-flight operation. It would also make an accidental TUI key irreversible.

Unregistering one child was rejected because current Study validation requires
both participant and granted-memory roles, and Grants require both endpoint
Profile UIDs to remain registered. Reclassifying the sibling as an ordinary
Profile would destroy provenance needed by later study analysis.

Treating any child removal as whole-Study removal was rejected because the
visible hierarchy already communicates two different target scopes. A
focusable header makes the whole-Study boundary explicit.

## Limitations and follow-up

This change does not reclaim disk space and does not yet expose a trash,
restore, or permanent purge command. A future purge needs its own review and a
process-lease boundary before deleting stable store paths. Removed Profiles can
continue to serve existing Grants as hidden Study dependencies, but they cannot
be selected directly or used as endpoints for a newly created Grant.
