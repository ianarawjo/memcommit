# Eval application boundary matrix

| Concern | Owner | Boundary |
| --- | --- | --- |
| CLI grammar, ledger display, provider setup | `memcommit.adapters.console.commands.eval` | Presents Eval and passes typed campaign inputs; does not own corpus validation or scoring |
| Ambiguity and duplicate campaigns | `memcommit.application.operations.eval.semantic_campaign` | Validates calibration/holdout corpora and locks, executes replayable runs, scores results, and writes complete ledgers |
| Operation-gate campaign | `memcommit.application.operations.eval.operation_gate_campaign` | Validates baseline/extension/lock composition and executes the selected gate cases |
| Legacy developer runner | `memcommit.application.operations.eval.runner` and `.scoring` | Runs old Forget/Integrate corpora and deterministic UID-level scores |
| Authored packaged resources | `memcommit.application.capabilities.evaluation.resources` | Supplies fixture paths/resources without importing or executing a peer operation |
| Production semantic operations | Their own operation/capability packages | May consume prompt rules/examples through `fixture_resource`; never call an Eval campaign engine |

The physical split is an ownership correction. Campaign behavior and fixture
contents are unchanged; tests cover both the moved engines and every known
production fixture consumer.

