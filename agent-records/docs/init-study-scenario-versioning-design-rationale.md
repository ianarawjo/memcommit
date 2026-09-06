# Init-study packaged-scenario design rationale

## Decision

`mem init-study [NAME]` creates the packaged `coffee` scenario, and
`mem init-study [NAME] --scenario legacy` creates the preserved three-task
regression scenario. These are the only public scenario names. The former
`coffee-v1` and `legacy-v1` spellings were implementation versions rather than
useful participant choices, so they are no longer accepted.

Both scenarios are self-contained. Initialization builds an isolated
participant Profile and a run-private authority Profile directly from the
selected scenario, materializes the scenario's Grants, and atomically publishes
the pair. It does not require or create a registered source Profile. Therefore
`init-study --from-profile`, `profile import-study`, `profile refresh-study`,
and the special `study-baseline` Profile lifecycle were removed together.

## Scenario ownership

`memcommit.study_scenarios.coffee` owns the Coffee specification and builder.
Both scenarios now store Memory content as native Context JSON and use the
shared resource-import decoder/publication boundary; see
[native JSON import](native-json-import-design-rationale.md).
Legacy Practice is native data as well. Study retains run composition and Grant
materialization, while historical Markdown parsing is an external authoring
compatibility path only.
`memcommit.study_scenarios.legacy` owns the old fixture loader, bundle builder,
source corpus, and scenario-specific prewarm tooling. Keeping these together
makes the scenario a coherent input package instead of distributing its source
between `eval`, `agent-records`, and a root-level runtime package.

The generated files under `agent-records/outputs/study-fixtures` remain
historical execution evidence. They are not the runtime source of truth and are
not imported before initialization.

## Reproducibility and provenance

Every run still records the source identity and digest in the existing Study
provenance fields. Because no source Profile exists, each packaged scenario has
a stable virtual source UID and scenario name. The Legacy UID intentionally
matches the former canonical baseline identity so already recorded provenance
continues to correlate with the same fixture world. The Coffee UUID namespace
is also held constant after shortening the public name, preserving its
published Context and Memory identities.

The Legacy scenario reconstructs the same validated task packages and then
uses the same participant/authority composition and Grant materialization as
the old import-then-init route. Regression tests freeze its externally relevant
result: 65 participant Contexts with 471 owned Memories, 43 readable granted
Contexts with 625 granted Memories, 75 authority Contexts, and eight Grants.

## Prewarm boundary

Scenario initialization installs no semantic prewarm. A new run starts with no
checkpoints, sessions, receipts, ad-hoc caches, or shared prewarm attachment.
The Legacy prewarm modules remain scenario-owned research tooling for existing
artifacts and exact-registry tests, but they are not a hidden initialization
dependency.

## Tradeoff and non-goals

Removing the editable baseline eliminates the ability to change one registered
Profile and have later runs copy it. The selected replacement favors a command
whose scenario name completely identifies its packaged input. Editing a
scenario now means editing and reviewing its owned source, tests, and digest.

This change does not migrate or delete previously created `study-baseline`
Profiles or historical Study runs. After the special lifecycle is removed,
such a Profile is ordinary stored data and can be renamed or removed under the
normal Profile rules.
