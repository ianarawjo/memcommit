# Atomize Grounding agent-tool design rationale

Last verified: 2026-08-15.

## Motivation

Conversational Atomize Grounding already has one durable application workflow
and one public Python facade. An agent should not drive the terminal workbench,
reconstruct saved sessions, or reproduce provider, freshness, checkpoint, and
recovery rules. It needs a small machine contract that enters the same public
facade used by other non-terminal hosts.

`memcommit_atomize_grounding` projects the five public lifecycle operations as
one versioned tool. One tool keeps discovery centered on the operation while
the required `kind` discriminates the exact lifecycle transition. It does not
introduce a second Grounding implementation.

## Version 1 request contract

Every request is a closed JSON object with `version: 1`, one exact `kind`, and
no fields owned by another kind. `context_name` is optional for every action;
the public client resolves an omitted value from its frozen Store state and
resolves an explicit relative locator against one current-Context snapshot.

| `kind` | Additional input | Provider | Durable meaning |
| --- | --- | --- | --- |
| `open` | none | no | read one saved dialogue; no mutation |
| `start` | `selector`, `comment` | yes | assess one issue and save the complete first turn |
| `reply` | `reply`, optional `revision` | yes | assess and save one complete revision turn |
| `keep` | none | no | close the dialogue as review-only; Memories stay unchanged |
| `apply` | none | no | apply or recover the exact ready proposal in one checkpoint |

`revision` is one of `CONFIRM`, `EXTEND`, `CORRECT`, or `RETRACT`, and defaults
to `EXTEND`. The adapter accepts case-insensitive revision text during direct
in-process invocation and normalizes it before the public call; the published
JSON Schema exposes the canonical uppercase values. Empty text, missing
required fields, unknown fields, booleans masquerading as the integer version,
and cross-kind fields fail before Store or provider access.

## Response and error boundary

A successful response contains the saved session identity and digest, Context,
state, issue identity and arity, turn count, current understanding, current
status and explanation, typed follow-up questions, exact proposals, readiness,
and any saved checkpoint UID. Tuple-valued public projections become JSON
arrays without dropping issue links. `apply` additionally returns the
checkpoint UID, change count, and recovery flag from the public receipt.

The adapter calls exactly one matching `MemCommitClient` method. It imports no
command, TUI, Store, Grounding application, Grounding runtime, provider, or MCP
module. Public failures become bounded agent errors:

- invalid input and unavailable Context/analysis retain actionable public
  detail;
- provider failures are redacted and retryable;
- concurrent changes, storage failures, and incomplete execution are redacted
  and non-retryable; and
- unexpected adapter failures become a generic non-retryable internal error.

The registry performs its existing JSON-safety check after the adapter returns.
The MCP projection therefore exposes the same frozen schema through
`tools/list` and preserves the complete response through `tools/call`; it owns
no Grounding-specific handler.

## Invariants and limitations

- `start` requires an existing saved Atomize analysis and workbench. The tool
  does not silently run Atomize analysis or create a target issue.
- `open`, `keep`, and `apply` never connect to a semantic provider. `start` and
  `reply` use the public client's configured semantic provider.
- `keep` changes only the dialogue receipt. `apply` is the only action in this
  contract that may change Memories, and it retains the application's
  one-checkpoint and late-success recovery rules.
- The returned session `version` is observable but version 1 has no
  caller-supplied dialogue-version precondition because the public facade does
  not expose one yet. Existing binding and application freshness checks remain
  authoritative; transport-level retries and idempotency remain host concerns.
- The tool does not expose the TUI, synthesize approvals, start a saved Atomize
  analysis, or broaden Context authority.

## Verification

Focused tests exercise every kind, exact argument forwarding, complete JSON
projection, apply receipts, strict cross-kind rejection, retry classification,
error redaction, adapter import direction, registry discovery, and an MCP call.
The installed-wheel gate discovers the tool through the official MCP stdio
client outside the checkout and performs a real provider-free `open` against a
durable review-only dialogue. Source and installed checks therefore cover the
same `MCP → registry → adapter → public client → application` path without an
operation-specific MCP implementation.
