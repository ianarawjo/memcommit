# MCP installed-wheel verification

Status: HISTORICAL. MCP distribution support was retired on 2026-08-27; see
`agent-adapter-ownership-and-mcp-retirement-design-rationale.md`. These runs
remain evidence for the former transport and do not describe the current
wheel.

Last verified: 2026-08-16 against the Replace callable-boundary worktree.

## Current eighteen-tool and import-isolation gate

A fresh wheel built from the current worktree was installed with its `[mcp]`
extra into a new `uv` virtual environment. The official MCP
2.0.0 stdio client ran from outside the checkout, imported MemCommit from that
environment's `site-packages`, and discovered this exact registry order:

1. `memcommit_help`
2. `memcommit_show`
3. `memcommit_find`
4. `memcommit_replace`
5. `memcommit_search`
6. `memcommit_query`
7. `memcommit_quality_find`
8. `memcommit_add_memories`
9. `memcommit_compare`
10. `memcommit_meld`
11. `memcommit_atomize`
12. `memcommit_atomize_grounding`
13. `memcommit_distill`
14. `memcommit_elaborate`
15. `memcommit_fit`
16. `memcommit_forget`
17. `memcommit_resolve`
18. `memcommit_dedun`

The client then invoked Add and verified its checkpoint independently. It
planned provider-free Replace over both added Memories, applied the exact
reviewed digest, independently verified both changed texts and the second
checkpoint, and confirmed `provider_used: false` across plan and Apply. It
opened a durable review-only Grounding dialogue without a provider. For
structural Atomize it exercised two saved sessions without provider access:
one exact in-place Apply/retry, plus response replacement, require-new Output
planning, Save As/retry, Source preservation, destination selection, and both
single-checkpoint outcomes. It also invoked Forget Analyze on an empty direct
Source without constructing a provider, applied the explicit no-op, retried
the exact version in the same process, and verified zero Forget checkpoints.
Finally, it confirmed that an unknown tool returns the typed `unknown_tool`
error. This proves that the eighteen
registered adapters and their transitive modules ship in the wheel and cross
the installed MCP discovery boundary. Provider-backed semantic execution remains
covered by the in-process public-client, agent-registry, and MCP-projection
tests; the installed smoke intentionally makes no external provider call.
Compare and Resolve are exercised through installed discovery here rather than
live semantic invocation. Forget additionally crosses installed
execution through its provider-free empty-Source route; its provider-backed
and changed-Apply paths remain covered in-process.

From a second process whose working directory was outside the checkout,
`import memcommit` did not load `memcommit.adapters.python_api`; resolving the real public
client loaded no Add, Fit, Distill, Elaborate, Forget, Ground, Meld, or Query
application implementation. The resolved root/API client objects retained
identity and the module origin remained under `site-packages`.

The wheel was version `0.0.1`, CPython was `3.13.5`, and the loaded module origin
was under the new temporary environment rather than this source checkout. No
build artifact was written into the repository.

## Gate and environment

This check asks a narrower question than whether the whole repository is ready
for release: can a wheel containing the committed MCP transport be installed
with its optional dependency and complete a real stdio session without
importing the source checkout?

The earlier clean-commit run used:

- MemCommit wheel version `0.0.1`;
- CPython `3.13.5`;
- official MCP Python SDK `2.0.0`;
- a new virtual environment, working directory, and Store under `/tmp`;
- a wheel built normally from an unmodified `git archive 7aad0230`; and
- `tests/installed/mcp_stdio_smoke.py` as the external official client.

The smoke script rejects any MemCommit import whose path is under the source
checkout. It finds the installed `mem-mcp` entry point, starts it with an
explicit Store root, and communicates only through the SDK's stdio client and
`ClientSession`.

## Verified path

The earlier client completed MCP initialization and discovered the then-shipped
registry order:

1. `memcommit_query`
2. `memcommit_add_memories`

The current eighteen-tool run above supersedes that historical discovery list for
package-completeness evidence while preserving the older run's clean-commit and
invalid-HOME regression record.

It invoked Add with two exact Memory texts and an explicit `smoke/target`
Context. The MCP result contained matching success and receipt data; an
independent Store read found the two texts in order and exactly one checkpoint
whose UID matched the returned receipt. The Atomize reads separately verified
that in-place Apply changed only its Source, Save As preserved its Source and
created/selected the planned output, and exact retries reused their respective
checkpoint UIDs. A call to an unregistered tool returned `isError: true`,
`code: unknown_tool`, and `retryable: false`. Closing the client closed the
stdio server process normally.

The loaded module origin was inside the new environment's `site-packages`, not
the source checkout. Query was verified through discovery in this run; invoking
it was intentionally excluded because it would require an external semantic
provider. Query execution remains covered at the public client, agent adapter,
registry, projection, and in-memory MCP server layers.

The installed Forget call separately verified process-local retention,
provider-free empty-Source analysis, explicit no-op Apply, exact replay, and
zero checkpoints.

The same installed wheel passed twice: once with the person's normal HOME and
once with a deliberately invalid HOME Profile registry containing unsupported
`schema_version: 999`. Because the server was started with `--root`, neither
the client fixture nor the server consulted that unrelated Profile state.

## Resolved distribution findings

Two existing packaging boundaries appeared before the successful run:

1. A wheel built with the former tracked `build/` directory
   copied stale `build/lib/memcommit/context.py` instead of the current source
   module. The installed file's SHA-1 matched the stale copy and lacked
   `GrantedContextLink`, so server import failed. Commit `ee3fcdc7` stopped
   tracking 164 derived paths and ignored root build products. The final check
   needed no special removal or relocation before ordinary `uv build`.
2. With the person's normal HOME, importing the installed package read a newer
   Profile registry before the explicit `--root` was processed and failed its
   schema-version check. Commit `7aad0230` made import path values lazy and
   froze Store roots at construction. The final invalid-registry run proves an
   explicit root now bypasses HOME Profile parsing entirely.

These were not MCP protocol failures, and neither was hidden inside the
transport adapter. They were repaired at their owning packaging and Store
initialization boundaries. This check establishes the installed MCP slice; it
does not by itself certify every CLI/TUI operation or native Windows behavior.

## Reproduction contract

Build the committed source tree normally, install the local wheel with its
extra, and invoke the smoke client from outside the checkout:

```text
uv build --wheel --out-dir ARTIFACTS CLEAN_SOURCE
uv venv VENV
uv pip install --python VENV/bin/python "ARTIFACT.whl[mcp]"
PATH="VENV/bin:$PATH" VENV/bin/python \
  tests/installed/mcp_stdio_smoke.py \
  --store EXPLICIT_STORE \
  --workdir OUTSIDE_CHECKOUT \
  --forbid-origin SOURCE_CHECKOUT
```

On Windows, use the virtual environment's `Scripts` paths. Native Windows
behavior is not claimed by this macOS verification.
