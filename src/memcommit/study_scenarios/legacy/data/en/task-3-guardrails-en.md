# Task 3 General Selective-Sharing Guardrails

This document contains a complete synthetic set of 75 pre-review guardrails for
local outbound sharing candidates in Task 3's `sever` stage.
`local/guardrails` is an ordinary Context, separate from the connected healthcare
guidance agent's query-only material. While retaining the existing boundaries
for purpose, privacy, evidence, approval, and retention, it extends the review
scope to recipient authority, minimization, delivery channels, downstream use,
auditing, and recovery. The guardrails contain no User Model that presumes the
user's sharing preferences, because such assumptions could steer participant
choices and contaminate study behavior. World Models for external data-flow
conditions and Other Models for anticipated recipient or organization
interpretations fill those positions instead. `mem sever` now accepts one
ordinary Criteria Context per pass; these guardrails can fill that role or be
combined with another authorized criterion through `mem meld` first.

Each `directory/NN` denotes a hierarchical Memory location under `local/guardrails`.
The two-letter purpose ticker in brackets is an authoring and review sidecar, not
part of the Memory content. Only the sentence following the ticker is a Memory
candidate. `PP` states an action the agent should take in the imperative. `KB`
is verified sharing or security knowledge; `SM` describes the local agent's
role, capabilities, and observation limits; `OM` models what a recipient, third
party, or operator expects or judges, or how one may respond; and `WM` describes
states and constraints of media, copies, time, and institutional environments
that are independent of minds. The purpose distribution is KB 8, PP 47, SM 4,
UM 0, WM 5, and OM 11.

Memory content is maintained in the Context JSON files below. This document retains the data contract and a navigation index.

- [`local/guardrails/purpose-and-scope`](../native/task-3/task-3/en/local/guardrails/purpose-and-scope/context.json)
- [`local/guardrails/privacy-and-others`](../native/task-3/task-3/en/local/guardrails/privacy-and-others/context.json)
- [`local/guardrails/evidence-and-uncertainty`](../native/task-3/task-3/en/local/guardrails/evidence-and-uncertainty/context.json)
- [`local/guardrails/approval-and-delivery`](../native/task-3/task-3/en/local/guardrails/approval-and-delivery/context.json)
- [`local/guardrails/retention-and-revocation`](../native/task-3/task-3/en/local/guardrails/retention-and-revocation/context.json)
- [`local/guardrails/recipient-and-authority`](../native/task-3/task-3/en/local/guardrails/recipient-and-authority/context.json)
- [`local/guardrails/minimization-and-redaction`](../native/task-3/task-3/en/local/guardrails/minimization-and-redaction/context.json)
- [`local/guardrails/channel-and-format`](../native/task-3/task-3/en/local/guardrails/channel-and-format/context.json)
- [`local/guardrails/downstream-use`](../native/task-3/task-3/en/local/guardrails/downstream-use/context.json)
- [`local/guardrails/audit-and-recovery`](../native/task-3/task-3/en/local/guardrails/audit-and-recovery/context.json)
