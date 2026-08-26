# Task-1 admin execution sheet · prepared, not executed

This is the exact W1 slice of <code>admin-preflight.json</code>. Only sequences 1–100 are the currently executable world-serial prefix. Sequence 101 is the single phase-wide Init-study decision boundary, and sequences 102–105 depend on that outcome. W2 must not begin while W1 Profile/current remains unrestored. Actual <code>mem</code> calls while preparing this sheet: **0**.

## Fixed execution boundary

Launcher: <code>env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/KimMunyeong/.codex/audit-snapshots/memcommit-study-long-audit-20260823-code python -m memcommit.cli</code>

Never override or repurpose <code>HOME</code>, <code>home</code>, or <code>CODEX_HOME</code>. Root holds the global lease; no other world or worker interleaves. Stop after sequence 100 until the one decision covering all six Init-study M5 routes is bound.

## Frozen Source and runtime evidence

Host inventory is limited to each Profile store’s canonical <code>contexts/**/context.json</code>; Profile-root backups are excluded.

| Import | Source Profile | Existing Source Context | Identity boundary |
|---|---|---|---|
| M1 | <code>study-baseline</code> · e2cdbdc7-3db4-4d23-b59e-2a2783545005 · Store 1cbcfb9bb72a3392eb6be707b134e6fb3effe17eab0f472c1ce2072c81f9589f | <code>granted-memory/task-2/advisor1/methods</code> | Context d2f78b99-5dcf-5876-89a9-1058bceca333; digest 33b9da32804d92ffb8ddc7f837a9e508a9f2eec5abf27513d6ec4138e4b34158 |
| M2 | <code>study-baseline</code> · e2cdbdc7-3db4-4d23-b59e-2a2783545005 · Store 1cbcfb9bb72a3392eb6be707b134e6fb3effe17eab0f472c1ce2072c81f9589f | <code>granted-memory/task-1/campus-wiki/construction-details</code> | Context b5756b95-5cd1-55da-b881-5fcdc95f140e; digest 630c954b0d30fb671020ba82bf1ac2cb9accd12162d9596d3b273b20d910688f; 7 globally collision-free recursive Context UIDs |
| M3 | <code>study-baseline</code> · e2cdbdc7-3db4-4d23-b59e-2a2783545005 · Store 1cbcfb9bb72a3392eb6be707b134e6fb3effe17eab0f472c1ce2072c81f9589f | <code>granted-memory/task-2/advisor2/methods</code> | Context 531f5f15-65f7-5315-8ccf-0cea6e53b76a; digest 642b765ead29f6a8ed59aeb31f5930a7cb445109058e80a0ffc747948c93308f; direct Memory 90be328f-1c05-5574-9657-1b0cc04a10b8; content 0fecdff0f7b1204928239ca5665756cbf5dda44709758e5a093df8187927029e |
| M4 | <code>study-baseline</code> · e2cdbdc7-3db4-4d23-b59e-2a2783545005 · Store 1cbcfb9bb72a3392eb6be707b134e6fb3effe17eab0f472c1ce2072c81f9589f | <code>granted-memory/task-2/advisor1/claim-evidence</code> | Context b0c4b50c-f70b-5b0c-a1eb-0fd63e0531bf; digest 15308b056bb219bdec35de15068d4a309d93f59a672224c729cd6a11298fd50c |
| M5 | <code>study-baseline</code> · e2cdbdc7-3db4-4d23-b59e-2a2783545005 · Store 1cbcfb9bb72a3392eb6be707b134e6fb3effe17eab0f472c1ce2072c81f9589f | <code>granted-memory/task-2/advisor2/claim-evidence</code> | Context 1ca4b72a-fcbb-5997-a1b5-f764662460a5; digest 967550d89fb9c9cf10d5e833de81bc40ec81e6c2f57e56516dd00815a691a25f |

Log M3 and Share M2–M5 use the existing nonempty Memory-only direct owner <code>task-1/participant/transform-scratch/source/building-access</code>; its Context UID is <code>48397c4d-5d60-4756-950a-f62e7ea50068</code>, selected Memory UID is <code>6fcde57e-036a-438a-a8a8-76719b5c8db7</code>, and the content digest is <code>be62efd767c7a63ec9464bec484d5501f0f1257db3c07a54d1717c95cad53095</code>. The exact owner/UID/digest and all-Memory item types are host-revalidated before use.

