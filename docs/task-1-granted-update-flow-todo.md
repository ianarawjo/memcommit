# Task 1 granted update flow TODO

## Goal

Make the participant-facing Task 1 flow executable against the run-private
granted campus wiki without copying authority Memories into the participant
Profile or modifying `study-baseline`:

```text
inspect participant/construction-updates
→ query campus-wiki, federating relevant query-only descendants
→ preview verified changes against the granted campus-wiki
→ apply the reviewed update through the editable grant
→ inspect a stable diff and recovery receipts
```

This file is the implementation checklist. Documentation refresh is included,
but it is not a substitute for the runtime work below.

## Required invariants

- The source remains the participant-owned
  `task-1/participant/construction-updates` graph.
- The target remains the run-private authority Profile's granted
  `task-1/campus-wiki` graph. No target copy is materialized in the participant
  Profile.
- `study-baseline` is never a mutation target. A participant update can change
  only the authority Profile created for that Study run.
- `impact` requires target `READ` and discloses only the frozen granted scope.
- `update` additionally requires the exact operation permissions it will use:
  `UPDATE` for replacements, `CREATE` for additions, and `DELETE` for
  whole-Memory removals. Task 1's parent wiki grant will explicitly include
  all three; `UPDATE` must never be interpreted as implicit deletion authority.
- The narrower `construction-details` override remains `QUERY`-only. Neither
  `impact` nor `update` may treat it as readable or writable merely because it
  is below `campus-wiki` in the public namespace.
- Relative locators are resolved once at command start. The canonical source,
  target, active Profile, grant UID/revision, attachment identity, authority
  Profile, Context bindings, and base fingerprints are frozen in the preview
  and revalidated before every write and before answer/result publication.
- Revocation, scope change, authority Context replacement, source/target drift,
  or active-Profile change makes the plan stale and prevents mutation.
- A failed multi-Context application restores already written Contexts and
  does not publish a successful receipt. Crash durability remains an explicit
  prototype boundary until a journal exists.
- `diff`, checkpoints, provenance, and undo/recovery refer to the authority
  Context identities actually changed, while remaining inspectable from the
  participant run.

## Ordered implementation checklist

- [ ] 1. Freeze the executable contract in tests.
  - Cover one participant-owned source and one editable granted target.
  - Assert the query-only descendant is excluded from impact/update input.
  - Assert read-only, query-only, stale, revoked, wrong-attachment, and
    baseline-target cases fail closed.
  - Preserve the compact expected result: two edits, one addition, one
    explicit removal, two unchanged target Memories, and five final Memories.

- [x] 2. Add granted-target support to read-only `mem impact`.
  - Resolve the target through the existing grant resolver rather than
    command-local path parsing.
  - Load only READ-authorized frozen bindings from the run-private authority
    store.
  - Save a plan that records the target as a granted authority view, including
    grant and authority identities, without writing either source or target.
  - Render the same preview contract used for ordinary targets.

- [x] 3. Extend staged-update records and validation for a granted target.
  - Persist the frozen public target name plus authority Profile, grant,
    attachment, binding, and base-digest preconditions.
  - Keep backward compatibility for existing ordinary source/target records.
  - Reject old or incomplete granted-target records rather than inferring
    authority from current global state.

- [ ] 4. Apply `mem update` through the grant under authority-store locks.
  - Recheck the active participant Profile and exact grant snapshot.
  - Check `UPDATE` and `CREATE` per planned operation before the first write.
  - Require the explicitly granted `DELETE` permission for every planned
    whole-Memory removal.
  - Save only the run-private authority Context post-images; never write the
    baseline or concealed query-only descendants.
  - Preserve rollback behavior across all affected authority Contexts.

- [ ] 5. Make receipts, `mem diff`, checkpoints, and recovery grant-aware.
  - Render the reviewed public target while validating the underlying
    authority identities.
  - Ensure repeated update is idempotent and does not reconnect to the provider
    or create duplicate checkpoints.
  - Verify stale/revoked results remain inspectable but cannot be presented as
    current or applied again.

- [ ] 6. Run an end-to-end Study verification.
  - Initialize a fresh two-Profile Study run.
  - Ask a parent wiki question that selects `construction-details` only when
    relevant.
  - Preview and apply the compact Task 1 update against the granted wiki.
  - Confirm the run-private authority changed, the participant source did not,
    and `study-baseline` remained byte-for-byte unchanged.
  - Confirm Task 2/3 grants and query sessions are unaffected.

- [ ] 7. Refresh examples and participant-facing documentation.
  - Replace the obsolete single-Profile/no-grant `init-study` description.
  - Add the parent federated-query example while retaining exact-child and
    `#HANDLE` examples.
  - Update Task 1 permission tables to
    `READ+CREATE+UPDATE+QUERY` for the wiki and
    `QUERY+SESSION_LOG` for `construction-details`.
  - Show which commands are executable and retain any remaining limitation
    explicitly; do not document planned behavior as complete before its tests
    and live verification pass.

## Recommended first slice

Start with checklist items 1 and 2 only: contract tests plus read-only granted
`impact`. This establishes target resolution, scope exclusion, and stale-grant
semantics without crossing the write boundary. Once that preview is stable,
the staged record and mutation path can reuse the same frozen target identity.
