# MCP installed-wheel verification

Last verified: 2026-08-15 against source commit `b8cae0bd`.

## Gate and environment

This check asks a narrower question than whether the whole repository is ready
for release: can a wheel containing the committed MCP transport be installed
with its optional dependency and complete a real stdio session without
importing the source checkout?

The successful run used:

- MemCommit wheel version `0.0.1`;
- CPython `3.13.5`;
- official MCP Python SDK `2.0.0`;
- a new virtual environment, working directory, HOME, and Store under `/tmp`;
- a wheel built from `git archive b8cae0bd`; and
- `tests/installed/mcp_stdio_smoke.py` as the external official client.

The smoke script rejects any MemCommit import whose path is under the source
checkout. It finds the installed `mem-mcp` entry point, starts it with an
explicit Store root, and communicates only through the SDK's stdio client and
`ClientSession`.

## Verified path

The client completed MCP initialization and discovered, in frozen registry
order:

1. `memcommit_query`
2. `memcommit_add_memories`

It invoked Add with two exact Memory texts and an explicit `smoke/target`
Context. The MCP result contained matching success and receipt data; an
independent Store read found the two texts in order and exactly one checkpoint
whose UID matched the returned receipt. A call to an unregistered tool returned
`isError: true`, `code: unknown_tool`, and `retryable: false`. Closing the client
closed the stdio server process normally.

The loaded module origin was inside the new environment's `site-packages`, not
the source checkout. Query was verified through discovery in this run; invoking
it was intentionally excluded because it would require an external semantic
provider. Query execution remains covered at the public client, agent adapter,
registry, projection, and in-memory MCP server layers.

## Distribution findings

Two existing packaging boundaries appeared before the successful run:

1. A wheel built without clearing the archive's tracked `build/` directory
   copied stale `build/lib/memcommit/context.py` instead of the current source
   module. The installed file's SHA-1 matched the stale copy and lacked
   `GrantedContextLink`, so server import failed. The successful verification
   moved that derived tree aside only in the temporary build directory. The
   repository copy was not changed.
2. With the person's normal HOME, importing the installed package read a newer
   Profile registry before the explicit `--root` was processed and failed its
   schema-version check. The successful verification used a fresh HOME. This
   shows that explicit-root startup is not yet fully isolated from process-global
   Profile configuration at import time.

These are not MCP protocol failures, and neither was hidden or repaired inside
the transport adapter. They remain blockers for calling an ordinary unclean
repository build an authoritative wheel. The packaging work should remove
tracked derived build output from artifact selection and defer Profile loading
until a Profile-backed Store is actually selected.

## Reproduction contract

Build from a clean source tree that does not contain stale `build/` output,
install the local wheel with its extra, and invoke the smoke client from outside
the checkout:

```text
uv build --wheel --out-dir ARTIFACTS CLEAN_SOURCE
uv venv VENV
uv pip install --python VENV/bin/python "ARTIFACT.whl[mcp]"
HOME=ISOLATED_HOME PATH="VENV/bin:$PATH" VENV/bin/python \
  tests/installed/mcp_stdio_smoke.py \
  --store ISOLATED_STORE \
  --workdir OUTSIDE_CHECKOUT \
  --forbid-origin SOURCE_CHECKOUT
```

On Windows, use the virtual environment's `Scripts` paths. Native Windows
behavior is not claimed by this macOS verification.