- <code>${BASELINE_IMPORT_MEMORY_UID}</code>: Bind the full exact direct Memory UID/content digest from this world's M3 Source Context before execution; verify it is absent from bare A_W.
- <code>${IMPORTED_MEMORY_UID_FROM_IMPORT_M3}</code>: After M3, bind the same full prebound BASELINE_IMPORT_MEMORY_UID only after the receipt prefix/target and host-read target UID/content digest all match; the receipt alone prints only uid[:8].
- <code>${PHASE_ENTRY_CURRENT}</code>: Bind the host-frozen current at this world's lease entry; only TUI Switch M5 resolves it.
- <code>${EVAL_RUN_ID_FROM_M2_LEDGER}</code>: Host-read the isolated Eval ledger immediately before and after M2; require exactly one new validated record matching started_at, provider codex_chatgpt, model gpt-5.6-sol, reasoning none, and the fixed case, then bind its full run_id. M2 stdout only names the ledger path.
- <code>${PINNED_STUDY_PROVIDER_POLICY_SHA256}</code>: Host-freeze the frozen snapshot policy digest proving codex_chatgpt/gpt-5.6-sol/reasoning none before Eval M2.
- <code>${IMPORT_SOURCE_PROFILE_UID_AND_STORE_SHA256}</code>: Bind the exact per-method Source Profile UID and baseline-store digest from import_sources; revalidate unchanged before/after every Import.
- <code>${IMPORT_SOURCE_CONTEXT_UID_AND_SHA256}</code>: Bind the exact per-method Source Context UID/digest; for M2 bind every recursive member and prove global UID disjointness from active plus earlier imports.
- <code>${WORLD_LOG_MEMORY_CONTEXT}</code>: Bind the exact active-Study direct owner Context from host_source_evidence.world_reads for this world.
- <code>${WORLD_LOG_MEMORY_UID}</code>: Bind that owner's exact direct Memory UID/content digest and verify it still exists immediately before Log M3.

Eval M2 stdout is not a run-ID source. Freeze the isolated ledger record-ID set immediately before and after M2, require exactly one new validated record matching the frozen case/provider/model/reasoning and <code>started_at</code>, bind its full <code>run_id</code>, then let M3 status consume and M4 check that binding.

Import M3 receipt prints only the first eight UID characters. Lock/Unlock M3 use the full prebound Source Memory UID only after the receipt prefix/target and host-read materialized target UID/content digest agree.

## Exact ordered command sheet

Rows sharing a transaction ID are indivisible. Status/Pwd occur only at stable points. M4 Import remains immediately between Undo M4 and stale Redo M4, and its Source Context UID is distinct from every earlier planned import.

