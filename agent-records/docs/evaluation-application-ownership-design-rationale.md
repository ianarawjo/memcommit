# Reserved Eval shell and fixture ownership

## Decision

`eval` remains a public `PARTIAL` operation name, but it has no executable
evaluation application yet. The console package keeps only a reservation
callback and
`memcommit.application.operations.eval` keeps only its
package marker. The former semantic campaign, operation-gate campaign, scoring,
provider-selection, ledger presentation, and hidden `mem dev eval` routes are
removed.

This is an intentional empty boundary, not a compatibility facade. `mem eval`
prints that the operation is reserved, `mem eval --help` exposes no campaign
subcommands, and the removed `mem eval semantic ...` grammar fails as unknown.
Future Eval work must define a new application contract instead of silently
reviving one of the retired research harnesses.

## Fixture ownership

The former shared `application.capabilities.evaluation` resource package mixed
runtime prompt inputs, test-only corpora, and Eval-only campaign data. Those
roles now have distinct owners:

| Resource role | Owner |
| --- | --- |
| Ambiguity, conflict, and duplicate prompt calibration | `application.capabilities.memory_issue_analysis/fixtures/` |
| Atomize prompt calibration | `application.operations.atomize/fixtures/` |
| Compare compact-summary rules | `application.operations.compare/fixtures/` |
| Rationale rules and examples | `application.operations.rationale/fixtures/` |
| Resolve exact rules and examples | `application.operations.resolve/fixtures/` |
| Shared Distill/Makemore prompt examples | `application.capabilities.semantic/fixtures/` |
| Prompt-unseen Distill/Makemore and Update regression inputs | `tests/fixtures/` |

Each production consumer now resolves its resource from its own package with
`importlib.resources`. There is no general `fixture_resource` accessor and no
production import through Eval.

Eval-only ambiguity holdout and operation-gate corpora, their locks, and the
old Forget/Integrate benchmark corpora were deleted with their engines. Their
only callers were removed Eval routes. Existing user data under `~/.mem/eval`
is deliberately not inspected, migrated, or deleted: removing code-owned
campaign support does not authorize destruction of retained local records.

## Why keep the shell

Keeping both the console and application operation directories preserves the
one-to-one public operation topology and leaves an explicit place for a later
Eval design. Marking the operation `PARTIAL` makes that incompleteness visible
without presenting historical campaign code as the application that future
Eval must become.

Removing the entire route was rejected because the name is intentionally
reserved. Keeping the campaign engines behind an inert command was also
rejected because importable implementation would leave an ambiguous owner and
could be mistaken for the supported contract. Keeping production prompt
fixtures under a generic evaluation capability was rejected because those
files affect live operation prompts and therefore belong with their actual
runtime consumers.

## Historical boundary

The older semantic-Eval records remain as implementation history, but they no
longer describe callable behavior. This note and the focused Eval boundary
matrix are the current ownership record. Eval remains `UNREVIEWED` in the
separate operation route-classification ledger; Help-facing `PARTIAL` maturity
is not a route-classification judgment.
