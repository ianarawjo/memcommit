# Study fixture bundle design rationale

## Decision

Each user-study task is built as a task store plus a separate task-specific
authority store. English is canonical `Memory.content`; reviewed Korean source
text is installed as a `ko` same-UID translation catalog. All source data,
including material exposed only through query, is ordinary authority-owned
Context data. The task receives permissioned views through manifest grant
templates rather than copies or forks.

```text
outputs/study-fixtures/
├── task-1/profiles/{task-1,task-1-campus-authority}/.mem
├── task-2/profiles/{task-2,task-2-proposal-authority}/.mem
└── task-3/profiles/{task-3,task-3-healthcare-authority}/.mem
```

`mem profile import-study` validates these six generated stores and their grant
templates, then composes them into one editable `study-baseline` Profile
without moving legacy `~/.mem`:

```text
study-baseline
├── practice/description
├── task-{1,2,3}/description
├── task-{1,2,3}/...
└── granted-memory/task-{1,2,3}/...
```

The package boundary remains split because it proves ownership and permission
contracts. The live authoring boundary is merged because the still-changing
Study Memory must be selectable, importable, and copyable as one unit.

Generated packages and the registered `study-baseline` are deliberately not
two automatically synchronized writable copies. `mem profile refresh-study`
is the explicit bridge: it validates all packages and grant templates, keeps
the baseline Profile UID stable, and swaps the store plus provenance in one
registry transaction. By default it compares the live store with the digest
recorded at import and refuses to overwrite divergence. The explicit
`--replace-edited-baseline` escape hatch is required when local baseline edits
have already been transferred to fixture sources or are intentionally being
discarded. This preserves an editable rehearsal layer without allowing stale
generated data to silently erase human corrections.

`mem init-study [NAME]` never rereads these generated packages. It snapshots
the current registered baseline into two run-private Profiles: `NAME` owns the
three participant Task branches, while `NAME-granted-memory` owns all three
authority branches. The command rematerializes the reviewed manifest grant
templates between those two Profiles, with public paths directly below
`task-N` (for example, `task-1/campus-wiki`). Context and Memory identities,
translation views, and task current Contexts cross the snapshot boundary;
checkpoints and other operational artifacts do not.

The participant Profile opens at the `practice` parent, not at a measured Task
Context or directly inside `practice/description`. The participant must descend
into the description before proceeding, while every Task-specific Context and
its fixture provenance remain intact for later explicit navigation. The
granted-memory Profile retains its Task 1 authority orientation because it is
not participant-facing onboarding state.

Both stores and all grants publish in one registry transaction. A failure
before that publication rolls back both stores. A participant mutation allowed
by Task 1's `CREATE` or `UPDATE` permission therefore changes only that run's
authority copy; it never changes `study-baseline`, the generated package, or a
different run. Later baseline changes apply only to later initialized runs.

## Source and generated artifacts

The language-partitioned Markdown and TSV files under `docs/fixtures/` are the
human-reviewable source. They use stable fixture IDs or canonical locators and
designer-only metadata such as purpose, audience, relation, update action, and
Verified state. Those annotations are not prefixed to Memory content.

The strict loader normalizes the three existing authoring shapes, merges the
purpose sidecars, validates the expected counts, and pairs English and Korean
only when locator, ID, purpose, audience, and source Verified state agree.
The current corpus contains:

| Task | Task-owned | Authority READ/edit | Authority QUERY | Total ordinary records |
| --- | ---: | ---: | ---: | ---: |
| 1 | 77 | 300 | 78 | 455 |
| 2 | 2 | 300 | 75 | 377 |
| 3 | 302 | 100 | 75 | 477 |
| Total | 381 | 700 | 228 | 1,309 |

The editable baseline additionally contains 15 participant-only rehearsal
Memories under `practice/description` and `practice/source`, bringing the
composed baseline to 1,324 ordinary Memories. They are not part of any Task
corpus or authority package and therefore do not change the reviewed Task
counts above.

The old Korean XLSX was a smaller intermediate snapshot and is not a build
input. Spreadsheet views are regenerated from the current parsed corpus.

## Ordinary Context mapping

Every `init-study` participant Profile receives two separate local rehearsal
Contexts. `practice/description` contains an overview, a `SITUATION`, and a
`TASK` Memory. The overview introduces memcommit and the three Study
situations. `SITUATION` explains the rehearsal Source and why it needs
atomization; `TASK` alone states the executable instruction to use the grouped
`mem help` browser, discover Atomize, and save the result as
`practice/source-atomized`. The visible role prefixes are deliberate
participant-facing content, not designer-only purpose metadata. The task does
not add a separate Impact, inspection, or approval step.
`practice/source` contains 12 Memories, one for
each newline-separated editing request from the original writing sessions.
Some of those requests still contain multiple independently reviewable
constraints for Atomize to separate. Separating the instruction from the source
prevents it from becoming Atomize evidence while still requiring the
participant to learn the help structure rather than receiving an exact
command.

