# Tested `mem atomize` grounding screens

## Purpose

These captures make the implemented conversation inspectable as a complete
user-visible flow rather than only as a collection of substring assertions. A
deterministic semantic-provider fixture drives the same public CLI entry
points used by the application. The regression test compares every rendered
line with these files after replacing volatile UUID prefixes with named
placeholders.

The captured path is:

```text
saved workbench
→ initial clarification
→ required consequential follow-up
→ provider-free resume
→ corrective answer
→ exact ready proposal
→ provider-free ready resume
→ explicit acceptance
→ one applied checkpoint
```

## Captures

| Step | Durable state | Screen | Contract demonstrated |
| --- | --- | --- | --- |
| 0 | workbench | [`00-workbench.txt`](examples/mem-atomize-grounding-screens/00-workbench.txt) | The reviewer sees issue order, short readings, the exact source, and a unified response field before opening a dialogue. |
| 1 | `AWAITING_REPLY` | [`01-evaluate-awaiting-reply.txt`](examples/mem-atomize-grounding-screens/01-evaluate-awaiting-reply.txt) | The agent restates what it understood, resolves the selected issue provisionally, exposes a downstream scope question, and blocks the proposed edit without changing Memory. |
| 2 | `AWAITING_REPLY` | [`02-provider-free-resume.txt`](examples/mem-atomize-grounding-screens/02-provider-free-resume.txt) | Reopening the dialogue renders the identical saved understanding without another provider call. |
| 3 | `READY_TO_APPLY` | [`03-reply-ready-to-apply.txt`](examples/mem-atomize-grounding-screens/03-reply-ready-to-apply.txt) | A corrective reply remains visible as a second turn, answers the follow-up, recomputes the shared understanding, and exposes two exact edits while Memory is still unchanged. |
| 4 | `READY_TO_APPLY` | [`04-provider-free-ready-resume.txt`](examples/mem-atomize-grounding-screens/04-provider-free-ready-resume.txt) | The accepted shared interpretation and exact pending proposal remain stable across remote or later resumption. |
| 5 | `APPLIED` | [`05-applied.txt`](examples/mem-atomize-grounding-screens/05-applied.txt) | Explicit acceptance applies the exact proposal in one checkpoint and labels the terminal screen as applied rather than provisional. |

The scripted provider is intentional. A live semantic call would make a UI
golden nondeterministic and could confuse semantic-model variation with a
rendering regression. Provider parsing, cumulative turn payloads, stale-input
checks, mutation boundaries, and the live Task 1 path are tested separately.

## Normalization

Values that are random by design are normalized:

```text
<ANALYSIS>
<SESSION>
<STUDENT>
<STAFF>
<CHECKPOINT>
```

CRLF is normalized to LF, and invisible line-ending whitespace produced by
the prompt widget is removed. No visible content is otherwise normalized.
Issue identities, comments, readings, follow-up text, proposal text, state
labels, command guidance, and mutation disclosures remain exact. This makes a
changed conversational role or misleading terminal label fail the regression
test while avoiding failures caused only by a new UUID.

The capture contract lives in
`test_cli_grounding_dialogue_resumes_then_applies_once_with_provenance`.
That test also verifies provider call counts, unchanged pre-accept Context
bytes and checkpoint counts, the final two Memory edits, one new checkpoint,
and recorded trace/rationale evidence.
