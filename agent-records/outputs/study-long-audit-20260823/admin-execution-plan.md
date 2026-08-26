# Admin phase execution plan · 2026-08-23

## Outcome

Phase 3 will execute 21 public operations × 5 methods × 6 worlds = **630
ledgered attempts**, interleaved by round and globally serialized. No admin
operation was executed while writing this plan.

The executable plan uses the fixed live Study Profile
`study-long-audit-20260823` and one root-owned global serial transaction. Every
attempt uses the restart-stable source snapshot:

`env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/KimMunyeong/.codex/audit-snapshots/memcommit-study-long-audit-20260823-code python -m memcommit.cli ...`

The live repository package must never be imported for an attempt. No command,
shell wrapper, subprocess, or TUI may override or repurpose `HOME`, `home`, or
`CODEX_HOME`.

### Rejected alternative: temporary HOME clones

The first draft proposed process-local `HOME` overrides pointing at physical
copies of `.mem` and `.mem-profiles`. That design is **not executable** under
the environment boundary: `HOME`/`home`/`CODEX_HOME` may not be overridden or
repurposed. It is retained here only as a rejected alternative; no launcher,
cleanup rule, or safety claim below depends on it.

The live serial transaction is required by the frozen contracts:

- `status`, `pwd`, `undo`, and `redo` have no explicit Context operand.
- `branch`, `checkout -b`, `init`, `switch`, and `rename` can change global
  current.
- `config set` writes machine-global `~/.mem/config.json`, has no unset
  command, and exposes no command-level compare-and-swap.
- the Study's Provider policy is pinned; Provider editing another Profile is
  outside this phase.
- `profile` and `init-study` edit the global registry; every successful
  `init-study` creates a participant/authority pair and selects the participant.
- `undo` and `redo` use one active-Profile command stack rather than a named
  Context.
- `share` can cross a Profile boundary immediately when both explicit operands
  are supplied.

## Evidence used

This plan follows [PHASES.md](PHASES.md), all six core ledgers/issues, all six
transform ledgers/issues sidecars, and the frozen command source. The
practice-source transform ledger validates 24 operations × 5 attempts, its
`issues-transform.md` sidecar is present, and both confirm that
`practice/source` remained read-only. W6 has no remaining evidence-sidecar
preflight gap.

Relevant already-observed constraints are:

- all six worlds repeatedly suffered whole-Profile orientation overload;
- task-1/task-2/task-3 proved that Status is current-only;
- task-1/task-2/task-3/ticker proved implicit saved state can bleed across
  concurrent worlds;
- task-3 ended fail-closed and explicitly made external Share a human decision;
- task-3 and practice-source require safety conditions to remain adjacent to
  the facts they govern;
- ticker and a-is-apple provide synthetic corpora suitable for provider probes
  without transmitting personal material.

## Live serial transaction protocol

Root owns one global lease for the complete active Profile/current/config/
provider/command-stack interval. No worker or parallel phase may invoke `mem`
while that lease is held.

At phase entry and before every world, use host-level read-only inspection to
freeze:

- active Profile UID/name and registry generation/digest;
- current Context;
- complete config JSON bytes/digest;
- effective pinned Provider policy/digest;
- command-stack head and redo state;
- protection records under that world's `A_W` namespace.
- registered `study-baseline` and `teststudy0803` Profile UIDs, complete
  Source-store digests, and the selected Import Source Context/Memory UID and
  content digests. Inventory is restricted to each live Store's canonical
  `contexts/**/context.json`; Profile-root backups are excluded.

Host-level inspection may read files but must not edit them. It is not a `mem`
attempt.

For each world:

1. Profile must be `study-long-audit-20260823`.
2. All Context content, namespace, protection, Import, Branch, Init, Rename,
   Undo, and Redo writes must resolve under `A_W`. `R_W` is read-only Source.
   Import alone reads from a mapped separate read-only Source Profile via the
   exact method map below; it never names the active Study as Source.
3. Every current-changing Branch/Checkout/Init/Rename/Switch attempt runs under
   the same lease. Switch M5 is the counted operation that restores the
   captured entry current; no sixth cleanup Switch is allowed.
4. Lock/Unlock M1–M3 are strictly adjacent pairs. M4 is one transactional
   bracket—Lock M4 → the counted protected Rename M4 probe → Unlock M4—and no
   other command may enter it. Every bracket finishes unlocked. M5 is a
   no-policy-change missing/already-unlocked boundary.
5. Undo/Redo use only admin-operation producers under `A_W` and are immediately
   adjacent as specified below; no setup Add/Edit/Delete command is allowed.
6. Config uses only reads and parser/validation failures. No Config attempt may
   reach a write handler; config bytes must remain identical throughout.
7. Provider/Profile default behavior is read, probe, unchanged-use, missing, or
   pinned-policy rejection. No other Profile is selected or edited.
8. Admin Contexts remain as auditable phase evidence. They are not deleted or
   moved at cleanup, because an extra `mem` cleanup would exceed coverage.
9. After Switch M5 (and Profile M5 if an approved Init-study success occurred),
   verify active Profile/current/config/provider and every non-admin Context
   against the frozen entry snapshot.

A mismatch outside `A_W` stops the phase immediately. Recovery may use only an
already-counted owned Undo/Redo pair; otherwise leave the phase incomplete and
never issue an unledgered cleanup command.

## World substitution table

Every operation matrix below is the Cartesian product of its five methods with
all six rows here. Thus each section defines 30 attempts, not five samples.