| # | Round | Operation | Method | Exact argv | Mode | Decision | Outbound | Transaction/dependency |
|---:|---:|---|---|---|---|---|---|---|
| 1 | 1 | profile | M1 | <code>["profile","list"]</code> | CLI | none | false | — |
| 2 | 1 | config | M1 | <code>["config"]</code> | CLI | none | false | — |
| 3 | 1 | provider | M1 | <code>["provider"]</code> | CLI | none | false | — |
| 4 | 1 | checkout | M1 | <code>["checkout","task-1/participant/transform-scratch"]</code> | CLI | none | false | — |
| 5 | 1 | status | M1 | <code>["status","-s"]</code> | CLI | none | false | task-1:stable-state:m1 |
| 6 | 1 | pwd | M1 | <code>["pwd"]</code> | CLI | none | false | task-1:stable-state:m1 |
| 7 | 1 | init | M1 | <code>["init","task-1/participant/admin-scratch"]</code> | CLI | none | false | task-1:r1:init-undo-redo |
| 8 | 1 | undo | M1 | <code>["undo"]</code> | CLI | none | false | task-1:r1:init-undo-redo |
| 9 | 1 | redo | M1 | <code>["redo"]</code> | CLI | none | false | task-1:r1:init-undo-redo |
| 10 | 1 | branch | M1 | <code>["branch","task-1/participant/admin-scratch/r1-branch","--from","task-1/participant/transform-scratch","--direct"]</code> | CLI | none | false | — |
| 11 | 1 | import | M1 | <code>["import","context","granted-memory/task-2/advisor1/methods","--from-profile","study-baseline","--as","task-1/participant/admin-scratch/import-direct","--direct"]</code> | CLI | none | false | — |
| 12 | 1 | lock | M1 | <code>["lock","--context","task-1/participant/admin-scratch","--direct"]</code> | CLI | none | false | task-1:r1:lock-unlock |
| 13 | 1 | unlock | M1 | <code>["unlock","--context","task-1/participant/admin-scratch","--direct"]</code> | CLI | none | false | task-1:r1:lock-unlock |
| 14 | 1 | log | M1 | <code>["log","--context","task-1/participant/transform-scratch"]</code> | CLI | none | false | — |
| 15 | 1 | eval | M1 | <code>["eval","semantic","status","--ledger-dir","outputs/eval-admin-task-1"]</code> | CLI | none | false | — |
| 16 | 1 | help | M1 | <code>["help"]</code> | CLI | none | false | — |
| 17 | 1 | rename | M1 | <code>["rename","task-1/participant/admin-scratch/r1-branch","task-1/participant/admin-scratch/r1-renamed","--force"]</code> | CLI | none | false | — |
| 18 | 1 | share | M1 | <code>["share"]</code> | CLI | none | false | — |
| 19 | 1 | shell-init | M1 | <code>["shell-init"]</code> | CLI | none | false | — |
| 20 | 1 | switch | M1 | <code>["switch","task-1/participant/transform-scratch"]</code> | CLI | none | false | — |
| 21 | 1 | init-study | M1 | <code>["init-study","study-long-audit-20260823","--from-profile","study-baseline"]</code> | CLI | none | false | — |
| 22 | 2 | profile | M2 | <code>["profile","current"]</code> | CLI | none | false | — |
| 23 | 2 | config | M2 | <code>["config","show"]</code> | CLI | none | false | — |
| 24 | 2 | provider | M2 | <code>["provider","status"]</code> | CLI | none | false | — |
| 25 | 2 | checkout | M2 | <code>["checkout","."]</code> | CLI | none | false | — |
| 26 | 2 | switch | M2 | <code>["switch","./source"]</code> | CLI | none | false | — |
| 27 | 2 | branch | M2 | <code>["branch","task-1/participant/admin-scratch/r2-tree","--from","task-1/participant/transform-scratch","--recursive"]</code> | CLI | none | false | task-1:r2:branch-undo-redo |
| 28 | 2 | undo | M2 | <code>["undo","--keep"]</code> | CLI | none | false | task-1:r2:branch-undo-redo |
| 29 | 2 | redo | M2 | <code>["redo"]</code> | CLI | none | false | task-1:r2:branch-undo-redo |
| 30 | 2 | status | M2 | <code>["status","-b"]</code> | CLI | none | false | task-1:stable-state:m2 |
| 31 | 2 | pwd | M2 | <code>["pwd"]</code> | CLI | none | false | task-1:stable-state:m2 |
| 32 | 2 | init | M2 | <code>["init","task-1/participant/admin-scratch/tree/leaf","--parents"]</code> | CLI | none | false | — |
| 33 | 2 | import | M2 | <code>["import","context","granted-memory/task-1/campus-wiki/construction-details","--from-profile","study-baseline","--as","task-1/participant/admin-scratch/import-tree","--recursive"]</code> | CLI | none | false | — |
| 34 | 2 | lock | M2 | <code>["lock","--context","task-1/participant/admin-scratch","--recursive"]</code> | CLI | none | false | task-1:r2:lock-unlock |
| 35 | 2 | unlock | M2 | <code>["unlock","--context","task-1/participant/admin-scratch","--recursive"]</code> | CLI | none | false | task-1:r2:lock-unlock |
| 36 | 2 | log | M2 | <code>["log","--context","task-1/participant/transform-scratch","--manual"]</code> | CLI | none | false | — |
| 37 | 2 | eval | M2 | <code>["eval","semantic","run","ambiguity","--case","single-none-main-entrance-hours","--runs","1","--provider","codex_chatgpt","--model","gpt-5.6-sol","--reasoning","none","--ledger-dir","outputs/eval-admin-task-1"]</code> | CLI | none | true | task-1:eval:m2-m3-m4 |
| 38 | 2 | help | M2 | <code>["help","which command inspects current orientation?"]</code> | CLI | none | true | — |
| 39 | 2 | rename | M2 | <code>["rename","task-1/participant/admin-scratch/r2-tree","task-1/participant/admin-scratch/r2-renamed","--force"]</code> | CLI | none | false | — |
| 40 | 2 | share | M2 | <code>["share","task-1/participant/transform-scratch/source/building-access","--to","admin-task-1-missing-endpoint"]</code> | CLI | none | false | — |
| 41 | 2 | shell-init | M2 | <code>["shell-init","zsh"]</code> | CLI | none | false | — |
| 42 | 2 | init-study | M2 | <code>["init-study","admin/task-1-invalid","--from-profile","study-baseline"]</code> | CLI | none | false | — |
| 43 | 3 | profile | M3 | <code>["profile","use","study-long-audit-20260823"]</code> | CLI | none | false | — |
| 44 | 3 | config | M3 | <code>["config","set","provider"]</code> | CLI | none | false | — |
| 45 | 3 | provider | M3 | <code>["provider","status","--operation","query"]</code> | CLI | none | false | — |
| 46 | 3 | branch | M3 | <code>["branch","task-1/participant/admin-scratch/r3-from-prior","--from","task-1/participant/admin-scratch/r1-renamed","--direct"]</code> | CLI | none | false | task-1:r3:owned-branch-redo-switch-rename-undo-stable-read |
| 47 | 3 | redo | M3 | <code>["redo"]</code> | CLI | none | false | task-1:r3:owned-branch-redo-switch-rename-undo-stable-read |
| 48 | 3 | switch | M3 | <code>["switch","task-1/participant/admin-scratch/r3-from-prior"]</code> | CLI | none | false | task-1:r3:owned-branch-redo-switch-rename-undo-stable-read |
| 49 | 3 | rename | M3 | <code>["rename",".","task-1/participant/admin-scratch/r3-renamed","--force"]</code> | CLI | none | false | task-1:r3:owned-branch-redo-switch-rename-undo-stable-read |
| 50 | 3 | undo | M3 | <code>["undo"]</code> | CLI | none | false | task-1:r3:owned-branch-redo-switch-rename-undo-stable-read |
| 51 | 3 | status | M3 | <code>["status","-r"]</code> | CLI | none | false | task-1:r3:owned-branch-redo-switch-rename-undo-stable-read |
| 52 | 3 | pwd | M3 | <code>["pwd"]</code> | CLI | none | false | task-1:r3:owned-branch-redo-switch-rename-undo-stable-read |
| 53 | 3 | checkout | M3 | <code>["checkout","-b","task-1/participant/admin-scratch/r3-checkout","--direct"]</code> | CLI | none | false | — |
| 54 | 3 | init | M3 | <code>["init","task-1/participant/admin-scratch"]</code> | CLI | none | false | — |
| 55 | 3 | import | M3 | <code>["import","memory","${BASELINE_IMPORT_MEMORY_UID}","--from-profile","study-baseline","--context","granted-memory/task-2/advisor2/methods","--into","task-1/participant/admin-scratch"]</code> | CLI | none | false | — |
| 56 | 3 | lock | M3 | <code>["lock","--memory","${IMPORTED_MEMORY_UID_FROM_IMPORT_M3}","--context","task-1/participant/admin-scratch"]</code> | CLI | none | false | task-1:r3:lock-unlock |
| 57 | 3 | unlock | M3 | <code>["unlock","--memory","${IMPORTED_MEMORY_UID_FROM_IMPORT_M3}","--context","task-1/participant/admin-scratch"]</code> | CLI | none | false | task-1:r3:lock-unlock |
| 58 | 3 | log | M3 | <code>["log","--memory","${WORLD_LOG_MEMORY_UID}","--context","task-1/participant/transform-scratch/source/building-access"]</code> | CLI | none | false | — |
| 59 | 3 | eval | M3 | <code>["eval","semantic","status","--ledger-dir","outputs/eval-admin-task-1"]</code> | CLI | none | false | task-1:eval:m2-m3-m4 |
| 60 | 3 | help | M3 | <code>["help","Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."]</code> | CLI | none | false | — |
| 61 | 3 | share | M3 | <code>["share","task-1/participant/transform-scratch/source/building-access","--direct","--recursive"]</code> | CLI | none | false | — |
| 62 | 3 | shell-init | M3 | <code>["shell-init","bash"]</code> | CLI | none | false | — |
| 63 | 3 | init-study | M3 | <code>["init-study","study-long-admin-task-1-r3","--from-profile","admin-task-1-missing-baseline"]</code> | CLI | none | false | — |
| 64 | 4 | profile | M4 | <code>["profile","use","admin-task-1-missing"]</code> | CLI | none | false | — |
| 65 | 4 | config | M4 | <code>["config","set","--help"]</code> | CLI | none | false | — |
| 66 | 4 | provider | M4 | <code>["provider","use","codex_chatgpt","--operation","query"]</code> | CLI | none | false | — |
| 67 | 4 | lock | M4 | <code>["lock","--profile"]</code> | CLI | none | false | task-1:r4:profile-lock-rename-unlock |
| 68 | 4 | rename | M4 | <code>["rename","task-1/participant/admin-scratch/r1-renamed","task-1/participant/admin-scratch/r4-protected-rename","--force"]</code> | CLI | none | false | task-1:r4:profile-lock-rename-unlock |
| 69 | 4 | unlock | M4 | <code>["unlock","--profile"]</code> | CLI | none | false | task-1:r4:profile-lock-rename-unlock |
| 70 | 4 | checkout | M4 | <code>["checkout","-b","task-1/participant/admin-scratch/r4-invalidator","--direct"]</code> | CLI | none | false | task-1:r4:checkout-undo-import-redo |
| 71 | 4 | undo | M4 | <code>["undo"]</code> | CLI | none | false | task-1:r4:checkout-undo-import-redo |
| 72 | 4 | import | M4 | <code>["import","context","granted-memory/task-2/advisor1/claim-evidence","--from-profile","study-baseline","--as","task-1/participant/admin-scratch/r4-import-owned","--direct"]</code> | CLI | none | false | task-1:r4:checkout-undo-import-redo |
| 73 | 4 | redo | M4 | <code>["redo"]</code> | CLI | none | false | task-1:r4:checkout-undo-import-redo |
| 74 | 4 | status | M4 | <code>["status","-d","-r"]</code> | CLI | none | false | task-1:stable-state:m4 |
| 75 | 4 | pwd | M4 | <code>["pwd"]</code> | CLI | none | false | task-1:stable-state:m4 |
| 76 | 4 | branch | M4 | <code>["branch","task-1/participant/admin-scratch/r2-renamed","--from","task-1/participant/transform-scratch","--direct"]</code> | CLI | none | false | — |
| 77 | 4 | init | M4 | <code>["init","00000000-0000-4000-8000-000000000000"]</code> | CLI | none | false | — |
| 78 | 4 | log | M4 | <code>["log","--memory","ffffffff-ffff-4fff-8fff-ffffffffffff","--context","task-1/participant/transform-scratch"]</code> | CLI | none | false | — |
| 79 | 4 | eval | M4 | <code>["eval","semantic","check","${EVAL_RUN_ID_FROM_M2_LEDGER}","--ledger-dir","outputs/eval-admin-task-1"]</code> | CLI | none | false | task-1:eval:m2-m3-m4 |
| 80 | 4 | help | M4 | <code>["help","--emit-selection"]</code> | CLI | none | false | — |
| 81 | 4 | share | M4 | <code>["share","task-1/participant/transform-scratch/source/building-access"]</code> | 180×52 adaptive TUI | none | false | — |
| 82 | 4 | shell-init | M4 | <code>["shell-init","zsh"]</code> | CLI | none | false | — |
| 83 | 4 | switch | M4 | <code>["switch","task-1/participant/admin-scratch/admin-preflight-missing"]</code> | CLI | none | false | — |
| 84 | 4 | init-study | M4 | <code>["init-study"]</code> | 180×52 adaptive TUI | none | false | — |
| 85 | 5 | config | M5 | <code>["config","admin-preflight-invalid"]</code> | CLI | none | false | — |
| 86 | 5 | provider | M5 | <code>["provider","probe","--operation","query"]</code> | CLI | none | true | — |
| 87 | 5 | checkout | M5 | <code>["checkout"]</code> | 180×52 adaptive TUI | none | false | — |
| 88 | 5 | init | M5 | <code>["init"]</code> | 180×52 adaptive TUI | none | false | — |
| 89 | 5 | import | M5 | <code>["import"]</code> | 180×52 adaptive TUI | none | false | — |
| 90 | 5 | help | M5 | <code>["help"]</code> | 180×52 adaptive TUI | none | false | — |
| 91 | 5 | share | M5 | <code>["share","--to","task-3/government/healthcare-agent"]</code> | 180×52 adaptive TUI | none | false | — |
| 92 | 5 | branch | M5 | <code>["branch"]</code> | 180×52 adaptive TUI | none | false | task-1:r5:branch-undo-redo |
| 93 | 5 | undo | M5 | <code>["undo"]</code> | CLI | none | false | task-1:r5:branch-undo-redo |
| 94 | 5 | redo | M5 | <code>["redo"]</code> | CLI | none | false | task-1:r5:branch-undo-redo |
| 95 | 5 | lock | M5 | <code>["lock","--context","task-1/participant/admin-scratch/admin-preflight-missing","--direct"]</code> | CLI | none | false | — |
| 96 | 5 | unlock | M5 | <code>["unlock","--context","task-1/participant/admin-scratch/admin-preflight-missing","--direct"]</code> | CLI | none | false | — |
| 97 | 5 | rename | M5 | <code>["rename","task-1/participant/admin-scratch/r5-missing-old","task-1/participant/admin-scratch/r5-renamed","--force"]</code> | CLI | none | false | — |
| 98 | 5 | log | M5 | <code>["log","--actions"]</code> | CLI | none | false | — |
| 99 | 5 | eval | M5 | <code>["eval","semantic","check","admin-task-1-missing-run-id","--ledger-dir","outputs/eval-admin-task-1"]</code> | CLI | none | false | — |
| 100 | 5 | shell-init | M5 | <code>["shell-init","zsh"]</code> | CLI | none | false | — |
| 101 | 5 | init-study | M5 | <code>["init-study","study-long-admin-task-1-r5","--from-profile","study-baseline"]</code> | PENDING PHASE DECISION | init_study_durable_residue | false | task-1:r5:decision-restore-stable-read |
| 102 | 5 | profile | M5 | <code>["profile"]</code> | PENDING GATE · 180×52 adaptive TUI | depends_on_init_study_decision | false | task-1:r5:decision-restore-stable-read |
| 103 | 5 | switch | M5 | <code>["switch"]</code> | PENDING GATE · 180×52 adaptive TUI | depends_on_init_study_decision | false | task-1:r5:decision-restore-stable-read |
| 104 | 5 | status | M5 | <code>["status"]</code> | PENDING GATE | depends_on_init_study_decision | false | task-1:stable-state:m5 |
| 105 | 5 | pwd | M5 | <code>["pwd"]</code> | PENDING GATE | depends_on_init_study_decision | false | task-1:stable-state:m5 |

