# Task 3 Participant Brief Draft

## Task

You may send information to a government healthcare institution system to
personalize healthcare support. The information-request agent explains only
general information categories and the consent, use, and sharing consequences
that follow an actual transmission. It does not access stored personal Memories
or institution records; select, include, exclude, or modify items for
transmission; prepare a transmission copy; or send one directly. The personal
Memories include specific events involving meals, mobility, scheduling, family,
and daily-life management, as well as preferences derived from multiple events
and personal rules that the local agent has followed.

Consult `government/healthcare-agent/information-request` to understand the
general information categories and the consequences of transmission. Then, in a
local review process separate from the information-request agent, decide what
information from `personal-memory` to send. For each candidate, the participant
decides—based on its necessity and sensitivity—whether to send the specific
event as written, send a summary or preference or policy that preserves its
conditions, or not send it. All content actually sent through the government
healthcare institution system's transmission screen is treated as one unit of
consent to share.

## Starting State

- `personal-memory`: 300 de-identified, synthetic personal Memories
- `guardrails`: pre-review policies automatically applied to local outbound
  sharing
- `government/healthcare-agent/information-request`: 75 query-only information-
  sharing guidance Memories

`information-request` explains general information categories that may help
healthcare support and what can happen after an actual transmission. Depending
on the type of information, transmitted information may be provided to relevant
third parties for healthcare purposes or used for service improvement. The
exact services, recipients, and scope of third parties vary by information type,
and the information-request agent cannot identify them.

This agent does not directly request information or prepare transmission
candidates. It does not access stored personal Memories or institution records,
and it has no authority to select, include, exclude, modify, transmit, or delete
any Memory. Mentioning information in the conversation is not a submission to
the institution, and the agent does not retain information outside the current
conversation record. Even if prior medication instructions, care visits, or
mobility experiences are presented in the conversation, it neither verifies
their currency or accuracy nor turns them into institution records, and it
cannot physically delete or transmit them. The government healthcare
institution system is responsible for actual receipt, retention, internal
sharing, and downstream processing. Assume that `guardrails` has already been
reviewed for this synthetic scenario; participants do not need to modify or
evaluate it.

## Expected Flow

1. Consult the query-only information-sharing guidance to understand the general
   information categories and the consequences of actual transmission.
2. Find relevant candidates and their conditions in `personal-memory`.
3. Use the local tool
   `mem sever --to government/healthcare-agent/information-request --save ...`
   to create sharing candidates and local rationale. The information-request
   agent does not run this command or select candidates.
4. Review the candidates and, when needed, use `mem rationale` and source traces
   to check the basis and omitted conditions for events, summaries, and policies.
5. Send the finally reviewed items to the government healthcare institution's
   receiving system with `mem share --to government/healthcare-agent`. This
   locator identifies the institution recipient in the research fixture, not
   the information-request agent's repository. All content actually sent is
   treated as one unit of consent to share.

Unshared source text and local rationale remain local. Before actual
transmission, the local `guardrails` and the participant determine the candidate
scope; the information-request agent does not take part. Merely stating
information during a query does not send it to the institution. Conversely,
after content is actually sent through the institution's transmission screen,
all of it is a consented sharing unit, and depending on the information type it
may be provided to relevant third parties for healthcare purposes or used for
service improvement. The information-request agent cannot identify the exact
services or recipient scope.