| Key | Goal root `R_W` | Admin-only namespace `A_W` | Goal boundary |
|---|---|---|---|
| W1 task-1 | `task-1/participant/transform-scratch` | `task-1/participant/admin-scratch` | Never mutate or Share campus authority/granted sources. |
| W2 task-2 | `task-2/participant/transform-scratch` | `task-2/participant/admin-scratch` | Preserve equal authority; imports/branches stay labeled by source. |
| W3 task-3 | `task-3/local/transform-scratch` | `task-3/local/admin-scratch` | No healthcare delivery without exact human approval. |
| W4 ticker | `audit/ticker/transform-scratch` | `audit/ticker/admin-scratch` | Synthetic data; suitable for bounded provider probes. |
| W5 a-is-apple | `audit/a-is-apple/transform-scratch` | `audit/a-is-apple/admin-scratch` | Synthetic data; keep mapping provenance visible. |
| W6 practice-source | `practice/audit-workspace/transform-scratch/source` | `practice/audit-workspace/admin-scratch` | Use the existing materialized Memory-only child as the read root; keep the admin namespace disjoint and never edit `practice/source`. |

### Cross-Profile Import source map

Every Source is host-frozen from a registered, read-only, non-active Profile.
Freeze that method's Profile UID, complete Store digest, exact Source Context
UID/digest, and—at M3—the exact directly owned Memory UID/content digest. The
canonical inventory excludes Profile-root backups.

| World | M1 direct | M2 recursive | M3 direct Memory owner | M4 direct | M5 TUI preview/cancel |
|---|---|---|---|---|---|
| W1 | `study-baseline:granted-memory/task-2/advisor1/methods` | `study-baseline:granted-memory/task-1/campus-wiki/construction-details` | `study-baseline:granted-memory/task-2/advisor2/methods` | `study-baseline:granted-memory/task-2/advisor1/claim-evidence` | `study-baseline:granted-memory/task-2/advisor2/claim-evidence` |
| W2 | `study-baseline:granted-memory/task-2/advisor1/terminology` | `study-baseline:granted-memory/task-2/proposal-submission-guidelines` | `study-baseline:granted-memory/task-2/advisor2/terminology` | `study-baseline:granted-memory/task-2/advisor1/compensation` | `study-baseline:granted-memory/task-2/advisor2/compensation` |
| W3 | `study-baseline:granted-memory/task-2/advisor1/reproducibility` | `study-baseline:granted-memory/task-3/remote/government/healthcare-agent/info-request/questions-and-answers` | `study-baseline:granted-memory/task-2/advisor2/reproducibility` | `study-baseline:granted-memory/task-2/advisor1/ethics` | `study-baseline:granted-memory/task-2/advisor2/ethics` |
| W4 | `study-baseline:granted-memory/task-2/advisor1/style` | `study-baseline:granted-memory/task-3/remote/government/healthcare-agent/info-request/transmission-guidance` | `study-baseline:granted-memory/task-2/advisor2/style` | `study-baseline:granted-memory/task-2/advisor1/review` | `study-baseline:granted-memory/task-2/advisor2/review` |
| W5 | `study-baseline:granted-memory/task-2/advisor1/scope` | `teststudy0803:granted-memory/task-3/guardrails` | `study-baseline:granted-memory/task-2/advisor2/scope` | `study-baseline:granted-memory/task-2/advisor1/emphasis` | `study-baseline:granted-memory/task-2/advisor2/emphasis` |
| W6 | `study-baseline:granted-memory/task-2/advisor1/safety` | `teststudy0803:granted-memory/task-3/government/healthcare-agent/information-request` | `study-baseline:granted-memory/task-2/advisor2/safety` | `study-baseline:granted-memory/task-2/advisor1/evaluation` | `study-baseline:granted-memory/task-2/advisor2/evaluation` |

Host inspection verified each M3 Context has a direct Memory and every M2 root
has a nontrivial, closed recursive subtree. The complete planned M1/M2/M4
Context-UID sets are pairwise disjoint and absent from the active Profile. M3
imports its exact Memory into bare `A_W`, where its target-local UID is also
proven absent. M5 uses an existing still-unimported Source and cancels before
Apply. This separates Context Import's global UID rule from Memory Import's
target-Context-local rule.

### Memory-only Log/Share source map

`S_W` is an existing active-Study Context containing at least one direct
Memory and no ContextRef, SnapshotRef, GrantRef, or other live reference. This
is required because direct Share rejects reference-bearing or empty Contexts.

| World | `S_W` | Direct Memories |
|---|---|---:|
| W1 | `task-1/participant/transform-scratch/source/building-access` | 13 |
| W2 | `task-2/participant/transform-scratch/source` | 6 |
| W3 | `task-3/local/transform-scratch/source` | 3 |
| W4 | `audit/ticker/transform-scratch/result` | 7 |
| W5 | `audit/a-is-apple/transform-scratch/result` | 15 |
| W6 | `practice/audit-workspace/transform-scratch/source` | 12 |

Freeze each `S_W` Context UID/digest and one directly owned Memory UID/content
digest. Log M3 uses that exact owner tuple; Share M2–M5 use the same nonempty
Memory-only Source and never deliver.

Fresh names use `A_W/r<round>-<operation>`. Existing-Memory methods must freeze
a direct UID and content digest from the prior world ledger before execution;
do not guess a UID. “Missing” selectors use an explicit reserved value first
proven absent by host-level read-only inspection of the live catalog.

## Interleaving and ledger rule

Run one whole world at a time in fixed order W1 → W2 → W3 → W4 → W5 → W6.
Within that world, run rounds 1→5 and execute one attempt for every operation
before the next round. Restore and verify the world-entry Profile/current and
release its global lease before starting the next world. Current/Profile/
command-stack operations remain serial. Each
attempt records the README-required fields plus global-lease identity, registry
generation before/after, active Profile/current before/after, config digest,
command-stack owner, outbound-contact flag, and recovery verification.

A protected or cancelled attempt is evidence, but it does not substitute for a
successful form when the world has authority for that form, except where this
plan deliberately excludes the irreversible success route (all Share cells).

## Risk and explicit-target summary

