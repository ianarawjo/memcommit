# Task 3 Healthcare Information-Sharing Guidance Specification

This document contains a complete synthetic set of 75 Memories explaining
consequences that may follow when, in Task 3, a user sends information from
local personal Memories to a government healthcare institution system. This
Context's role is to explain that transmitted information is treated as
consented sharing, along with possible institutional use and retention,
provision to relevant third parties for healthcare purposes, and use for
service improvement. It contains no instructions for the healthcare Q&A
agent to select, include, exclude, edit, transmit, or delete information; judge
the currency or accuracy of personal Memories; or perform another service.

The canonical Context locator is
`remote/government/healthcare-agent/info-request/questions-and-answers`. The query-only designation is
an interaction boundary of the research prototype, not actual authentication or
operational security. Local `local/guardrails` constrain whether sharing actually
occurs; this request does not decide what the user must share. This Context has
no User Model so that it does not presume user preferences.

The healthcare Q&A agent in this Context does not ask for information or
prepare a transmission copy. It explains only what happens when a user actually
sends information through the government healthcare institution system's
transmission screen. All information actually sent is treated as one submitted
unit for which sharing was consented, and depending on the type of information,
it may be provided to relevant third parties for healthcare purposes or used
for service improvement. This specification does not identify the exact
services, recipients, or scope of third parties. A submission without separate
proxy-submission requirements verified by the institution is treated as having
been made directly by the account user, but the healthcare Q&A agent itself
does not verify identity or proxy authority. This agent cannot inspect stored
personal Memories or institution records and has no authority to retain any
information outside the current conversation record. It also cannot select,
modify, transmit, or delete information; inspect or control the institution's
receipt, retention, internal sharing, or deletion; or inspect or alter access
permissions. Scheduling, payment, and contacting actions are also outside this
agent's authority.

Each `directory/NN` denotes a hierarchical Memory location beneath the canonical
Context. The two-letter purpose ticker in brackets is an authoring and review
sidecar, not part of the Memory content. Only the sentence following the ticker
is a Memory candidate. `KB` is direct knowledge about sharing categories and
transmission boundaries; `PP` is an imperative action the healthcare Q&A
agent should follow; `SM` describes the healthcare Q&A agent's capabilities
and observation limits; `OM` models what external requesters, external tools,
and automated agents that directly call this endpoint may expect or what request
strategies they may use; and `WM` describes states and constraints of service,
transmission, and facility environments that are independent of minds. The
purpose distribution is KB 5, PP 42, SM 8, UM 0, WM 7, and OM 13.

The healthcare Q&A agent in this set has no authority to interact with
downstream actors inside the government institution or to observe or control
their decisions. Accordingly, `OM` is not used to speculate about interpretations
by invisible downstream actors. It models only the expectations and behavior of
separate actors that can actually send requests to this endpoint, such as
misrouted external agents, automated API clients, and requesters attempting
repeated or excessive collection. This distinction retains realistic failures
such as misrouting, prompt injection, and probing response boundaries without
inventing actors that cannot interact directly merely to meet a quota.

This specification is a boundary table that explains transmission consequences,
not an authority matrix that enforces which information is allowed or excluded.
Review criteria are whether it treats all information actually sent as consented
sharing, discloses possible provision to relevant third parties for healthcare
purposes and use for service improvement, states that the exact services and
recipient scope vary with the information type, and treats out-of-purpose tasks
as outside information-sharing guidance. Here, a `third party` is an external
person or organization, other than the user and the initial recipient government
healthcare institution, that may receive information to provide healthcare
support or processing related to the information supplied. Internal personnel
at the same institution do not count as third parties in this synthetic fixture.
This is not a definition under real law.

The healthcare Q&A agent does not select, include, exclude, modify,
transmit, or delete a transmission copy. Merely mentioning information in the
current conversation does not submit it to the institution; only all content
actually sent through the government healthcare institution system's
transmission screen constitutes the consent unit. Mentioning personal Memory
content in this conversation neither transmits it to the institution nor
physically deletes it. This boundary is not a universal legal claim; it is the
purpose, authority, and responsibility boundary of this synthetic agent.

Because this agent cannot see stored personal Memories, a malicious request
exfiltrating source personal Memory text from this agent is outside this
fixture's threat model. Realistic attack surfaces are bulk or varied API calls
that resemble normal requests, distillation that collects response rules and
refusal boundaries, prompt injection, and endpoint resource exhaustion. Because
the current query provider is one-shot, in a serious attack the only termination
behavior it can guarantee is to end processing without generating further
responses to that request. This fixture does not assume that blocking recalls,
rate limiting, or user bans are implemented. Separately, convenience
preferences, temporary states, persistent functional limitations, and required
accessibility support are different kinds of information. The institution may
verify them, but this agent does not determine or verify them.

Memory content is maintained in the Context JSON files below. This document retains the data contract and a navigation index.

- [`remote/government/healthcare-agent/info-request/questions-and-answers/request-manifest`](../native/task-3/task-3-healthcare-authority/en/remote/government/healthcare-agent/info-request/questions-and-answers/request-manifest/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/care-access`](../native/task-3/task-3-healthcare-authority/en/remote/government/healthcare-agent/info-request/questions-and-answers/care-access/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/scheduling-and-continuity`](../native/task-3/task-3-healthcare-authority/en/remote/government/healthcare-agent/info-request/questions-and-answers/scheduling-and-continuity/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/hospital-stays`](../native/task-3/task-3-healthcare-authority/en/remote/government/healthcare-agent/info-request/questions-and-answers/hospital-stays/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/communication-and-explanations`](../native/task-3/task-3-healthcare-authority/en/remote/government/healthcare-agent/info-request/questions-and-answers/communication-and-explanations/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/memory-use-and-boundaries`](../native/task-3/task-3-healthcare-authority/en/remote/government/healthcare-agent/info-request/questions-and-answers/memory-use-and-boundaries/context.json)
