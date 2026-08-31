# Eval application boundary matrix

| Concern | Owner | Boundary |
| --- | --- | --- |
| Public discovery and maturity | `memcommit.operation_catalog` and Console Help inventory | Lists Eval as `PARTIAL` and describes a reserved, non-executable operation |
| Console route | `memcommit.adapters.console.commands.eval` | Keeps `mem eval` and `--help`; exposes no subcommands, provider setup, status, scoring, or ledger UI |
| Application operation | `memcommit.application.operations.eval` | Empty package marker reserved for a future contract; contains no campaign engine |
| Production prompt resources | Their consuming operation or shared semantic capability | Loaded directly from the owning package and never routed through Eval |
| Regression-only resources | `tests/fixtures` | Exercise contracts without becoming distributable runtime inputs |
| Historical local ledgers | User-owned `~/.mem/eval` data | Left untouched; the current application neither reads nor writes them |

The former `semantic_campaign`, `operation_gate_campaign`, `runner`, and
`scoring` modules and the hidden `mem dev eval` command are intentionally
absent. The boundary is complete only while no alternate executable Eval route
or generic evaluation resource package reappears.