No Phase-3 operation accepts a saved semantic-session UID. “Session” risk in
this phase therefore means active Profile/current, Profile action/operation
ledger, shell session, or active command-stack state.

| Operation | Profile/current/session-stack/config-provider risk | Explicit target contract |
|---|---|---|
| Status | reads global current | none |
| Branch | writes namespace, command stack, and current | existing Source via `--from`; fresh target positional |
| Checkout | writes current; `-b` also namespace/stack | Switch target explicit; branch Source is current |
| Config | machine-global write surface, but this plan admits no-write routes only | explicit key only; no Context and no unset |
| Eval | provider contact and profile-independent ledger write | explicit ledger/run/case, no Context |
| Help | approved synthetic provider contact; shell-selection session | request explicit, no Context |
| Import | active-Profile Context/Memory write; Profile Import is forbidden | explicit resource/source Profile/target |
| Init | namespace, stack, and current write | fresh name only |
| Init-study | creates two Profiles, action ledgers, active switch | baseline/name explicit |
| Lock | Profile/current protection write | explicit Context/Memory; Profile form active-only |
| Log | reads Context history or active-Profile ledgers | Context/Memory explicit; operations/actions active-only |
| Profile | registry/active selection risk; this plan uses reads, unchanged-use, and exact restoration only | most subcommands explicit; bare selector active/TUI |
| Provider | pinned Study policy read/rejection; approved synthetic Probe contact | operation explicit, no Context |
| Pwd | reads global current | none |
| Redo | writes from active-Profile command stack | none |
| Rename | namespace, pointers, stack, and possibly current write | OLD/NEW explicit; OLD may be relative |
| Share | immediate delivery risk exists, but all counted routes fail/cancel before delivery | Source and grant endpoint explicit |
| Shell-init | parent-shell risk only if output is evaluated | shell explicit, no Context |
| Switch | writes global current | Context explicit or TUI |
| Undo | writes from active-Profile command stack | none |
| Unlock | Profile/current protection write | explicit Context/Memory; Profile form active-only |

## Operation matrices

### 1. Status

**Contract/risk.** Read-only, but it can inspect only current; `-d` and `-r` are
exclusive. It therefore carries global-current risk and has no explicit target.

**W1–W6 × M1–M5.**

| Method | Route and expected boundary |
|---|---|
| M1 | Counted Checkout M1 selects `R_W`; before any Init/Undo work, run `status -s` on that stable current. |
| M2 | Complete Branch M2 → Undo M2 → Redo M2 first; then run `status -b` on the stable restored `A_W/r2-tree`. |
| M3 | Complete Redo M3(no-redo) → Switch M3 → Rename M3 → Undo M3 first; then run `status -r` on the stable restored pre-rename admin child. |
| M4 | Complete Checkout M4 → Undo M4 → Import M4 → Redo M4(stale) first; then run `status -d -r`, expecting scope-conflict rejection without changing that stable state. |
| M5 | Complete Branch M5 → Undo M5 → Redo M5, any approved Init-study/Profile restoration, and Switch M5 first; then run ordinary `status` on the stable captured entry current. |

No TUI belongs to Status itself. No user decision is needed. Root's global
lease and the counted Checkout/Switch attempts own current for the matrix.

### 2. Branch

**Contract/risk.** Creates fresh local Context(s), copies direct content/history
bindings, and switches current to the new root. `--from` explicitly targets the
existing local Source; the new name is not an existing-Context locator.

| Method | Route and expected boundary |
|---|---|
| M1 | `branch A_W/r1-branch --from R_W --direct`; successful exact root copy. |
| M2 | `branch A_W/r2-tree --from R_W --recursive`; successful lexical subtree copy. |
| M3 | Branch the M1 output into `A_W/r3-from-prior`; prior-output chaining. |
| M4 | Reuse the actually retained `A_W/r2-renamed` target from Rename M2; expect collision, no switch. |
| M5 | Bare `branch` in a verified 180×52 color PTY; browse Source/name and create fresh `A_W/r5-branch`; this counted success is producer F for adjacent Undo M5/Redo M5. |

All targets are fresh descendants of `A_W`; `R_W` is read-only. Successful
branches remain as ledger evidence, and an owned counted Undo/Redo pair supplies
recovery where scheduled. No external or user content decision is needed.

### 3. Checkout

**Contract/risk.** Without `-b` it delegates to Switch. With `-b` it delegates
to Branch, and the branch Source is current because Checkout exposes no
`--from`. It changes current.

| Method | Route and expected boundary |
|---|---|
| M1 | `checkout R_W`; explicit canonical Switch route. |
| M2 | `checkout .` after M1; relative idempotent current route. |
| M3 | `checkout -b A_W/r3-checkout --direct`; branch the frozen current root. |
| M4 | `checkout -b A_W/r4-invalidator --direct`; owned Context-creation producer used to test Undo M4 and stale Redo M4. |
| M5 | Bare `checkout` in 180×52 color PTY; select a known admin Context and verify receipt/current. |

M3 is the same successful explicit branch route in all six worlds; no world
substitutes the earlier ambiguous `-d`-without-`-b` variant. M4 remains the
owned producer. No user decision is needed.

### 4. Config

**Contract/risk.** Bare/config-show are read-only. A valid `config set` rewrites
the machine-global config file and has neither unset nor command-level CAS, so
this matrix never supplies a valid key/value write. No Context target exists.
Root freezes the exact config bytes before M1 and checks the same bytes after
every attempt.

| Method | Route and expected boundary |
|---|---|
| M1 | Bare `config`; capture ordered stored keys and exact bytes/digest. |
| M2 | `config show`; second explicit read, same digest. |
| M3 | `config set provider` with VALUE omitted; parser/usage failure before the write handler. |
| M4 | `config set --help`; eager parser help exits before the handler. Frozen Typer parser introspection verified exit 0 and `handler_called=false`. |
| M5 | `config admin-preflight-invalid`; unknown-subcommand parser failure. |