Both Contexts exist solely for onboarding. Keeping them outside `task-1`,
`task-2`, and `task-3` prevents rehearsal analyses, workbenches, and any
accidental later application from contaminating measured Task material. The
run-private granted-memory Profile never receives these Contexts and no Grant
references them. Context and Memory identities are deterministic across runs.
A baseline created before this fixture existed is still accepted by
`init-study`; the new run receives the canonical practice fixture without
mutating that older baseline.

The three Practice description Memories are:

```text
memcommit is a research prototype that provides command-line and terminal user interfaces (CLI/TUI) for managing agent memory and supporting collaboration among people and agents.
Through memcommit's operations and structural concepts—including Memories, Contexts, Profiles, Grants, and Sessions—you can manage agent memories as they are collected, organized, and propagated among people and agents.
In this study, you will use memcommit in three different situations, each involving a different context, goal, and kind of memory.
```

```text
SITUATION · Before beginning the three study tasks, complete a short practice exercise to become familiar with how memcommit organizes and presents its commands. Each newline-separated editing note in `practice/source` is stored as its own Memory, preserving the boundaries between the original requests. Some notes still combine recurring constraints, rough wording, and typos.
```

```text
TASK · Divide their underlying constraints into appropriate atomic Memories without performing the requested edits, adding instructions, or changing the intended meaning, so that each constraint can be reviewed independently. Open `mem help`, inspect the available operations, find the operation designed for atomization, and use it to atomize the notes and save the result as `practice/source-atomized`.
```

The Source Context contains the following 12 accumulated English editing
notes. Each blank-line-separated excerpt below is stored as its own Memory, so
the original writing-session boundaries are data structure rather than prose;
no connective text was invented to make them sound like one request:

```text
When I ask “How does this read?”, I really want an opinion, so don't edit the draft immediately; first check the sentence order and paragraph division.

If I later ask for polishing, preserve the overall strucutre and citation-needed markers, and change only wording that causes a problem.

When I ask to change one expression, leave almost everything else as it is, including technical or project-specific terms that I selected. Um... for example, use distribute, not divide, when material is absorbed into two parts.

If a passage is supposed to make four points, keep all four while removing parts that are too redundent and stating repeated content only once.

When the draft has to fit a shorter fixed limit, aim to cut around 20–30% from redundant or unnecessary material.

But don't shorten sentences so aggressively that a claim sounds more categorical; keep enough wording to preserve its original strength and conditions.

If the next idea is merely related and does not broaden the scope, don't use More broadly; use In relation to this or another accurate connector without adding a new claim merely to make two paragraphs connect.

For any titlle about interaction with AI agent memory, keep the exact terminology and intended words: use interaction and management and AI agent memory rather than agent memory.

By default, format a document title in sentence case rather than title case. An explicitly named style guide may override only that capitalization default; always keep for whenever it is part of the intended wording.

If titles of works use quotation marks in some places and italics in others, make them consistently italic throughout the document by default; an explicitly named style guide may override only this work-title format.

When I say that content looks wrong, find accurate information before proposing a correction by reading the original paper, book, or guide, not only an abstract or a short snippet.

Before adding or reusing citations and refferences, verify that each source exists and supports the exact claim after reviewing the complete source. Don't invent quotations or evidence or overstate an author's contribution or a paper's status. If I asked only for review, report a verification problem first instead of silently rewriting the draft.
```

They deliberately retain the hesitant wording, repeated corrections, contextual
fragments, and misspellings from separately issued requests. The durable
constraints concern review-before-editing, structural fidelity, redundancy and
length, claim strength, terminology, transitions, title conventions, factual
verification, and citation provenance. Atomize should preserve the rough source
as evidence while proposing independently reviewable policies; the rehearsal
does not ask the model to perform any of the requested document edits or to
turn spelling correction into the semantic task.

The earlier fixture used `MemLab` as the participant-facing product name,
combined Practice situation and instruction in one task Memory, and included a
third provenance-only description Memory. The current fixture uses the
repository name `memcommit` and keeps the actionable instruction independently
visible. During initialization, only exact known legacy text is rewritten in
the run snapshot: the combined row keeps its stable task UID and becomes the
new `TASK`, while a deterministic `SITUATION` UID is inserted immediately
before it. Independently edited baseline prose is preserved. The retired
provenance Memory remains removable because it added a non-actionable row
without affecting the Atomize target or task contract. Snapshot migration does
not mutate the editable baseline. A retained Tutorial Atomize prewarm prepared
against the older description remains admissible only when temporarily
reconstructing the exact pre-split row, legacy brand, retired Memory, or their
known combinations makes its full description digest match. The compatibility
check never persists or renders those reconstructed variants, and any other
instruction difference still fails closed.

