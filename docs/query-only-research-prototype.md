# Query-only Context research prototype

## Decision

Some study information should be visible as an available Context without
being readable through `mem ls`, `mem show`, `mem switch`, or ordinary Context
files. Participants should be able to ask questions of that information and
receive only an answer.

The prototype represents this with a distinct `QueryContextRef`. It does not
change the existing `context_ref`: an ordinary `context_ref` remains a live,
readable reference to another Context.

## Data model

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
study fixture, it is kept separately:

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

## Task 1 organizational origin and local fork

For the revised Task 1 authority model, the organizational wiki and the
participant's working copy are deliberately different objects. Their
canonical identifiers follow
[`task-1-naming-contract.md`](task-1-naming-contract.md):

```text
campus-wiki                         query-only organizational origin
participant/campus-wiki-fork        writable local fork of the participant's assigned scope
participant/construction-updates    verified local change source
```

The local fork can contain direct, writable Memories for the assigned wiki
sections and a `QueryContextRef` named `campus-wiki` for asking bounded
questions of the opaque origin. Ordinary traversal, `impact`, and `update`
must not open that pointer. They operate only on the fork's directly available
local material. This avoids treating query access as either a full checkout or
write permission.

The current query-only prototype can preserve and query such a pointer, but it
does not create a scoped fork from the concealed source, bind a fork to an
upstream revision, refresh it, or publish changes. Task 1 must therefore seed
the local fork as fixture data. Future `push` or PR support must treat
publication as a separate authorized operation rather than allowing `update`
to write through the pointer.

The seeded fork is assumed to be the latest approved snapshot of the
participant's assigned scope when Task 1 begins, with no concurrent remote
change to that scope during the task. This is a study-scenario simplification,
not a guarantee provided by `QueryContextRef`. A later publication adapter
must replace it with explicit upstream revision and divergence checks.

## Commands

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

Questions use:

```bash
mem query contractor-agreements \
  "May contractors enter the building on weekends?"
```

`mem query` resolves only a direct `QueryContextRef`. It does not save the
question, answer, or a checkpoint.

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
- the local operating-system user can still open `~/.mem/query-sources`;
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

`QueryContextRef.provider` is an allowlisted provider key, not a command or
executable path. The provider adapter separates Context storage from answer
generation, so a later MCP, internal-network, or Claude implementation can
replace `codex_chatgpt` without changing the pointer model or public command.

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