M3/M5 are parser failures and M4 is an eager parser help exit; frozen-source
inspection confirms none enters `config_set`. Any config byte/digest change is a phase
stop, not a restore opportunity. No Config write, TUI, or user decision is
allowed.

### 5. Eval

**Contract/risk.** Eval is Profile-independent and has no Context target.
`semantic status/check` read an explicit `--ledger-dir` without provider
contact. `semantic run` contacts a provider and writes only that ledger.

| Method | Route and expected boundary |
|---|---|
| M1 | `eval semantic status --ledger-dir <W-empty-ledger>`; successful empty scoreboard. |
| M2 | Under the existing long-audit approval, run one fixed `ambiguity` case (`single-none-main-entrance-hours`), `--runs 1`, explicitly with `--provider codex_chatgpt --model gpt-5.6-sol --reasoning none`, into that W-specific ledger; record `outbound=true`. |
| M3 | As the next Eval attempt, status the exact M2 ledger as a read-only consumer; it need not print a run ID and records `outbound=false`. |
| M4 | As the next Eval attempt, `eval semantic check ${EVAL_RUN_ID_FROM_M2_LEDGER} --ledger-dir ...`; bind the exact ID from an isolated host-read ledger pre/post set difference before M3, then validate it with `outbound=false`. |
| M5 | Check a reserved absent run ID; stale failure. |

M2 transmits only the already-approved frozen synthetic fixture, never a world
Context. The existing long-audit approval covers this same pinned-provider,
non-sensitive scope, so it needs no additional decision. The CLI completion
prints only the ledger path, not a run ID: host-read the isolated ledger
immediately before and after M2, require exactly one new validated record
matching `started_at`, provider, model, reasoning, and case, and bind that full
ID. Preserve the exact M2 → M3 → M4 dependency with no other Eval ledger
command between them. Freeze the Study policy digest and verify it proves the
exact provider/model/reasoning route above; a machine transient default is not
an acceptable substitute. Eval has no TUI.

### 6. Help

**Contract/risk.** Bare non-TTY Help is local. A natural-language request sends
the request plus the frozen Help catalog to the Help provider. Study copy-match
preflight can reject copied Help wording before connection. No Context target
exists.

| Method | Route and expected boundary |
|---|---|
| M1 | Bare non-TTY `help`; complete deterministic inventory. |
| M2 | Under the existing long-audit approval, send the fixed non-sensitive request “which command inspects current orientation?” to the same pinned Help provider; record `outbound=true`. |
| M3 | Deliberate ≥50% authored Study Help copy; expect pre-provider protection. |
| M4 | `help --emit-selection` outside a TTY; expect terminal-required failure. |
| M5 | Bare Help in 180×52 color PTY; choose the A–Z inventory view, navigate to the exact `switch` operation row, Enter once to expand Forms, verify `Forms` and `← back`, Left once to collapse, then Escape once to close. |

M2 is inside the existing long-audit approval and needs no additional decision.
Do not send task-3 personal Memory text; use only the exact synthetic wording
recorded in the ledger. All other Help attempts record `outbound=false`. The
M5 inventory has no search input or SYNTAX layer. Escape/Q closes immediately,
so Escape is never a back action; H exits the selector to static help and is
forbidden in this route.

### 7. Import

**Contract/risk.** Context/Memory Import copies by value into the active
Profile while preserving imported identity and excluding operational history.
Profile Import would create a registered Profile and is forbidden in this live
plan. The frozen application also rejects an Import whose Source Profile is the
active Profile, so every counted success uses the separate read-only
mapped `study-baseline` or `teststudy0803` Source above.

| Method | Route and expected boundary |
|---|---|
| M1 | Import the method-mapped Context direct as fresh `A_W/import-direct`; its complete UID is globally collision-free. |
| M2 | Import the separate method-mapped closed subtree recursively as fresh `A_W/import-tree`; verify every frozen member and UID. |
| M3 | Import one host-frozen exact direct Memory from the mapped M3 Context into bare `A_W`; the receipt exposes only `uid[:8]`, so host-read the target and match the prebound full UID/content digest before Lock M3. |
| M4 | Import the distinct mapped Context direct as fresh `A_W/r4-import-owned`; this producer invalidates Redo M4 after Checkout M4 was undone. |
| M5 | Bare Import in 180×52 color PTY; select the mapped existing Source and fresh preview target, then cancel before Apply. |

Source Profile UID/Store digest, Source Context UID/digest, exact M3 Memory
UID/content digest, and fresh target absence are frozen by host-level reads.
Post-state verification proves each Source Store digest is unchanged. All
writes land under `A_W`. No same-active-Profile Source, `import profile` route,
Profile creation, external network transfer, or unledgered cleanup is allowed.

### 8. Init

**Contract/risk.** Creates fresh ordinary Contexts and switches current. The
name is a new identifier; `--parents` creates missing lexical prefixes but does
not embed children. No existing target is accepted.

| Method | Route and expected boundary |
|---|---|
| M1 | `init A_W`; fresh exact Context/current switch, immediately followed by owned Undo M1 and Redo M1. |
| M2 | `init A_W/tree/leaf --parents`; hierarchical creation/reuse. |
| M3 | Reuse `A_W`; expect existing-name rejection and unchanged current. |
| M4 | Use a UID-shaped or otherwise invalid portable name; pre-write failure. |
| M5 | Bare Init in 180×52 color PTY with an exact world mapping: W1 cancel, W2 create `A_W/r5-init`, W3 cancel, W4 create `A_W/r5-init`, W5 create `A_W/r5-init`, W6 cancel. |

All successful names are under `A_W` and remain as phase evidence. No user
decision or extra cleanup command is needed.

### 9. Init-study

**Contract/risk.** Every success creates a durable participant/authority Profile
pair, records Study actions, pins Provider policy, and selects the new
participant. Removal would itself leave registry tombstones and would add
unrequested Profile attempts. There is no success route that is both live and
residue-free.

