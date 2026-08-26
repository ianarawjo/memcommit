# Task-1 admin execution issues

## ADM-PLAN-INIT-UNDO-001 · Init is not the adjacent Undo producer

- Severity: P0 execution-plan/runtime mismatch
- Reproduced: once in the approved W1 serialized run (seq7–9); no retry was made because the command stack is global.
- Expected: seq7 `init task-1/participant/admin-scratch` would become the immediately adjacent global command-stack producer; seq8 `undo` would remove that exact Context and seq9 `redo` would restore it.
- Actual: seq7 created Context `c12593b7-7124-45ea-ba47-25a9a482ff23`, but seq8 selected the older Sever source unit `checkpoint:3b8f7779-87f6-42d1-a0c0-77b1738f3ef4` in `practice/audit-workspace/transform-scratch/sever-r2`. Undo receipt `5094302f-9227-4d08-838a-ba82f922ff27` / checkpoint `70ca655c-ea9b-4bc6-bb59-caee03b7bf85` removed four Memories. Seq9 redo receipt `663a74f9-4783-4df7-a221-d352488e9711` / checkpoint `95d15153-fcb7-492d-b321-e03914e8af55` restored them.
- Recovery verification: the restored Context UID is `8c039b43-7259-48c5-8188-bc9714604183`; its canonical digest `0003be1003d92bccd90d3ceb60ce9a51214199622bde1581981b33c45254f756` exactly matches the original Sever checkpoint snapshot and contains four Memories. The seq7 Context still exists. Seq10, already dispatched before the semantic mismatch was recognized, created branch `796ba3d5-e8b9-47f3-802e-cd7f6a80187b`; execution then stopped.
- Workaround: do not use `init` as an Undo/Redo producer. Re-plan each Undo/Redo pair around a command proven by frozen source and an isolated runtime probe to publish a command-history unit, with the intended unit UID frozen before Undo.
- Product vs plan classification: the observed behavior is consistent with the frozen runtime's command-history contract; the defect is in the preflight plan assumption, not evidence of an `undo` product implementation failure.