## Gate schedule

- Execute W1 sequences 1–100 only before the decision.
- Approve: W1 101 Init-study → 102 Profile exact restore → 103 Switch entry-current restore → 104 Status → 105 Pwd, then W2 begins.
- Decline: a separately reviewed meaningful no-create Init-study M5 route must be bound, or the phase stops incomplete. Profile M5 uses its declined already-active cancel branch; W2 still cannot begin before W1 102–105 finish.
- The aggregate 600 <code>none</code> cells are a classification total, not a pre-gate executable prefix.

## Adaptive 180×52 TUI contracts

Each TUI uses the fixed launcher, <code>TERM=xterm-256color</code>, <code>COLORTERM=truecolor</code>, <code>NO_COLOR</code> unset, and 180×52. Before every key, capture the screen and satisfy the per-step predicate. Static row counts are forbidden; concrete keys and capture digests are appended only after execution. On mismatch or transition limit, Escape unwinds without Apply.

### 81 · share M4

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/081-share-m4</code>
- Search text: <code>task-1/participant/transform-scratch/source/building-access</code>, <code>task-3/government/healthcare-agent</code>
- Common actions: use fixed Source task-1/participant/transform-scratch/source/building-access → select endpoint task-3/government/healthcare-agent → open preview → choose Close/Escape; never Apply
- Before-key predicate: The 180x52 capture visibly shows the operation-owned share surface, expected focus for step 1, no unexpected mutation receipt, and the next semantic target/action can be matched without relying on row count.
- Allowed keys: <code>Tab</code>, <code>Shift-Tab</code>, <code>Up</code>, <code>Down</code>, <code>Enter</code>, <code>Escape</code>, <code>Backspace</code>, <code>printable UTF-8 text</code>; max transitions: 80
- Forbidden: Apply; Approve; Create; Send; Import confirmation; any key whose visible label commits durable state
- Expected/stop: cancelled_no_delivery; Share closed receipt states nothing was sent
- Apply forbidden: yes; concrete runtime keys initially: <code>[]</code>

