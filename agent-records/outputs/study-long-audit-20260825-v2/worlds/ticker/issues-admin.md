# Ticker ADMIN issues

## TICK-V2-A-STATUS-SNAPSHOT-UID-01 — Recursive Status compares a ContextSnapshotRef occurrence UID to the live target UID

- Severity: `HIGH`
- Classification: `FUNCTIONAL_READ_FAILURE_CONTEXT_SNAPSHOT_IDENTITY`
- Expected: `status --recursive` on `task-2/participant` follows its retained Context snapshot using the snapshot's target Context identity and renders a read-only frame.
- Actual: Status exited 1 with `An embedded Context identity changed during Status.` Host diagnosis shows occurrence UID c458ab18 differs from the live target UID b839b146, while the snapshot's explicit target_context_uid correctly equals b839b146.
- Workaround: Use `status --short`, default direct Status, or an exact direct read that does not follow embedded snapshot occurrences.
- Reproduction: 1/1 recursive Status on the snapshot-bearing task-2/participant Context

## TICK-V2-A-IMPORT-FIXTURE-01 — Cumulative ticker identity collisions invalidated the Admin import/Rename fixture

- Severity: `CAMPAIGN_LIMITATION`
- Classification: `CAMPAIGN_FIXTURE_STABLE_IDENTITY_COLLISION`
- Expected: Admin Context import M1/M2 creates fresh by-value scratch fixtures that positive-control Rename M1/M2 can rename without touching Branch/Checkout targets.
- Actual: The cumulative ticker Profile already contained the task-1 Context stable UIDs, so both imports rejected aliasing the same identities and both dependent Renames found no Source. Branch3 consequently succeeded; the harness stopped before unsafe Checkout3 cloning and continued with an explicit clean-O target-collision route and exact Branch3 Undo/Redo.
- Workaround: Preflight imported stable identities host-side and choose a source Context whose UID is absent from the active cumulative Profile, or reserve init-created scratch fixtures for all positive Renames.
- Reproduction: 2/2 Context imports and their 2/2 dependent positive Renames

## TICK-V2-A-INIT-EXPECTATION-01 — Admin protocol incorrectly expected default Init to reject a missing lexical parent

- Severity: `CAMPAIGN_LIMITATION`
- Classification: `CAMPAIGN_PROTOCOL_EXPECTATION_MISMATCH`
- Expected: The campaign protocol expected `init C/missing-parent/leaf` without `--parents` to fail.
- Actual: Init correctly created only the exact leaf Context and switched to it; no parent Context object exists. The current operation contract reserves parent-Context creation for `--parents`.
- Workaround: Use a collision, invalid UID-shaped name, or another documented validation failure for a negative Init method; treat a missing lexical parent as a valid exact-leaf route.
- Reproduction: 1/1 default exact-leaf Init with an absent parent Context

