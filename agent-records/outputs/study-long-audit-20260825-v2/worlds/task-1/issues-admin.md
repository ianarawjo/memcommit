# Task-1 ADMIN issues

## T1-V2-ADMIN-HARNESS-POST-DIGEST-INTERRUPTION — Audit harness interruption lost Eval stdout after the child had exited

- Severity: low
- Classification: audit-harness-infrastructure
- Expected: The world runner should persist the child output and attempt record before an operator interruption can leave a counted call unrecorded.
- Actual: Eval M2 completed a durable 1/1 PASS run and the mandatory post-child identity assertion passed, but Ctrl-C arrived during the subsequent lane digest. The in-process stdout/cost wrapper was lost before phase-admin persistence.
- Workaround: Recover the counted attempt from the unique durable Eval run JSON and exact post-child identity host read; never rerun the mem command.
- Evidence: T1-V2-ADMIN-025

## T1-V2-ADMIN-SAME-PROFILE-CONTEXT-IMPORT-COLLISION — Same-world Context Import cannot create an aliased by-value scratch copy

- Severity: medium
- Classification: operation-boundary/usability
- Expected: Importing a registered task-1 Context by value under a fresh scratch name should either create an independent identity or expose an explicit same-Profile copy route.
- Actual: Both direct and recursive Context Import stopped because the managed source Context UID already existed in the active Study Profile, even though each `--as` destination was fresh. Exact Memory Import into scratch later succeeded.
- Workaround: Use exact Memory Import for a selective by-value copy, or Branch/Copy within the active Profile when source identity already exists.
- Evidence: T1-V2-ADMIN-012, T1-V2-ADMIN-028

## T1-V2-ADMIN-INIT-MISSING-PARENT-AUTO-CREATES — Init creates a missing parent chain without --parents

- Severity: medium
- Classification: functional/creation-boundary
- Expected: `init task-1/participant/admin-v2-scratch/missing-parent/leaf` should reject the absent lexical parent unless `--parents` is supplied, keeping the explicit parent-expansion method distinct.
- Actual: The command exited 0 and initialized the leaf even though `missing-parent` did not exist and `--parents` was absent.
- Workaround: Host-check the parent catalog before Init when missing-parent creation would broaden scope; use `--parents` only when the full chain is intentional.
- Evidence: T1-V2-ADMIN-094