### 84 · init-study M4

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/084-init-study-m4</code>
- Search text: <code>study-long-admin-task-1-r4-preview</code>, <code>Enter create</code>, <code>Esc cancel</code>
- Common actions: type exact proposed Study name study-long-admin-task-1-r4-preview in the single name field → after the exact name and footer are visible, press Escape directly; never Enter
- Before-key predicate: The single 5-line Init-study name field is visible and focused, no creation receipt or second layer is visible, and the footer reads exactly Enter create · Esc cancel.
- Allowed keys: <code>Escape</code>, <code>Backspace</code>, <code>printable UTF-8 text</code>; max transitions: 40
- Forbidden: Enter; Create; Apply; Approve; any nonexistent second-layer navigation; any key whose visible label commits durable state
- Expected/stop: cancelled; Escape closes the single Init-study name-field screen; no participant/authority Profile is created and registry generation/active Profile remain unchanged.
- Apply forbidden: yes; concrete runtime keys initially: <code>[]</code>

### 87 · checkout M5

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/087-checkout-m5</code>
- Search text: <code>task-1/participant/admin-scratch/r1-renamed</code>
- Common actions: select known retained Context task-1/participant/admin-scratch/r1-renamed → verify it differs from the current r3-checkout Context → confirm selection
- Before-key predicate: The 180x52 Checkout capture visibly shows expected focus for step 1, exact target task-1/participant/admin-scratch/r1-renamed, current is not that target, and no unexpected mutation receipt.
- Allowed keys: <code>Tab</code>, <code>Shift-Tab</code>, <code>Up</code>, <code>Down</code>, <code>Enter</code>, <code>Escape</code>, <code>Backspace</code>, <code>printable UTF-8 text</code>; max transitions: 80
- Approval: Enter/approval is permitted only after the current capture visibly contains the exact selected semantic target (task-1/participant/admin-scratch/r1-renamed) and the runner records a host-computed digest of that exact visible target/review state; otherwise Escape/back immediately.
- Forbidden: none beyond the visible-state contract
- Expected/stop: current_changed; receipt/current equals task-1/participant/admin-scratch/r1-renamed and differs from pre-attempt current
- Apply forbidden: no; concrete runtime keys initially: <code>[]</code>