| Method | Route and expected boundary |
|---|---|
| M1 | Use the existing Study name `study-long-audit-20260823` with `--from-profile study-baseline`; duplicate-name/no-create failure. |
| M2 | Use a deliberately invalid Profile name containing `/`; validation failure before creation. |
| M3 | Use fresh-looking name with a proven-missing `--from-profile` baseline; no-create failure. |
| M4 | Bare 180×52 TUI exposes only one 5-line Study-name field and the footer `Enter create · Esc cancel`. Type the exact proposed name, verify that same field/footer, then press Escape directly. Never press Enter; no baseline selector or final-review layer exists. |
| M5 | **PENDING USER DECISION:** `init-study study-long-admin-W-r5 --from-profile study-baseline`; one real successful pair for W, followed immediately by Profile M5 selecting the original Study. |

M1–M4 are executable no-create evidence. M5 must not run until the user accepts
that six approved cells create six Study pairs (12 durable Profile entries),
action-ledger events, and registry-generation changes that will remain after
the audit. `profile remove-study` is not a cleanup option: it is destructive,
adds out-of-matrix Profile attempts, and leaves tombstone state. If the user
declines, all six M5 cells remain explicitly pending and the phase cannot claim
full 630-attempt completion.

### 10. Lock

**Contract/risk.** Can target current/explicit Context, lexical subtree, exact
direct Memory, or active Profile. It changes durable protection policy. Profile
and current-only forms are global within the active Profile.

| Method | Route and expected boundary |
|---|---|
| M1 | `lock --context A_W --direct`; pair immediately with Unlock M1. |
| M2 | `lock --context A_W --recursive`; pair with recursive Unlock. |
| M3 | After Import M3, lock its exact direct imported Memory in bare `A_W`; pair with Memory Unlock using `--context A_W`. |
| M4 | `lock --profile`; Rename M4 supplies the already-counted protected-write probe, then Unlock M4. |
| M5 | Lock a proven-missing Context/Memory selector; expect fail-closed no policy change. |

M1–M3 have no command between Lock and their matching Unlock. M4 is the sole
exception: Lock M4 → counted protected Rename M4 → Unlock M4 is one
transactional bracket. Never leave a lock for another world. No TUI or user
decision is needed. Host inspection verifies no residual lock.

### 11. Log

**Contract/risk.** Checkpoint/history and Memory-lineage routes accept
`--context`; `--operations` and `--actions` are active-Profile scoped and
exclusive. A natural-language query may contact a provider, so it is excluded
from the default admin matrix.

| Method | Route and expected boundary |
|---|---|
| M1 | `log --context R_W`; explicit retained checkpoints. |
| M2 | `log --context R_W --manual`; manual-only filter. |
| M3 | `log --memory ${WORLD_LOG_MEMORY_UID} --context S_W`; the full UID, content digest, and exact direct owner are host-frozen and revalidated immediately before use. |
| M4 | Use a proven-stale Memory selector; safe failure/empty lineage boundary. |
| M5 | W1–W3: `log --actions`; W4–W6: `log --operations --limit 20`; late Profile-scoped evidence. |

Log is terminal-independent and needs no TUI or user decision.

### 12. Profile

**Contract/risk.** Bare Profile is TUI in a terminal and List otherwise.
Create/remove/rename/grant/import routes mutate registry or stores and are
outside this live phase. `use` is permitted only when the named Profile is
already active, except the counted restoration after an approved Init-study.

| Method | Route and expected boundary |
|---|---|
| M1 | `profile list`; frozen registry inventory. |
| M2 | `profile current`; exact active/current/store orientation. |
| M3 | `profile use study-long-audit-20260823` while it is already active; successful unchanged-use with no registry write. |
| M4 | `profile use admin-W-missing` after host proof of absence; fail with active Profile unchanged. |
| M5 | Bare Profile in 180×52 color PTY. If Init-study M5 was approved, select `study-long-audit-20260823` to restore it; otherwise inspect and cancel without switching. |

No Profile is created, renamed, imported, granted, removed, or selected merely
for Provider testing. If M5 restores an approved Init-study success, verify the
original active UID and current before releasing the global lease; the accepted
new pair remains registered.

### 13. Provider

**Contract/risk.** Bare/status are observation-only. The active Study policy is
pinned, so `use/reset` editing must fail. `probe` contacts the pinned provider
with a fixed synthetic schema but sends no Context content. No other Profile may
be selected to manufacture an editable route.

| Method | Route and expected boundary |
|---|---|
| M1 | Bare `provider`; pinned Study route overview, no contact. |
| M2 | `provider status`; default pinned route and digest. |
| M3 | `provider status --operation query`; explicit effective-operation read. |
| M4 | `provider use codex_chatgpt --operation query`; expect fixed-Study rejection and unchanged registry/config/provider digests. |
| M5 | Under the existing long-audit approval, `provider probe --operation query`; strict synthetic READY/echo contract with the same pinned provider, no Context content, and `outbound=true`. |

Never send task/world Memories in Probe. `provider reset` is not used because it
is an edit route, even if the pinned policy would likely reject it. M1–M4 record
`outbound=false`; M5 needs no additional decision. No TUI.

### 14. Pwd

**Contract/risk.** Read-only and content-free, but current-only; no operand.

| Method | Route and expected boundary |
|---|---|
| M1 | Counted Checkout M1 selects `R_W`; after Status M1 and before any Init/Undo work, print that stable `R_W`. |
| M2 | Complete Branch M2 → Undo M2 → Redo M2, then Status M2; print the stable restored `A_W/r2-tree`. |
| M3 | Complete Redo M3(no-redo) → Switch M3 → Rename M3 → Undo M3, then Status M3; print the stable restored pre-rename admin child. |
| M4 | Complete Checkout M4 → Undo M4 → Import M4 → Redo M4(stale), then Status M4; print the resulting stable current. |
| M5 | Complete Branch M5 → Undo M5 → Redo M5, Profile restoration if needed, Switch M5, then Status M5; print the captured phase-entry current. |

