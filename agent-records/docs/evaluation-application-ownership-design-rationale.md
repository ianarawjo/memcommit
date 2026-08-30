# Eval operation and authored fixture ownership

## Decision

Executable campaign behavior belongs to the displayed Eval operation under
`memcommit.application.operations.eval`. `semantic_campaign.py` owns replayable
ambiguity and duplicate campaigns, `operation_gate_campaign.py` owns the
operation-gate campaign, and the older developer-only Forget/Integrate runner
and deterministic scoring code live beside those engines.

The package `memcommit.application.capabilities.evaluation` now owns only the
authored JSON resources and the narrow `fixture_path`/`fixture_resource`
accessors. It is not a second executable Eval implementation. This split makes
`mem help` navigation direct without pretending that all JSON files are used
only by Eval.

## Why the fixtures do not all belong to Eval

The directory contains three materially different resource roles:

- Eval-only campaign corpora: `operation_gates*.json` and their locks,
  `ambiguity_holdout.json` and its lock, plus the ambiguity/duplicates
  calibration corpus when replayed by `mem eval run`.
- Production prompt/rule resources: `atomize.json`, `duplicates.json`,
  `ambiguity.json`, `conflict.json`, `comparison_summary.json`,
  `rationale.json`, `resolve.json`, and `distill_makemore.json`.
- Research or contract-only resources currently read only by tests:
  `distill_goal_holdout.json`, `distill_makemore_holdout.json`, and
  `update.json`. The old developer Eval runner additionally reads
  `forget.json` and `integrate.json`.

Production prompt consumers use these resources at request construction, not
after a command merely for scoring. Atomize validates its authored profile and
adds Atomize plus ambiguity/conflict calibration cases. Find Duplicates,
Ambiguities, and Conflicts add their corresponding cases. Compare, Rationale,
and Resolve add normative rules and optionally authored cases. Distill and
Makemore render the reviewed bidirectional example families into their provider
instructions. The shared semantic prompt policy omits authored examples in
Study turns while retaining the normative rules where applicable.

Because those files influence real provider input, moving the whole fixture
directory into `operations.eval` would make production operations depend on a
peer operation. The resource-only capability is the temporary honest owner.
A future split may give each operation its own rules and cases, with only true
cross-operation corpora remaining shared, but that requires coordinated
packaging and prompt-version migration rather than a directory rename.

## Boundaries

The Eval console imports campaign engines only from
`memcommit.application.operations.eval`; the hidden legacy developer command
imports its runner there as well. Production operations import only the
resource accessor, never an Eval campaign engine. Engine defaults resolve
packaged fixture paths through that accessor, while callers may still pass an
explicit fixture path for a campaign run.

There is no compatibility facade for the former
`memcommit.application.capabilities.evaluation.semantic_campaign`,
`operation_gate_campaign`, `runner`, or `scoring` paths. Retaining them would
leave two apparent owners. Fixture bytes and package-data location are
unchanged, so retained fixture digests and calibration locks stay valid.

## Limitations

The name `capabilities.evaluation` remains broader than its new resource-only
role. Renaming or splitting that package is deferred until every production
fixture receives an operation-specific ownership decision. The legacy
Forget/Integrate runner is kept operational but is not evidence that those
fixtures define the current Forget or Meld/Integrate application contracts.