### 88 · init M5

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/088-init-m5</code>
- Search text: <code>task-1/participant/admin-scratch/r5-init</code>
- Common actions: enter exact name task-1/participant/admin-scratch/r5-init → wait for valid-name state → Escape/cancel before create
- Before-key predicate: The 180x52 capture visibly shows the operation-owned init surface, expected focus for step 1, no unexpected mutation receipt, and the next semantic target/action can be matched without relying on row count.
- Allowed keys: <code>Tab</code>, <code>Shift-Tab</code>, <code>Up</code>, <code>Down</code>, <code>Enter</code>, <code>Escape</code>, <code>Backspace</code>, <code>printable UTF-8 text</code>; max transitions: 80
- Forbidden: Apply; Approve; Create; Send; Import confirmation; any key whose visible label commits durable state
- Expected/stop: cancelled; Init cancelled receipt and target remains absent
- Apply forbidden: yes; concrete runtime keys initially: <code>[]</code>

### 89 · import M5

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/089-import-m5</code>
- Search text: <code>CONTEXT</code>, <code>study-baseline</code>, <code>granted-memory/task-2/advisor2/claim-evidence</code>, <code>DIRECT</code>, <code>task-1/participant/admin-scratch/r5-import-cancel</code>
- Common actions: select CONTEXT kind → select Source profile study-baseline → select Source granted-memory/task-2/advisor2/claim-evidence → select DIRECT → enter target task-1/participant/admin-scratch/r5-import-cancel → reach preview after UID-collision validation passes → Escape/cancel before import
- Before-key predicate: The 180x52 Import capture visibly shows the expected frame/focus for step 1, the exact mapped Source/target when applicable, no UID-collision or mutation receipt, and the next action can be matched without row counts.
- Allowed keys: <code>Tab</code>, <code>Shift-Tab</code>, <code>Up</code>, <code>Down</code>, <code>Enter</code>, <code>Escape</code>, <code>Backspace</code>, <code>printable UTF-8 text</code>; max transitions: 80
- Forbidden: Apply; Approve; Create; Send; Import confirmation; any key whose visible label commits durable state
- Expected/stop: cancelled; Import cancelled receipt and target remains absent
- Apply forbidden: yes; concrete runtime keys initially: <code>[]</code>