A cold production Atomize check used `gpt-5.6-sol` with reasoning `medium`.
Literal excerpts such as “polish this” initially returned `UNCERTAIN` because
their missing drafts and deictic referents made them incomplete durable
Memories. The fixture therefore states the same accumulated requests as
recurring editing policies, while retaining their separate excerpt boundaries,
rough wording, and typos. A later trial produced 20 children but reached the
decoder's child limit before covering the final source policies; it too was
rejected. After the excerpt boundaries became 12 distinct Source Memories, the
final cold run completed in `115.982` seconds. It classified nine Memories as
`ATOMIC` and three as `COMPOSITE`, reported no quality issue or unresolved
item, covered the complete Source, and projected these 17 Output Memories:

1. `When I ask “How does this read?”, I really want an opinion, so don't edit the draft immediately; first check the sentence order and paragraph division.`
2. `If I later ask for polishing, preserve the overall strucutre and citation-needed markers, and change only wording that causes a problem.`
3. `When I ask to change one expression, leave almost everything else as it is, including technical or project-specific terms that I selected.`
4. `When material is absorbed into two parts, use distribute, not divide.`
5. `If a passage is supposed to make four points, keep all four while removing parts that are too redundent and stating repeated content only once.`
6. `When the draft has to fit a shorter fixed limit, aim to cut around 20–30% from redundant or unnecessary material.`
7. `But don't shorten sentences so aggressively that a claim sounds more categorical; keep enough wording to preserve its original strength and conditions.`
8. `If the next idea is merely related and does not broaden the scope, don't use More broadly; use In relation to this or another accurate connector without adding a new claim merely to make two paragraphs connect.`
9. `For any titlle about interaction with AI agent memory, keep the exact terminology and intended words: use interaction and management and AI agent memory rather than agent memory.`
10. `By default, format a document title in sentence case rather than title case. An explicitly named style guide may override only that capitalization default.`
11. `Always keep for whenever it is part of the intended wording.`
12. `If titles of works use quotation marks in some places and italics in others, make them consistently italic throughout the document by default; an explicitly named style guide may override only this work-title format.`
13. `When I say that content looks wrong, find accurate information before proposing a correction by reading the original paper, book, or guide, not only an abstract or a short snippet.`
14. `Before adding or reusing citations and refferences, verify that each source exists and supports the exact claim after reviewing the complete source.`
15. `Don't invent quotations or evidence.`
16. `Don't overstate an author's contribution or a paper's status.`
17. `If I asked only for review, report a verification problem first instead of silently rewriting the draft.`

This cold check is the frozen semantic basis for the tutorial prewarm. The
validated analysis is published separately into the Study semantic registry.
Each new participant run receives only a hidden validation receipt. The first
matching `mem atomize` command materializes the ordinary Atomize analysis and
follows the ownership-aware decision-free policy: because the proposal has no
required decision and its Output is local and checkpointed, it applies without
an Impact, inspection, choice, or approval screen. Optional `REVIEW` findings
remain part of the retained analysis, but they do not create a required review
step. The tutorial intentionally contains no ambiguity interaction. Any change
to the Source or tutorial instruction invalidates the exact binding.

Each Task Profile owns two participant-facing description Memories directly
under `description`: `SITUATION` contains the role and surrounding scenario,
while `TASK` contains only the required outcome. Their English bodies are
canonical and their Korean bodies are same-UID translations. Keeping the brief
inside the Task branch makes it part of every baseline snapshot and
`init-study` run without treating it as authority-owned evidence or a Grant.
The historical description identity remains on `SITUATION`; each new `TASK`
uses its own stable fixture identity. This preserves existing provenance while
making the instruction independently retrievable and immediately visible in
`mem ls`.
Those operation-specific Contexts remain unchanged, but a newly initialized
participant run does not select one until the participant leaves Practice.

Each canonical locator's final segment is a Memory leaf. By default, the
preceding segments become physical ordinary Contexts linked from their parents.
Runtime Memory and Context UIDs are deterministic UUIDv5 values derived from
task and stable fixture identity, so rebuilds do not silently assign a
different identity to unchanged fixture records.

Task 3 deliberately keeps its reviewed source locator keys in the historical
`local/personal-memory/YYYY-MM/NN` form while mapping them to runtime owners named
`local/personal-memory/YYYY/MM`. The builder therefore materializes `2024`, `2025`,
and `2026` as empty structural year Contexts above the 30 monthly Contexts.
Separating fixture identity from runtime placement lets the live baseline move
the same monthly Contexts and Memories without rekeying their UIDs merely to
gain a navigable year level. Only the newly introduced year Contexts receive
new structural identities; they are organization, not personal Memory claims.

