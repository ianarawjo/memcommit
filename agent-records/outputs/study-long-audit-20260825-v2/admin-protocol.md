# Six-world v2 admin-phase protocol

This protocol applies to the frozen code snapshot only. Every counted call uses
`run_world_mem.py WORLD ...`; placeholders must be replaced with live canonical
names or UIDs from that world's isolated lane.

## Safety invariants

- Assert the active Profile name, UID, and resolved Store before and after every
  call. The audit launcher performs both checks.
- Never successfully create or activate another Study/Profile. `init-study`
  uses safe validation failures or an explicit TUI cancel only.
- Treat only `branch` and `checkout -b` as Undo producers. Immediately before
  Undo, host-read the exact command-stack unit UID/member set and require
  `staged-update.granted_target == null`.
- Never run a complete valid Share source/receiver pair. All Share trials must
  stop before delivery, and sender/receiver digests must be unchanged.
- Keep config and Eval ledgers inside the lane. Synthetic provider work is
  limited to one Help lookup, one Eval case, and one provider probe per world.
- Preserve one cumulative Store and five interleaved rounds. Record every
  non-counted host read separately from the 105 counted `mem` calls.
- Use `a-is-apple` as the representative interactive admin lane. Its TUI trials
  use a real 180x52 color PTY and ordered snapshots/logs for every materially
  distinct state. Other worlds use the noninteractive substitutes below so the
  campaign does not create duplicate screenshot sets.

## Placeholders

- `C`: world-local absent scratch root:
  - task-1: `task-1/participant/admin-v2-scratch`
  - task-2: `task-2/participant/admin-v2-scratch`
  - task-3: `task-3/local/admin-v2-scratch`
  - ticker: `audit/ticker/admin-v2-scratch`
  - a-is-apple: `audit/a-is-apple/admin-v2-scratch`
  - practice-source: `practice/audit-workspace/admin-v2-scratch`
- `R` / `R_CHILD`: an existing local root and child.
- `O`: a separate existing local Context.
- `ENTRY`: phase-entry current Context.
- `E`: `/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/worlds/WORLD/admin-eval-ledger`.

## Five methods per operation

| Operation | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|
| status | `status --short` | `status --branch` | `status --recursive` | `status --direct --recursive` (safe exit 2) | `status` |
| branch | `branch C/b1 --from R --direct` | `branch C/b2-tree --from R --recursive` | `branch C/b3 --from <live-b1-name> --source-root-only` | `branch C --from R --direct` (collision) | a-is-apple: TUI bare branch to `C/b5-tui`; others: branch `C/b5` from missing Source |
| checkout | `checkout R` | after previous/next transaction, `checkout ..` | `checkout -b C/co3 --direct` | `checkout -b C/co4-tree --recursive` | a-is-apple: TUI bare checkout; others: missing target failure |
| config | `config` | `config set audit_v2_world WORLD` | `config show` | `config set provider codex_chatgpt` | `config set provider` (missing value) |
| eval | `eval semantic status --ledger-dir E` | one-case ambiguity run with provider/model policy and `--ledger-dir E` | `eval semantic check <FULL_RUN_ID_M2> --ledger-dir E` | `eval semantic task2-status --all --ledger-dir E` | accumulated semantic status with `--ledger-dir E` |
| help | non-TTY `help` | synthetic natural-language query lookup | a-is-apple: TUI expand one operation/form; others: `help query` | a-is-apple: TTY `help --emit-selection`, verify safe command line only; others: a different exact operation query | copied-text guard query expected to fail before provider |
| import | direct Context import into `C/import-direct` | recursive Context import into `C/import-tree` | exact Memory import into `C` | repeat M3 for collision/no mutation | a-is-apple: TUI immediate Esc; others: missing source Profile failure |
| init | `init C` | `init C/tree/leaf --parents` | `init C` collision | UID-shaped name failure | a-is-apple: TUI immediate Esc; others: missing-parent failure without `--parents` |
| init-study | invalid slash name | reserved `authoring` name | missing baseline Profile | `--prewarm-workers 0` validation failure | a-is-apple: TUI immediate Esc; others: another invalid/reserved name. Never run non-TTY bare init-study. |
| lock | lock frozen current | recursive lock `C/b2-tree` | lock exact Memory | lock `C/co4-tree` | `lock --profile` |
| log | `log --context C` | same with `--manual` | exact Memory log, limit 5 | `log --operations --limit 50` | `log --actions --limit 100` |
| profile | `profile current` | create inactive `admin-v2-WORLD-inactive` | `profile list` | use same active `sixworld-v2-template` | a-is-apple: TUI immediate Esc; others: use missing Profile |
| provider | bare provider | provider status | status for query | use codex_chatgpt for query, expected Study-lock failure | one provider probe for query |
| pwd | bare `pwd` five times; distinguish by cumulative current/producer state |
| redo | after Undo 1 | after Undo 2 | after Undo 3 | no-redo failure | after Undo 5 |
| rename | rename current b1 to `C/renamed-1` | rename b2 tree | rename co3 | locked co4 rename failure | after branch5, answer `n` to exact confirmation |
| share | non-TTY incomplete bare share | a-is-apple: TUI Esc at Source; others: missing Source failure | a-is-apple: valid receiver but Esc at Source; others: missing receiver with incomplete Source | direct+recursive conflict before delivery | valid Source to missing endpoint failure |
| shell-init | bare output | explicit zsh, byte-equal | zsh output consumed by `zsh -n` host check | source only in disposable `zsh -dfc`, never invoke function | unsupported bash failure |
| switch | round 1 last: `switch --previous` | round 2 first: `switch --next`, with no intervening mem | after checkout M3, switch to O | after checkout M4, switch to verified branched child | a-is-apple: TUI restore ENTRY; others: exact `switch ENTRY` |
| undo | after Branch 1 | after Branch 2 with `--keep` | after Checkout 3 and Switch O | locked Checkout 4 producer: protected failure | round 5 first, after Unlock 4: success on same Checkout 4 producer |
| unlock | current | recursive b2 tree | exact Memory | co4 tree | whole Profile |

Use the exact round transaction order:

1. `Branch1 -> stack UID check -> Undo1 -> redo-top same UID -> Redo1`.
2. The same with `Undo --keep`; end round 1 with `switch --previous` and start
   round 2 with `switch --next` before any other mem call.
3. `Checkout3(-b) -> Switch O -> top UID unchanged -> Undo3 -> Redo3`.
4. Early `Redo4` must fail with no redo. Later run
   `Checkout4 -> Switch child -> Lock co4 -> Rename protected failure -> Undo
   protected failure -> Unlock co4`, then no other mem call.
5. Start with `Undo5 -> Redo5`; Branch5 occurs afterward.

`init` and `rename` are not command-stack producers. Lock/Unlock M1-3 and M5
remain adjacent pairs. Record TUI PTY size, environment, exact keys, visible
state, and mutation status beside ordered snapshots.
