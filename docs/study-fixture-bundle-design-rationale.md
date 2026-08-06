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
| 1 | 76 | 300 | 78 | 454 |
| 2 | 1 | 300 | 75 | 376 |
| 3 | 301 | 100 | 75 | 476 |
| Total | 378 | 700 | 228 | 1,306 |

The editable baseline additionally contains one participant-only rehearsal
Memory under `practice/description`, bringing the composed baseline to 1,307
ordinary Memories. It is not part of any Task corpus or authority package and
therefore does not change the reviewed Task counts above.

The old Korean XLSX was a smaller intermediate snapshot and is not a build
input. Spreadsheet views are regenerated from the current parsed corpus.

## Ordinary Context mapping

Every `init-study` participant Profile receives `practice/description` as a
separate local Context with one four-sentence composite Memory explaining Mem,
Memories, Contexts, impact preview, and reviewed saving. It exists solely for
the onboarding Atomize exercise. Keeping it outside `task-1`, `task-2`, and
`task-3` prevents rehearsal analyses, workbenches, and any accidental later
application from contaminating measured Task material. The run-private
granted-memory Profile never receives this Context and no Grant references it.
The Context and Memory identities are deterministic across runs. A baseline
created before this fixture existed is still accepted by `init-study`; the
new run receives the canonical practice fixture without mutating that older
baseline.

The canonical rehearsal Memory is deliberately one composite record rather
than four pre-split Memories:

```text
MemLab is a research prototype that provides command-line and terminal user interfaces (CLI/TUI) for managing agent memory and supporting collaboration among people and agents.
Through MemLab's operations and structural concepts—including Memories, Contexts, Profiles, Grants, and Sessions—you can manage agent memories as they are collected, organized, and propagated among people and agents.
In this study, you will use MemLab in three different situations, each involving a different context, goal, and kind of memory.
Before beginning, this practice session will introduce MemLab's basic controls and structure by guiding you through atomizing a short practice description.
```

The four claims introduce the vocabulary used by the tutorial while giving
Atomize a small, legible decomposition target. They avoid claims about any
Study Task, participant, or granted source.

Each Task Profile also owns one participant-facing description Memory directly
under `description`. Its English body is the previously authored Task
description and its Korean body is a same-UID translation. Keeping the brief
inside the Task branch makes it part of every baseline snapshot and
`init-study` run without treating it as authority-owned evidence or a Grant.
The operation-specific starting Context remains unchanged.

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
`READ+CREATE+UPDATE+DELETE+QUERY` for the wiki and a narrower
`QUERY+SESSION_LOG` override for the details. Whole-wiki query is explicit but
one-shot; durable transcript permission remains limited to the query-only
details condition.

Task 2 starts at an empty `participant/proposal-workspace` task Context.
`task-2-proposal-authority` owns `advisor1`, `advisor2`, and
`proposal-submission-guidelines`; the advisor views are `READ` and guidelines
are `QUERY+SESSION_LOG`. Task 3 owns `local/personal-memory` and
`local/guardrails`. `task-3-healthcare-authority` owns ordinary
`remote/government/healthcare-agent/info-request/transmission-guidance` and the
query-only sibling `questions-and-answers`. Only the public transmission
guidance receives a derived-work READ grant; questions-and-answers receives
`QUERY+SESSION_LOG`.
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