No TUI belongs to Pwd and no user decision is needed.

### 15. Redo

**Contract/risk.** Redo uses only the active Study Profile's most recently
undone Context-command unit and has no target. Any intervening producer
invalidates redo, so exact adjacency and host-read stack ownership are required.

| Method | Route and expected boundary |
|---|---|
| M1 | Immediately redo Undo M1 of Init M1; verify `A_W` is restored. |
| M2 | Immediately redo Undo M2 of Branch M2; verify the branch subtree is restored. |
| M3 | At the start of round 3, before Rename M3, call Redo with no outstanding owned Undo; expect no-redo failure. |
| M4 | Checkout M4 creates D; Undo M4 removes D; Import M4 creates E and invalidates D's redo; then Redo M4 must fail stale/no-redo while E remains. |
| M5 | Immediately redo Undo M5 of the successful 180×52 Branch M5 creation; verify the branch returns. |

Only host-level read-only stack inspection may occur inside an adjacency
window. All producers are already-counted admin attempts under `A_W`; no Add,
Edit, Delete, extra Profile, or cleanup command is introduced.

### 16. Rename

**Contract/risk.** Renames an ordinary Context plus all lexical descendants,
updates current/references/checkpoint pointers, prompts unless `--force`, and
does not change query-only references. OLD supports existing relative locators;
NEW must be canonical and fresh.

| Method | Route and expected boundary |
|---|---|
| M1 | Rename the prior counted `A_W/r1-branch` output to fresh `A_W/r1-renamed --force`; exact successful child rename. |
| M2 | Rename the prior counted recursive Branch/Init parent to fresh `A_W/r2-renamed --force`; verify every lexical descendant moved. |
| M3 | After counted Switch M3 selects a known `A_W` child, rename `.` to fresh `A_W/r3-renamed --force`; this is producer C, immediately followed by Undo M3. |
| M4 | While counted Lock M4 holds the active Profile, try to rename a known `A_W` child; expect protected failure, then counted Unlock M4. |
| M5 | Use a host-proven stale OLD or a NEW that collides with an existing `A_W` child; expect fail-closed with both namespaces unchanged. |

M1/M2 successes and any Redo-restored Context remain under `A_W` as evidence;
there is no extra Rename cleanup. M3 supplies the owned producer for Undo M3,
and M4 consumes the already-counted Profile lock. No full-screen TUI or user
decision is needed; `--force` is allowed only for the exact admin child named
in the ledger, never for `R_W` or an `A_W` root with unrelated evidence.

### 17. Share

**Contract/risk.** Explicit SOURCE plus `--to ENDPOINT` delivers immediately
across a grant-backed Profile boundary. Incomplete forms enter interactive
selection/review in a TTY. Because delivery is irreversible, the success route
is explicitly outside this phase; the matrix exercises only pre-delivery
protection and cancellation.

| Method | Route and expected boundary |
|---|---|
| M1 | Non-TTY bare Share; expect missing SOURCE and endpoint failure. |
| M2 | Explicit nonempty Memory-only `S_W` with a proven-missing endpoint; fail before delivery. |
| M3 | Explicit `S_W` with both direct and recursive flags; scope-conflict rejection. |
| M4 | Source-only TUI at 180×52 using `S_W`; inspect endpoint/preview and close, recording no delivery. |
| M5 | Endpoint-only TUI at 180×52; select exact `S_W`, inspect preview, and cancel before Apply in all six worlds, including W3. |

All 30 counted Share cells are fail/cancel no-delivery routes. The shared Study
exposes a SHARE endpoint only for `task-3/government/healthcare-agent`, but this
phase does not Apply to it. An exact task-3 delivery, recipient verification,
and consent decision belong to a separate future test and do not count toward
this 630-cell matrix. No content crosses a Profile boundary here.

### 18. Shell-init

**Contract/risk.** Prints zsh integration; it does not modify the parent shell.
Only `zsh` is supported. Evaluating the output can define a function and push
Study history in the **current shell**, so evaluation is confined to a
disposable zsh subprocess. No Context/Profile target exists.

| Method | Route and expected boundary |
|---|---|
| M1 | `shell-init`; capture default zsh text. |
| M2 | `shell-init zsh`; explicit supported route and text-equivalence check. |
| M3 | `shell-init bash`; unsupported-shell failure. |
| M4 | Pipe M2 output to `zsh -n` as a prior-output syntax consumer. |
| M5 | Source M2 output inside a disposable interactive zsh subprocess, verify the `mem` function exists, then exit without touching the user's shell/history. |

The distinct consumers, not cosmetic shell arguments, make M1/M2/M4/M5
meaningful. No 180×52 TUI or user decision is needed.

### 19. Switch

**Contract/risk.** Switch changes global current. Explicit local and readable
grant names are resolved against one starting snapshot; QUERY-only rows are
not selectable. Bare Switch is a TUI. M5 does not require local/granted/query
category annotations to be simultaneously visible; authorization is enforced
by the host-bound target identity and the prohibition on selecting nonlocal
routes.

| Method | Route and expected boundary |
|---|---|
| M1 | `switch R_W`; explicit canonical local Context. |
| M2 | `switch ./<known-child>` from R_W; relative locator. |
| M3 | In all six worlds switch to the prior owned `A_W/r3-from-prior` Branch output, so the following relative Rename M3 producer remains inside the admin namespace. |
| M4 | W3: exact QUERY-only route; other worlds: proven-missing name. Expect rejection and unchanged current. |
| M5 | Bare Switch in 180×52 color PTY; host-bind the exact phase-entry ordinary local Context name/UID/digest, prove it materialized/selectable and different from current, navigate until that exact name is visibly focused, then Enter once and verify receipt/current restoration. Granted and query routes are forbidden targets. |

