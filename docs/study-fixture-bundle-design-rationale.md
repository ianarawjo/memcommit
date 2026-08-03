# Study fixture bundle design rationale

## Decision

The three user-study tasks are built as three independent, swappable `.mem`
stores. English is the canonical `Memory.content`; the reviewed Korean source
text is installed as a `ko` same-UID translation catalog. Query-only material
uses concealed bilingual QuerySource entries rather than an ordinary
translation catalog.

```text
outputs/study-fixtures/
├── task-1/.mem
├── task-2/.mem
└── task-3/.mem
```

This follows the study's reset-and-swap procedure. The installed application
still uses one `~/.mem`; the study harness can replace that complete directory
between tasks. The prototype does not reinterpret `mem switch` as a cross-task
operation and does not change the global storage architecture solely for the
fixture.

## Source and generated artifacts

The language-partitioned Markdown and TSV files under `docs/fixtures/` are the
human-reviewable source. They use stable fixture IDs or canonical locators and
designer-only metadata such as purpose, audience, relation, update action, and
Verified state. Those annotations are not prefixed to Memory content.

The strict loader normalizes the three existing authoring shapes, merges the
purpose sidecars, validates the expected counts, and pairs English and Korean
only when locator, ID, purpose, audience, and source Verified state agree.
The current corpus contains:

| Task | Ordinary | Query-only | Total |
| --- | ---: | ---: | ---: |
| 1 | 375 | 78 | 453 |
| 2 | 300 | 75 | 375 |
| 3 | 375 | 75 | 450 |
| Total | 1,050 | 228 | 1,278 |

The old Korean XLSX was a smaller intermediate snapshot and is not a build
input. Spreadsheet views are regenerated from the current parsed corpus.

## Ordinary Context mapping

Each canonical locator's final segment is a Memory leaf; the preceding
segments become physical ordinary Contexts linked from their parents. Runtime
Memory and Context UIDs are deterministic UUIDv5 values derived from task and
stable fixture identity, so rebuilds do not silently assign a different
identity to unchanged fixture records.

Task 1 follows the separate naming contract:

- `participant/construction-updates` is the initial Context;
- `participant/campus-wiki-fork` is the writable local wiki graph; and
- `campus-wiki` is the opaque query-only organizational source.

Task 2 starts at `advisor1` and also contains `advisor2`. Both roots reference
the same concealed `proposal-submission-guidelines` source. Task 3 starts at
`personal-memory`, also contains `guardrails`, and lets both roots address the
same concealed `government/healthcare-agent/information-request` source.

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

## Concealed bilingual sources

Query-only records cannot use ordinary translation views: opening them through
Translate, export, list, or show would defeat the concealment contract. A
schema-v2 QuerySource instead stores stable entry UID/key pairs with canonical
English and optional `ko` content inside `query-sources/`. `mem query` selects
the requested complete language variant inside that boundary.

Missing translated entries fail closed by default. English fallback is an
explicit low-level option and is not used by the fixture. The local operating
system user can still read the files; query-only remains study-UI concealment,
not cryptographic access control.

## Manifest and verification

Each task package includes `manifest.json` with the task, dataset, stable
fixture key, canonical locator, runtime owner, runtime UID, purpose, audience,
source hashes, query-only flag, source filenames, translation origin, and
review status. It supports exact spreadsheet joins and end-to-end checks
without putting designer annotations into Memory content.

The builder refuses a non-empty or symbolic-link destination and refuses any
path equal to, inside, or containing the configured live `STORE_DIR`. It stages
the complete task (or complete three-task set) in a temporary sibling,
validates normal Context, checkpoint, query-source, and translation-catalog
boundaries there, and publishes with one same-filesystem atomic rename. A
failure removes staging state, so the same destination can be retried without
manually cleaning a partial fixture. It then restores the process's original
store configuration. Builder-only state and Context lock files are removed
before publication because they coordinate a process rather than represent
fixture data. This temporary store-root adapter is deliberately
limited to a synchronous build process; general runtime store injection
remains a future refactor.

## Limitations

- The bundle builder does not publish, refresh, or merge an organizational
  upstream; Task 1's query-only `campus-wiki` is a fixed study source.
- Audience metadata describes intended disclosure and is not enforced as an
  ACL by the current Memory schema.
- Translation status is review workflow state, not proof of equivalence.
- The generated `.mem` stores are task inputs. Study reset automation and
  preservation of participant outputs are separate operational concerns.
