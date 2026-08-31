# Legacy Study fixture package design rationale

## Decision

The preserved three-task fixture is the packaged `legacy` scenario. Its
human-reviewable English and Korean Markdown/TSV sources, strict loader, bundle
builder, and scenario-specific prewarm tooling live together under
`src/memcommit/study_scenarios/legacy/`.

Fixture review projections live under `legacy.authoring`; explicit research-time
prewarm producers live under `legacy.prewarm.generation`. The latter consume the
operation contracts and the scenario-owned prewarm registry, but they are not
general semantic-evaluation campaigns. Keeping them under the scenario package
prevents the fixed legacy corpus and its baseline publication workflow from
appearing to be product-wide evaluation infrastructure. The default Coffee
scenario does not import either package.

The bundle builder still creates a task store and a distinct authority store
for each task. English is canonical `Memory.content`; Korean is a same-UID
translation-catalog view. Authority-only and query-only material remains
ordinary authority-owned Context data, and manifests declare the Grant
templates that expose it.

The six intermediate stores are a validation and composition boundary, not a
public Profile lifecycle. `mem init-study NAME --scenario legacy` builds them
in private staging, validates their stores and Grant templates, reconstructs
the established participant/authority topology, publishes the final pair, and
removes staging. There is no `profile import-study`, `profile refresh-study`,
or registered `study-baseline` step.

## Preserved topology

The participant receives the three task branches and the two onboarding
Contexts, `practice/description` and `practice/source`. The authority Profile
receives the three authority branches. Public granted paths remain directly
below `task-N`; Context and Memory identities, translation catalogs, task
currents, and Grant permissions cross the composition boundary, while
checkpoints and operational artifacts do not.

The source corpus contains 381 task-owned, 700 authority READ/edit, and 228
authority QUERY records, for 1,309 ordinary task records. The rehearsal adds
15 participant-only Memories. The final regression contract remains 65
participant Contexts/471 owned Memories, 75 authority Contexts/853 owned
Memories, 43 effective granted Contexts/625 granted Memories, and eight Grants.

## Source and generated evidence

`legacy/data/` is the authored runtime source. Its annotations—purpose,
audience, relation, update action, and review state—remain build metadata and
are not prefixed to participant-visible content. `legacy/bundle.py` is the
deterministic loader-to-store transformation.

`agent-records/outputs/study-fixtures/` is retained as historical generated
evidence from the former workflow. It is neither imported nor read by
`init-study`; future generated comparisons should be treated as outputs of the
packaged source, not as a second writable source of truth.

## Tradeoff

The old editable Profile provided a convenient rehearsal surface but created
two mutable copies—the generated package and registered baseline—plus explicit
refresh conflict handling. Packaging the source removes that synchronization
problem and makes `--scenario legacy` reproducible, at the cost of requiring a
reviewed source change and test update for fixture edits.