At phase end the live active Profile and current match the captured entry state.
No user decision is needed.

### 20. Undo

**Contract/risk.** Undo restores one global active-Profile checkpoint-producing
command unit and has no target. A stale granted Update receipt may be consulted
before falling back to the local stack, so root must prove the exact live stack
owner and keep every producer/Undo/Redo sequence adjacent under the global
lease.

| Method | Route and expected boundary |
|---|---|
| M1 | Immediately undo counted Init M1; verify `A_W` is absent/restored according to its receipt, then immediately Redo M1. |
| M2 | Immediately `undo --keep` after counted Branch M2; verify the branch is removed while compatible history is retained, then immediately Redo M2. |
| M3 | After Redo M3 first proves no outstanding owned Undo, run counted Rename M3 and immediately undo it; leave producer C undone. |
| M4 | Immediately undo counted Checkout M4 producer D; counted Import M4 then creates E and invalidates D before Redo M4's stale/no-redo probe. |
| M5 | Immediately undo the successful counted Branch M5 TUI producer F, then immediately Redo M5. |

Every producer is another already-counted admin operation under `A_W`; there
are no setup Add/Edit/Delete/Profile commands. Record producer attempt UID,
Context UID, before/after digest, and stack head. Only host-level read-only
inspection may occur inside adjacency. No user decision is needed.

### 21. Unlock

**Contract/risk.** Mirrors Lock and edits the same durable protection state.
Unlocking the active Profile leaves narrower locks intact. Explicit Context and
Memory targets are supported; current/Profile forms remain global.

| Method | Route and expected boundary |
|---|---|
| M1 | Immediately unlock Lock M1's exact Context; verify changed then writable. |
| M2 | Unlock Lock M2's recursive subtree atomically. |
| M3 | Unlock Lock M3's exact Memory occurrence. |
| M4 | Unlock the Profile locked by Lock M4; verify narrower locks, if any, remain. |
| M5 | Unlock a proven-missing or already-unlocked target; expect safe failure or idempotent receipt. |

Lock/Unlock M1–M3 are strict adjacent pairs under the global lease. M4 is the
explicit transactional-bracket exception: Lock Profile → protected Rename M4
probe → Unlock Profile. M5 changes no policy. Host-level verification must
prove no residual lock. No TUI or user decision.

## 180×52 color TUI schedule

Use `TERM=xterm-256color`, `COLORTERM=truecolor`, remove `NO_COLOR`, set and
verify `stty rows 52 cols 180`. Capture materially distinct states, not repeated
idle screens.

Required paths:

- Branch M5: Source → reach/name → successful creation receipt; this is the
  counted producer F for adjacent Undo M5/Redo M5.
- Checkout M5: picker → selected Context → receipt/current verification.
- Help M5: A–Z view → exact `switch` row → Enter opens Forms → verify `Forms`
  and `← back` → Left collapses → verify `Q/Esc close` → one Escape closes.
  Do not type a query, open a SYNTAX layer, use Escape as back, or press H.
- Import M5: resource kind → Source → target → preview/cancel.
- Init M5: exact name field → validation → W1/W3/W6 cancel or W2/W4/W5
  `A_W/r5-init` creation receipt, matching the fixed world map.
- Init-study M4: the sole 5-line name field → exact proposed name and
  `Enter create · Esc cancel` footer visible → Escape directly. Enter/Create
  is forbidden; there is no selector or review layer. Approved M5 is the exact
  noninteractive create route and is not exercised before its gate.
- Profile M5 has two separately executable contracts after the Init-study M5
  decision is bound. Approved: verify the newly created participant is active
  → find the exact original Study name/UID/digest → approve only that row →
  verify restoration. Declined: verify the original Study is already active →
  focus only that exact row → Escape/cancel without switching → verify the UID
  is unchanged. Profile M5 never launches while the decision remains pending.
- Share M4/M5: Source/endpoint choice → preview → cancel before Apply in all
  worlds; no receiver verification exists because delivery is out of phase.
- Switch M5: host-bind the exact phase-entry ordinary local Context identity →
  prove materialized/selectable and different from pre-attempt current → focus
  that exact visible name → Enter once → receipt/current restoration. Never
  require `LOCAL`, `GRANT`, and `QUERY ONLY` to be simultaneously visible, and
  never select granted or query routes.

Every TUI cell uses an executable adaptive contract rather than a fixed count
of arrow keys, because the live registry and Context catalogs grow during the
campaign. Before each key the runner captures the visible state and verifies
the required frame, focus, semantic target text, and absence of an unexpected
mutation receipt. The contract enumerates the allowed key grammar, ordered
semantic actions, exact search text, a finite transition limit, Escape/back
stop behavior, and the receipt stop predicate; the concrete keys actually sent
are appended to the ledger after the run. Create/select flows may send their
approval key only after the exact target and frozen digest are visible. Share
cancel flows forbid Apply/approval keys; Init-study M4 additionally forbids
Enter because it creates immediately from the single field. `TBD`
key placeholders are not executable and fail preflight verification.

## Serial execution order

Within each world, keep the 21-operation round interleave while satisfying the
following counted adjacency schedule. There are no uncounted setup/cleanup
`mem` commands:

1. Freeze live registry/Profile/current/config/provider/stack/lock state with
   host-level reads and acquire root's global lease. No Status or Pwd call is
   allowed inside an Undo→Redo adjacency window.
2. Round 1 exact state schedule: Checkout M1 → Status M1 → Pwd M1; later, Init
   M1 → Undo M1 → Redo M1 with no intervening `mem` command.
3. Round 2 exact state schedule: Branch M2 → Undo M2 → Redo M2 with no
   intervening `mem` command → Status M2 → Pwd M2.
