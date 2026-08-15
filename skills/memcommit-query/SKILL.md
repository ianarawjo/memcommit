---
name: memcommit-query
description: Use the registered memcommit_query tool to browse or answer ordinary readable Contexts, authority-granted query-only views, and exact legacy QueryContextRef Sources. Use when a user asks an agent to query MemCommit memory, inspect an opaque granted catalog, ask about a catalog handle, or save a granted Query session. Requires the host to expose version 1 of the tool; do not use for mutation or invent missing route metadata.
---

# MemCommit Query

Invoke `memcommit_query` directly. Do not reconstruct the operation with
`mem query`, Python snippets, provider calls, or filesystem reads.

## Select one explicit route

- Use `ordinary` for a question over readable ordinary Contexts. Supply known
  `context_names`, or omit them only when the host's frozen current Context is
  intentionally the target. Set descendant and embedded reach explicitly when
  the user specifies scope.
- Use `granted` for a public query-only view. Omit `question` to browse its
  opaque catalog. When asking about one returned handle, pass that exact
  `memory_handle`. Supply `session_name` only when the user requests a durable
  visible transcript.
- Use `reference` only when exact `uid`, `name`, `target_source_uid`, and
  `provider` metadata came from an existing `QueryContextRef`. Never guess or
  synthesize any of these fields.

Always send `version: 1`. Never silently change one route into another after an
error.

## Interpret the response

- On `ok: true`, answer from `result` without claiming access beyond the
  returned evidence.
- For ordinary Query, retain citation numbers and distinguish
  `grounded: false` from a supported answer.
- For granted `CATALOG`, describe only returned handles and placeholders; do
  not infer concealed content.
- For a granted answer with `session_receipt`, report that the visible turn was
  saved. Without a requested session, do not imply persistence.
- Treat `publication_failed` as no returned answer and no confirmed new turn,
  even if provider work may have completed internally.

## Handle failures

Do not expose or speculate about hidden provider, storage, or host details.
Correct `invalid_request` locally only when the intended values are already
known. Ask the user for missing Context, public-view, session, or reference
information. Retry only `provider_failure`, at most once, and only when it still
matches the user's request. Do not retry publication, storage, authority, or
internal failures automatically.

If `memcommit_query` is unavailable, state that the host has not registered the
required tool. Do not fall back to shell access unless the user separately asks
for CLI use.