The package may omit a prefix that owns no fixture Memory. At Study import,
the Profile composer fills each such gap with a fresh empty ordinary Context;
the picker never invents a namespace-only row. Existing fixture Context
and Memory identities remain unchanged, while recursive listing and upward
navigation obtain a continuous lexical chain. These structural parents are a
Profile topology guarantee. During `init-study`, Task-side parents remain below
`task-N`, while authority-side parents are rebuilt below the same task prefix
inside the separate run-private authority Profile. They are not fixture claims
and are not embedded into their children or parents.

Task 1's task Profile owns only `participant/construction-updates`.
`task-1-campus-authority` owns ordinary `campus-wiki` and its
`construction-details` subtree. The task receives
`READ+CREATE+UPDATE+DELETE+QUERY` for the wiki and a narrower `QUERY` override
for the details. Both Query routes are one-shot.

Task 2 starts at an empty `participant/proposal-workspace` task Context.
`task-2-proposal-authority` owns `advisor1`, `advisor2`, and
`proposal-submission-guidelines`; the advisor views are `READ` and guidelines
are `QUERY`. Task 3 owns `local/personal-memory` and
`local/guardrails`. `task-3-healthcare-authority` owns ordinary
`remote/government/healthcare-agent/info-request/transmission-guidance` and the
query-only sibling `questions-and-answers`. Only the public transmission
guidance receives a derived-work READ grant; questions-and-answers receives
`QUERY`.
The real healthcare-agent parent supplies a non-recursive `SHARE` endpoint
grant under the stable recipient name `government/healthcare-agent`.

Each physical Context gets one fixture-import checkpoint representing its
preloaded baseline. Import does not simulate hundreds of participant-authored
`mem add` operations because those events did not occur in the study session.

## Same-UID Korean representations

For every ordinary English Memory, the builder creates a `ko` translation
catalog entry with the exact same source UID. Its origin is `IMPORTED` and its
initial status is `UNREVIEWED`. A Korean source checkbox proves review of that
source sentence, not English–Korean semantic equivalence, so it cannot safely
promote the pair to `VERIFIED` automatically.

The catalog stays outside the Context graph. Therefore `mem ls` shows only the
canonical English Memory once, while `mem translate --to ko` renders the
Korean representation under the same UID. Editing or reviewing the Korean
view does not add a Memory, create a checkpoint, or switch Contexts.

## Query-only bilingual views

Query-only fixture records use the same ordinary authority Context and
translation-catalog representation as readable records. The task Profile has
no `READ` grant, so Translate, list, show, export, and switch cannot open them.
`mem query` authenticates the provider first, then serializes only the frozen
grant scope in the requested complete language. Missing translated entries
fail closed. The local operating-system user can still read managed authority
files; this is study-UI authority, not cryptographic access control.

## Manifest and verification

Each schema-v2 task manifest lists both Profile packages, ownership for every
entry, source hashes, translations, and grant templates. A grant template
contains stable template/grant identities, source Context identity, task
attachment or parent-view attachment, public name, permissions, recursive
scope, exclusions, and provider where applicable. It supports exact joins and
end-to-end checks without putting designer annotations into Memory content.

The builder refuses a non-empty or symbolic-link destination and refuses any
path equal to, inside, or containing the configured live `STORE_DIR`. It stages
the complete task (or complete three-task set) in a temporary sibling,
  validates normal Context, checkpoint, grant-template, and translation-catalog
boundaries there, and publishes with one same-filesystem atomic rename. A
failure removes staging state, so the same destination can be retried without
manually cleaning a partial fixture. It then restores the process's original
store configuration. Builder-only graph/state, per-Context, and global
command-order lock files are removed before publication because they
coordinate a process rather than represent fixture data. This temporary
store-root adapter is deliberately
limited to a synchronous build process; general runtime store injection
remains a future refactor.

## Limitations

- The bundle builder does not publish, refresh, fork, or merge an
  organizational upstream. Task 1's authority Profile is a fixed study source.
- Audience metadata describes intended disclosure and is not enforced as an
  ACL by the current Memory schema.
- Translation status is review workflow state, not proof of equivalence.
- The generated `.mem` stores are immutable import inputs. Edits belong to the
  editable baseline during authoring. Participant edits belong only to the
  initialized run's authority copy and do not flow back to the baseline,
  fixture source, or package. Authoring checkpoints are intentionally not
  imported into a participant run.
- Profile replacement, reset, and export of participant outputs remain
  separate recoverable workflow decisions.
