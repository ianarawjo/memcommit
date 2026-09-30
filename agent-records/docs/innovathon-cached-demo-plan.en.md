# Innovathon Cached-Response Demo Plan

- Date: 2026-09-30
- Authorship: An agent-authored record of the direction established in the conversation.
- Scope: The `memcommit-innovathon` repository and its `innovathon` branch only.
- Status: **Planning only. This document does not implement cache replay, initialization changes, Sync, or integration with external programs.**
- This is a demonstration scenario plan, not a statement of implementation completion or operation-route review status.
- Translation of: [Korean plan](innovathon-cached-demo-plan.md).

## Purpose and decisions

Instead of allowing variable LLM responses to change the issues and edits shown during the demonstration, store prepared, finalized responses in a cache and replay them. The goal is a demo that feeds cached responses into the existing processing flow and performs actual Context changes, validation, persistence, Checkpoint creation, and Receipt output—not a mock that merely imitates screen output.

This plan does not assume that the cache already exists or that its contents have been collected from actual model calls. Populating the cache and finalizing its contents are future tasks. The behavior is limited to the Innovathon scenario; it is not a change to the default behavior of the distributed application.

For now, record the plan only. Decide the execution package, cache directory structure, and settings during implementation. The previously discussed adaptation of `init-study` for the demo also remains a future task.

## Demonstration sequence

```text
Obtain a Skill through an external program
↓
Sync into a Profile
↓
Merge with the existing Context
↓
Review two predetermined issues in the Resolve screen
↓
Choice or Intent → cached change plan matching that input
↓
Cached reinspection result → Preview · Apply → success
↓
Query → cached answer matching the state immediately after Merge
↓
Personalization Update → cached change plan → approval · save → success
↓
Query → cached answer matching the personalized state
↓
Verify the result
↓
Sync again
↓
Upload to the company's internal marketplace through an external program
```

Sync and marketplace integration are separate features to be implemented later. Their inclusion in this sequence does not mean they are currently available. Performing an actual external upload is outside the task of recording this plan.

## Cached responses to prepare

| Stage | Content to store and replay | Responsibilities retained by the existing implementation |
| --- | --- | --- |
| Initial Audit | Classifications, reasons, and supporting Memory links for two issues | Construct and validate Audit objects bound to the current Context |
| Resolve suggestions | Each issue's `proposed_direction` | Build choices, display the selection screen, and collect user input |
| Update planning within Resolve | Addition, edit, and removal plans corresponding to a Suggestion or a planned Intent | Validate the `UpdatePlan`, calculate the resulting changes, and render the diff |
| Reinspection | A fixed inspection response corresponding to the changed state | Determine whether another round is needed and account for the decision history |
| Query after Merge | Answer text and supporting evidence links for each claim | Construct and display citations and References |
| Personalization Update | A change plan corresponding to the personalization input | Approval, actual persistence, Checkpoint creation, and Receipt output |
| Query after personalization | An answer reflecting the personalized content, with evidence links | Construct and display citations and References |

Resolve distinguishes accepting a Suggestion (`CONFIRM`) from providing user input (`INTENT`). In both cases, it combines the accepted instruction with issue information and the original supporting text, then passes them to Update. The cache returns a change plan matching that input. Replay the same effects for the same input, without forcing different choices to produce the same changes. KEEP BOTH / KEEP AS IS retain their existing preservation semantics.

Fixing the reinspection response does not mean returning the initial issues repeatedly regardless of changes. Return a response appropriate to the planned resulting state. In the default demonstration, the planned decisions lead to Preview without any new issue requiring resolution. If a subsequent round is needed, prepare a separate state and response for it.

## Integration approach

1. Connect the response-returning boundaries of the providers used by Resolve, Update, and Audit, as well as the provider used by Query, to the demo cache. Query has a separate provider connection and must also be connected.
2. Preserve the existing response parsing and object construction flow wherever possible. Do not replace the final `ResolveProposal` or Receipt after it has been produced.
3. Fix the response content and effects in the cache, and bind them to the Context and Memory identifiers of the current input. Do not return another run's UIDs or digests unchanged.
4. Retain change-plan validation, agreement between the selected diff and the execution plan, input-change and authorization checks, and actual persistence.

The current candidate integration points are listed below. Recheck them when implementation begins.

- Merge → Resolve: `application/operations/merge/resolve_preparation.py`
- Audit acquisition: `application/operations/resolve/preparation.py`
- Resolution suggestion generation: `application/operations/resolve/resolution_options/generation.py`
- Update for each choice: `application/operations/resolve/choice_plans.py`
- Reinspection of the changed result: `application/operations/resolve/proposal.py`
- Shared Update planning: `application/operations/update/model/planning.py`
- Ordinary Query answers: `application/operations/query/ordinary_application.py`, `answer.py`

## Cache selection and repeated runs

- Select the corresponding response using the scenario, stage, current input content, choice or Intent, and question. Decide the exact cache-key format during implementation.
- Query distinguishes the post-Merge and personalized states by the current Context content, not by the number of calls. Repeating a question in the same state returns the same answer and evidence.
- The text shown to the user must agree with the actual saved result. Query evidence must link to Memories that exist at that point.
- Define the supported Intents and questions first. For an unplanned input, report that no cached response is available rather than returning an unrelated response or automatically falling back to a live LLM.
- Provide a way to restore the initial state and restart the demonstration during implementation. The intended direction is to use `init-study` to prepare only the OpenAI Docs demo material; the exact Context structure and initially selected Context remain to be decided.

## Waiting indicator

Add a demonstration delay of approximately 2–3 seconds to each visible preparation stage. Reuse the existing shared `. → .. → …` animation. This delay is intentional presentation time for cache replay, not actual LLM inference time.

Apply the delay per user-visible stage rather than accumulating duplicate waits for internal function calls. Do not regenerate an already prepared change plan when it is finally applied.

## Decisions remaining before implementation

- Initial and incoming Skill content, the two actual issues, each Suggestion, and the Intents to demonstrate.
- The exact effects of each choice and the corresponding reinspection responses.
- The personalization instruction, answers to the same question before and after personalization, and their evidence.
- Cache preparation and storage, input identification, initialization, and repeatable demonstration setup.
- Sync directions and conflict handling, and integration with the external program and marketplace.

After implementation, verify the initial inspection → choice/Intent → reinspection → save → Query → personalization → Query sequence in a real terminal. Also verify repeated replay for the same input, KEEP choices, cache misses, agreement between saved content and Query evidence, and completion without external LLM calls. This document does not claim that those checks have already been performed.
