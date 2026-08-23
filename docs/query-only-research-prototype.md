# Query-only Context research prototype

## Decision

Some study information should be visible as an available view without being
readable through `mem ls`, `mem show`, or `mem switch`. Participants can ask
questions and receive only an answer.

New study bundles implement that interaction as a `QUERY` authority grant.
The source is an ordinary Context tree in a separate, switchable task-specific
authority Profile; the task Profile contains no source copy. A grant is a
view permission, not a fork or a special storage kind. The older
`QueryContextRef` plus `query-sources/` representation remains supported for
legacy and developer fixtures.

## Authority-granted data model

The Profile registry records the public view, authority and grantee Profile
UIDs, task attachment Context UID, source root Context UID, permission set,
and a frozen exact Context scope. With only `QUERY`, ordinary task-side
listing renders the view name and `(query-only)` mode but never loads the
authority Memories. Selecting the authority Profile gives its owner normal
Context and Memory CRUD.

Task 1 therefore has this physical and projected topology:

```text
task-1 Profile                         task-1-campus-authority Profile
participant/construction-updates      campus-wiki
  └── campus-wiki [READ+CREATE+UPDATE]  ├── readable wiki Contexts
      └── construction-details [QUERY]   └── construction-details Contexts
```

The narrower query grant overrides the broader wiki read grant. `mem ls
campus-wiki -R` can list the readable wiki while rendering the details link
without traversing its ordinary authority Contexts.

## Legacy `QueryContextRef` data model

A parent Context stores only this pointer record:

```json
{
  "type": "query_context_ref",
  "uid": "<reference UUID>",
  "name": "contractor-agreements",
  "target_source_uid": "<source UUID>",
  "provider": "codex_chatgpt"
}
```

The source content is not copied into the parent or its checkpoints. For the
study fixture, it is kept separately. Schema v2 stores an ordered set of
stable entry UID/key records, canonical English content, and optional complete
language variants such as `ko` inside that concealed file:

```text
~/.mem/
├── contexts/
│   └── facilities-reference/
│       ├── context.json
│       └── checkpoints/
└── query-sources/
    └── <source UUID>/
        └── source.json
```

The UUID is validated before it is used as a path. The query-source directory
and file are created with owner-only permissions where the operating system
supports them. The original import pathname is not persisted.
Stable entry keys must be printable and cannot contain control, format,
surrogate, zero-width, or bidirectional-override characters. This prevents a
concealed identifier from spoofing adjacent trusted output.

This arrangement prevents normal memcommit operations from accidentally
loading the source. It is deliberately outside `contexts/`, so it is not:

- returned by `mem contexts`;
- selectable with `mem switch`;
- traversed by `mem ls -R`;
- included in a Context checkpoint;
- copied into a branch or merge.

A branch, merge, or revert carries only the `QueryContextRef` pointer.
Removing or clearing that pointer does not delete the underlying study source,
because another Context may still refer to it.

Schema-v1 one-string sources remain readable as one deterministic legacy
entry. New study packages use schema v2. Entry identity is invariant across
language selection; a Korean query does not create a second query source or
ordinary Memory. A requested non-English variant must cover every entry or
loading fails closed with a generic unavailable-translation error. That error
does not echo the concealed key or other source metadata. Mixed English fallback exists only as an explicit
low-level option and is not the participant-facing default.

`QuerySource.content` remains the compatibility surface for provider callers;
it joins the selected entry contents exactly as the earlier one-string object
did. Direct dataclass construction and `dataclasses.asdict()` were never a
persistence contract and now expose the entry-oriented in-memory shape. Code
outside the store should obtain a source through `MemoryStore` and consume
`content` or `contents`, rather than constructing or serializing this internal
record itself.

## Task 1 visible wiki and query-only detail view

Task 1 keeps its participant workspace and authority-owned campus data in
different Profiles. Their canonical identifiers follow
[`task-1-naming-contract.md`](task-1-naming-contract.md):

```text
participant/construction-updates       task-owned change source
campus-wiki                            granted readable/editable view
└── construction-details               narrower granted query-only view
```

The authority Profile contains both trees as ordinary data. The task receives
no persisted `QueryContextRef` or Context copy; registry grants derive both
views at command time. `-fork` is deliberately absent because no divergent
copy or publication workflow exists.

## Commands

`mem query` also accepts one unrecognized operand as a natural-language
question for the selected ordinary Context. That path shares Find's visible
Memory and activity-artifact search frame; it does not weaken or replace the
query-only routing contract below. A recognized query-only selector continues
to take precedence.