### 90 · help M5

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/090-help-m5</code>
- Search text: <code>A–Z</code>, <code>switch</code>, <code>Forms</code>, <code>← back</code>, <code>Q/Esc close</code>
- Common actions: choose the A–Z inventory view using only the visibly focused view control → navigate the A–Z operation rows until the exact switch row is visibly focused → press Enter once on the focused switch row to expand Forms → after switch Forms and the ← back token are visible, press Left once to collapse → after the switch row is collapsed and Q/Esc close is visible, press Escape once to close
- Before-key predicate: The Help command inventory and INVENTORY VIEW control are visible, A–Z is an exact visible choice, and focus movement can be verified before Left/Right changes the view.
- Allowed keys: <code>Tab</code>, <code>Shift-Tab</code>, <code>Up</code>, <code>Down</code>, <code>Home</code>, <code>End</code>, <code>PageUp</code>, <code>PageDown</code>, <code>Left</code>, <code>Right</code>, <code>Enter</code>, <code>Escape</code>, <code>Q</code>; max transitions: 160
- Approval: Enter is permitted exactly once only while the visible focused operation row is switch and its Forms are collapsed; Enter only expands Forms and must not return a command selection.
- Forbidden: search input; printable query entry; SYNTAX layer; Escape as back-navigation; H full-help/static-help path; returning a command selection; any mutation or approval action
- Expected/stop: closed_no_mutation; After Left collapses the switch Forms, one Escape closes the Help inventory with no command selection or durable mutation.
- Apply forbidden: no; concrete runtime keys initially: <code>[]</code>

### 91 · share M5

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/091-share-m5</code>
- Search text: <code>task-1/participant/transform-scratch/source/building-access</code>, <code>task-3/government/healthcare-agent</code>
- Common actions: use fixed endpoint task-3/government/healthcare-agent → select Source task-1/participant/transform-scratch/source/building-access → open preview → choose Close/Escape; never Apply
- Before-key predicate: The 180x52 capture visibly shows the operation-owned share surface, expected focus for step 1, no unexpected mutation receipt, and the next semantic target/action can be matched without relying on row count.
- Allowed keys: <code>Tab</code>, <code>Shift-Tab</code>, <code>Up</code>, <code>Down</code>, <code>Enter</code>, <code>Escape</code>, <code>Backspace</code>, <code>printable UTF-8 text</code>; max transitions: 80
- Forbidden: Apply; Approve; Create; Send; Import confirmation; any key whose visible label commits durable state
- Expected/stop: cancelled_no_delivery; Share closed receipt states nothing was sent
- Apply forbidden: yes; concrete runtime keys initially: <code>[]</code>