4. Round 3 exact state schedule: Redo M3(no-redo) → Switch M3 → Rename M3
   producer C → Undo M3 → Status M3 → Pwd M3. C deliberately remains undone,
   so no Redo adjacency remains open.
5. Round 4 has two exact transactions. First: Lock M4 Profile → protected
   Rename M4 → Unlock M4, with no other command inside the bracket. Second:
   Checkout M4 producer D → Undo M4 → Import M4 producer E → Redo M4
   stale/no-redo → Status M4 → Pwd M4. Import intentionally closes the redo
   window before either read.
6. Round 5 autonomous schedule ends after Shell-init M5, local cell 100 for the
   world. Branch M5 TUI producer F → Undo M5 → Redo M5 still has no intervening
   `mem` command. Init-study M5 is local cell 101 and the direct decision gate;
   Profile, Switch, Status, and Pwd M5 (cells 102–105) remain pending on that
   decision. If approved, execute Init-study → Profile restore → Switch restore
   → Status → Pwd. If declined, do not count an Init-study M5 success; design a
   separate meaningful no-create fifth route before claiming coverage, then
   execute the four dependent cancel/restore/stable-read cells.
7. Run the remaining Init/Branch/Import/Rename methods only on their named
   `A_W` children. Preserve Eval M2 → M3 → M4 as an exact W-specific ledger
   chain; no other Eval ledger call enters that chain.
8. Config is reads/rejections only, and every attempt must preserve identical
   bytes. Provider uses pinned-policy reads, rejection, and the already-approved
   non-sensitive synthetic Probe. Help M2 and Eval M2 use that same approval.
9. All Share attempts are validation/conflict/cancel before delivery. The six
   Init-study M5 cells are the only direct decision gates. The 24 Profile,
   Switch, Status, and Pwd M5 cells are dependency-pending rather than
   autonomous because their exact branch depends on that decision.
10. Release the lease only after host-level read-only verification proves the
    original active Profile/current/config/provider and no residual locks.

Never interleave another world or worker inside the lease or any adjacency
window. Complete all five rounds and entry-state restoration for W1 before W2,
then continue through W6. The round interleave applies only inside one world.

## Pause and user-decision gates

The manifest classifies 600 cells as requiring no additional decision, but
that aggregate is **not** one executable pre-gate prefix. World serialization
and restoration make the current safe prefix exactly W1 cells 1–100. At W1
cell 101, execution must request one decision covering all six worlds. Without
that decision, W1 cells 102–105 cannot restore/release its lease and W2 cannot
start. The six Init-study M5 cells are direct gates and the following 24
Profile/Switch/Status/Pwd M5 cells are decision-dependent.

Pause once, before the first relevant attempt, for this choice:

1. **Init-study durable residue:** authorize or decline six M5 successes in the
   live registry. Approval creates six participant/authority pairs (12 durable
   Profile entries), Study action records, pinned policies, and registry
   generation changes. They are not removed afterward; decline leaves those
   six success cells pending until a meaningful no-create M5 replacement is
   designed and prevents a 630-attempt completion claim. `profile
   create`, Profile Import, and Profile removal are never authorized here.

Profile M5 has two predeclared branches. After approval it selects the exact
original `study-long-audit-20260823` row and verifies restoration. After a
decline/no-create alternative, the original Study is already active, so it
inspects that exact row and cancels without switching. The gate result must be
bound before either branch runs; an early Profile M5 cancel is not reusable as
the later restoration attempt.
The existing long-audit approval already covers the exact pinned-provider,
non-sensitive synthetic Help/Eval/Provider calls; record their outbound flag
but do not pause again. Share performs no delivery in this phase. No other
operation requires product-meaning judgment because all durable
Context changes remain within named `A_W` admin namespaces and are retained as
audit evidence. Config/Provider/Profile edits beyond the exact bounded routes
above, cleanup deletes, Profile removal, and external delivery without the
separate future-test approval are outside the plan.

## Completion checks

Before reporting phase complete:

- exactly 21 operation keys and exactly 5 attempts per operation per world;
- exactly 105 attempts per world and 630 total;
- decision classification contains exactly 600 no-additional-decision cells,
  six direct Init-study durable-residue gates, and 24 downstream dependent
  cells; the currently executable pre-decision prefix is only W1 cells 1–100;
- every command uses the fixed frozen `PYTHONPATH` launcher and none overrides
  or repurposes `HOME`, `home`, or `CODEX_HOME`;
- all live current/Profile/config/provider/stack transactions are covered by
  one root-owned serial lease;
- every Context/Memory write is under the matching `A_W`, except no-create
  validation routes; `R_W` and non-admin world state are unchanged;
- every Import reads its mapped separate `study-baseline` or `teststudy0803`
  Source; the exact Profile UID, canonical Store digest, Context/subtree UID
  set, and direct Memory tuple are frozen and the Source Store is unchanged;
- five owned Undo and five Redo attempts per world, with producer UID evidence;
- five Lock and five Unlock attempts per world, with no residual Context,
  Memory, or Profile lock;
- exactly 30 Init-study attempts: 24 verified no-create routes plus six approved
  M5 successes; if approval is declined, the six cells are pending and the
  phase is not reported complete;
- active Profile and current are restored after every world; config and pinned
  Provider bytes/digests are identical before/after; registry differences are
  limited to the exact approved Init-study pairs and recorded generations;
- no Profile was created/imported/renamed/removed except the specifically
  approved Init-study pairs, and admin Context evidence was not cleaned up with
  extra `mem` calls;
- exactly Help M2, Eval M2, and Provider M5 in each world record
  `outbound=true` (18 cells); every other cell records `outbound=false`;
- all 30 Share cells record no delivery and no receiver mutation; any future
  exact task-3 transfer is outside phase coverage;
- every required TUI path has ordered 180×52 color evidence;
- no code, test, or commit change.