The researcher installs a fixture with the hidden developer command:

```bash
mem dev query-source install contractor-agreements \
  --from ./contractor-agreements.md \
  --into facilities-reference
```

This does not change the active Context. Installation is rolled back if the
parent Context cannot be saved.

Participant-facing inspection deliberately reveals metadata only:

```text
$ mem ls facilities-reference
[query   1234abcd] contractor-agreements (query-only)
```

```text
$ mem show contractor-agreements --context facilities-reference
Query-only Context: contractor-agreements
Mode: query-only research prototype
Content: concealed from mem ls and mem show
```

Legacy pointer questions use:

```bash
mem query contractor-agreements \
  "May contractors enter the building on weekends?"
```

A Task 1 authority view can be queried in its complete Korean view without
exposing it through ordinary list or Translate:

```bash
mem query campus-wiki/construction-details \
  "공사기간 후문을 이용할 수 있나요?" \
  --language ko
```

`mem query` resolves either a direct legacy `QueryContextRef` or an effective
`QUERY` grant. Questions and answers are process-local and are not saved,
replayed, or listed by memcommit. Language selection occurs only after
provider authentication and inside the authority
source-loading boundary.

## Temporary Codex provider

The current provider starts one non-interactive Codex process per query. It:

1. rejects `OPENAI_API_KEY`, `CODEX_API_KEY`, and `CODEX_ACCESS_TOKEN`
   authentication overrides;
2. probes a working Codex executable;
3. requires `codex login status` to report exactly `Logged in using ChatGPT`;
4. verifies authentication before opening the concealed source;
5. passes the source and question through standard input, never shell command
   text or process arguments;
6. runs `codex exec` in an empty temporary directory with ephemeral,
   read-only, no-user-config settings;
7. returns only the final standard-output answer and deletes the temporary
   directory.

With that login mode, Codex usage is charged against the user's Codex access
in their ChatGPT plan (and any applicable ChatGPT credits), rather than an
OpenAI Platform API key. Each query still consumes the plan's usage allowance.
OpenAI documents the distinction in
[Codex authentication](https://learn.chatgpt.com/docs/auth) and
[Codex pricing](https://learn.chatgpt.com/docs/pricing).

`--ephemeral` prevents a local Codex session rollout from being persisted. It
does not mean that OpenAI receives no source text, nor does it override the
service's server-side data handling.

## Security boundary and study scope

This is a user-interface and interaction prototype, not confidentiality
enforcement:

- `mem trace`, `mem rationale`, `mem impact atomize`, `mem atomize --save`,
  and `mem atomize --save-as` never call the query-source loader. They may
  preserve the public `QueryContextRef` pointer, but concealed source text is
  not a candidate, provider input, trace source, or copied Memory. This is a
  tested command-path invariant, not an operating-system security boundary;
- the local operating-system user can still open legacy `query-sources/` or
  managed authority-Profile files directly;
- the source is sent to the selected model provider;
- a model can still produce an over-broad answer despite the prompt;
- the one-shot Codex process still has a tool surface, and its read-only
  sandbox can read host files; the instruction not to use tools is a prompt,
  not OS-level read isolation;
- local administrators and processes with the same permissions can read it.

Use fictional or otherwise approved study data only. A production design
should run a tool-less model endpoint in a real process/container boundary,
keep the source on an access-controlled MCP server or internal network
service, and return only policy-filtered answers.

## Provider replacement

The legacy `QueryContextRef.provider` and the study grant template's provider
are allowlisted keys, not commands or executable paths. The provider adapter
separates authority storage from answer generation, so a later MCP or
internal-network implementation can replace `codex_chatgpt` without changing
the public view or query-session contract.

As checked on 2026-07-27, Claude Code also supports a one-shot
`claude -p` mode and can use an individual Claude subscription login. Its
`ANTHROPIC_API_KEY` and cloud-provider authentication settings can override
subscription OAuth and cause usage-based billing, so a Claude adapter would
need its own fail-closed authentication check. Anthropic also limits how
third-party products may route subscription OAuth credentials; a broadly
distributed product should use an approved API or confirm the arrangement
with Anthropic. See
[Claude Code programmatic usage](https://code.claude.com/docs/en/headless),
[authentication](https://code.claude.com/docs/en/authentication), and
[legal and compliance](https://code.claude.com/docs/en/legal-and-compliance).