### 92 · branch M5

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/092-branch-m5</code>
- Search text: <code>task-1/participant/transform-scratch</code>, <code>DIRECT</code>, <code>task-1/participant/admin-scratch/r5-branch</code>
- Common actions: select Source task-1/participant/transform-scratch → select DIRECT reach → enter fresh target task-1/participant/admin-scratch/r5-branch → review exact target and create
- Before-key predicate: The 180x52 capture visibly shows the operation-owned branch surface, expected focus for step 1, no unexpected mutation receipt, and the next semantic target/action can be matched without relying on row count.
- Allowed keys: <code>Tab</code>, <code>Shift-Tab</code>, <code>Up</code>, <code>Down</code>, <code>Enter</code>, <code>Escape</code>, <code>Backspace</code>, <code>printable UTF-8 text</code>; max transitions: 80
- Forbidden: none beyond the visible-state contract
- Expected/stop: created; creation receipt names task-1/participant/admin-scratch/r5-branch
- Apply forbidden: no; concrete runtime keys initially: <code>[]</code>

### 102 · profile M5

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/102-profile-m5</code>
- Search text: <code>study-long-audit-20260823</code>, <code>${ORIGINAL_STUDY_PROFILE_UID}</code>
- Common actions: bind the same world's Init-study M5 approved/declined outcome before TUI launch
- Before-key predicate: The gate outcome, original Study name/UID, and expected active Profile are host-bound before the first key; otherwise do not launch.
- Allowed keys: <code>Tab</code>, <code>Shift-Tab</code>, <code>Up</code>, <code>Down</code>, <code>Enter</code>, <code>Escape</code>, <code>Backspace</code>, <code>printable UTF-8 text</code>; max transitions: 80
- Forbidden: none beyond the visible-state contract
- Expected/stop: branch_bound_original_profile_restore_or_unchanged_cancel; Use only the bound branch stop predicate and host-verify the original Study Profile UID before continuing
- Apply forbidden: no; concrete runtime keys initially: <code>[]</code>
- approved actions: verify the newly created participant Profile is active → search/focus original study-long-audit-20260823 row → verify frozen original Profile UID and exact row digest → confirm selection to restore original Study → verify restoration receipt
- approved approval: Enter is allowed only when the exact original Study name, frozen original Profile UID, and recorded visible-row digest match.; expected/stop: original_profile_restored; receipt and host-read active Profile equal the frozen original Study UID
- declined actions: verify original study-long-audit-20260823 is already active → focus that exact active row without selecting another Profile → Escape/cancel without switching → verify unchanged active Profile UID
- declined approval: none; expected/stop: unchanged_cancel; Profile TUI closed and the original active Profile UID remains unchanged
- Branch binding: Bind the same world's Init-study M5 ledger outcome before TUI launch; never reuse an early cancel as restoration.

### 103 · switch M5

- Capture: <code>outputs/study-long-audit-20260823/worlds/task-1/admin-tui/103-switch-m5</code>
- Search text: <code>${PHASE_ENTRY_CURRENT}</code>
- Prelaunch binding: bind its exact ordinary local Context name, UID, and digest; prove it is materialized/selectable, not a granted or query route, and different from the host-read pre-attempt current.
- Common actions: navigate the picker until the exact host-bound phase-entry Context name ${PHASE_ENTRY_CURRENT} is visibly focused → after the focused row is proven selectable, materialized, and different from the pre-attempt current, press Enter once to switch
- Before-key predicate: The prelaunch host binding is valid, picker navigation remains on ordinary local materialized rows, and each movement is checked against the exact target name ${PHASE_ENTRY_CURRENT} without selecting any other row.
- Allowed keys: <code>Up</code>, <code>Down</code>, <code>Home</code>, <code>End</code>, <code>PageUp</code>, <code>PageDown</code>, <code>Enter</code>, <code>Escape</code>; max transitions: 160
- Approval: Enter is permitted exactly once only when the visibly focused row name is ${PHASE_ENTRY_CURRENT}, host revalidation matches its ordinary local Context UID/digest, the row is materialized/selectable, and the pre-attempt current is different; otherwise Escape.
- Forbidden: selecting any granted route; selecting any query route; Enter on any row other than the exact phase-entry ordinary local Context; requiring LOCAL/GRANT/QUERY ONLY to be simultaneously visible
- Expected/stop: entry_current_restored; Switch receipt and host-read current equal the bound exact ordinary local Context ${PHASE_ENTRY_CURRENT}, and differ from the recorded pre-attempt current.
- Apply forbidden: no; concrete runtime keys initially: <code>[]</code>

## Atomic ledger procedure

Before each row, populate <code>pre_host</code> and <code>resolved_argv</code>, including exact Source Profile/store, Context/subtree, Memory, Log/Share owner, Eval ledger-set, current/Profile, config/provider, command-stack/redo, lock, and admin/non-admin digests. Atomically replace <code>phase-admin.partial.json</code>. After exit, record exit/stdout/stderr, outbound attempt, TTY captures/keys, post-host state, recovery proof, and defects, then atomically replace again. A mismatch stops W1; no unledgered cleanup is allowed.
