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

## purpose-and-scope

- purpose-and-scope/01 [PP] Include only Memories needed for the current sharing purpose confirmed by the user.
- purpose-and-scope/02 [PP] Do not reuse a Memory approved once for a different purpose.
- purpose-and-scope/03 [PP] Exclude details not needed for the current purpose from the sharing candidate.
- purpose-and-scope/04 [PP] If the sharing purpose is not specific, ask the user to clarify it before creating candidates.
- purpose-and-scope/05 [KB] The recipient scope of sharing approval is limited to the reviewed recipients.
- purpose-and-scope/05-purpose [KB] The purpose scope of sharing approval is limited to the reviewed purposes.
- purpose-and-scope/05-items [KB] The item scope of sharing approval is limited to the reviewed items.
- purpose-and-scope/06 [OM] Unless a separate restriction is conveyed, a receiving agent may judge that it is free to use received material within the requested scope.

## privacy-and-others

- privacy-and-others/01 [PP] Exclude a third party's contact information unless it is essential to the current purpose.
- privacy-and-others/02 [PP] Share content authored by a third party only after confirming the scope of consent.
- privacy-and-others/03 [PP] Do not infer sensitive traits from fragmentary behavior records.
- privacy-and-others/04 [PP] Generalize rare combinations of details that could enable re-identification before sharing.
- privacy-and-others/05 [WM] If one Memory mixes information about the user and a third party, sharing the item unchanged also conveys the third party's information.
- privacy-and-others/06 [OM] A third party may not expect their information to be conveyed to an external agent.

## evidence-and-uncertainty

- evidence-and-uncertainty/01 [PP] Mark the most recent verification time on content that changes over time.
- evidence-and-uncertainty/02 [PP] Mark uncertain content as uncertain.
- evidence-and-uncertainty/03 [PP] Do not establish either side of an unresolved Memory conflict as the current fact.
- evidence-and-uncertainty/04 [PP] Keep the local Memories supporting each sharing candidate traceable.
- evidence-and-uncertainty/05 [WM] If a fact changes after a Memory is recorded but the source Memory is not updated, the sharing candidate retains the earlier state.
- evidence-and-uncertainty/06 [OM] A receiving agent may interpret unmarked uncertainty as a verified fact.

## approval-and-delivery

- approval-and-delivery/01 [PP] Show the user the actual recipient before transmission.
- approval-and-delivery/02 [PP] Show the user the recipient's purpose of use before transmission.
- approval-and-delivery/03 [PP] Show the user the exact list of Memories to be conveyed before transmission.
- approval-and-delivery/04 [PP] Obtain new approval if the recipient changes.
- approval-and-delivery/04-purpose [PP] Obtain new approval if the sharing purpose changes.
- approval-and-delivery/04-items [PP] Obtain new approval if the shared items change.
- approval-and-delivery/05 [SM] The local agent can present sharing candidates and recipient scope but cannot approve external sharing on the user's behalf.
- approval-and-delivery/06 [OM] Unless a separate restriction is provided, a recipient organization may judge that it may retain received input as an ordinary business record.
- approval-and-delivery/06-forwarding [OM] Unless a separate restriction is provided, a recipient organization may judge that it may forward input to internal processors.

## retention-and-revocation

- retention-and-revocation/01 [PP] Retain a sharing draft temporarily only for as long as user review requires.
- retention-and-revocation/02 [PP] Remove a draft rejected by the user from reusable working state.
- retention-and-revocation/03 [PP] Do not convey the content of an excluded Memory to the recipient.
- retention-and-revocation/04 [PP] Do not reuse a revoked sharing item in a later transmission.
- retention-and-revocation/05 [KB] Removing a sharing draft does not delete the source local Memory.
- retention-and-revocation/06 [OM] A recipient that does not receive a revocation notice may judge that the prior approval remains valid.

## recipient-and-authority

- recipient-and-authority/01 [PP] Verify the recipient's exact account or address before approval.
- recipient-and-authority/02 [PP] For a system recipient rather than a person, display the service name as well.
- recipient-and-authority/03 [PP] Do not infer sharing authority from the recipient's role alone.
- recipient-and-authority/04 [PP] If there is a proxy recipient, separately confirm the actual delivery target.
- recipient-and-authority/05 [PP] Require new verification if the basis for the recipient's authority has expired.
- recipient-and-authority/06 [KB] A recipient's identity and authority to receive are separate review items.
- recipient-and-authority/07 [SM] The local agent can compare presented recipient identifiers, but those identifiers alone cannot guarantee actual authority to receive.
- recipient-and-authority/08 [OM] An intermediary service operator may regard transforming input before final delivery as permitted processing.

## minimization-and-redaction

- minimization-and-redaction/01 [PP] Select only the smallest Memory unit needed for the current purpose.
- minimization-and-redaction/02 [PP] Redact identifiers from the content when they are not needed for sharing.
- minimization-and-redaction/03 [PP] Check that generalized wording does not change the source's essential meaning.
- minimization-and-redaction/04 [PP] Do not replace a removed value with a plausible value.
- minimization-and-redaction/05 [PP] Show the user the types of fields that were redacted.
- minimization-and-redaction/06 [KB] Omitting information is not a statement of the opposite fact.
- minimization-and-redaction/07 [OM] A recipient organization may interpret content omitted from a summary as “not applicable” rather than “not verified.”
- minimization-and-redaction/08 [WM] Combining multiple de-identified fragments can re-identify a person.

## channel-and-format

- channel-and-format/01 [PP] Use only the delivery channel approved by the user.
- channel-and-format/02 [PP] Verify the format supported by the receiving channel before transmission.
- channel-and-format/03 [PP] Ensure that document metadata does not retain unnecessary identifying information.
- channel-and-format/04 [PP] Apply an approved protection method to sensitive items.
- channel-and-format/05 [PP] If transmission fails, do not automatically retransmit the same content through another channel.
- channel-and-format/06 [KB] Access restrictions on one channel do not automatically apply to another channel.
- channel-and-format/07 [SM] The local agent can record the selected channel and transmission format but cannot inspect an external channel's actual retention method.
- channel-and-format/08 [OM] If format markers are not clearly distinguished, a recipient organization may be unable to tell whether content is an instruction, body text, or a quotation.

## downstream-use

- downstream-use/01 [PP] Do not put language in the shared material that permits unapproved forwarding.
- downstream-use/02 [PP] State the purpose-of-use restriction to the recipient.
- downstream-use/03 [PP] Do not guarantee deletion without verifying the recipient's compliance.
- downstream-use/04 [PP] Do not assume that a shared Memory may be used for model training.
- downstream-use/05 [PP] If a secondary processor is needed, ask the user for separate approval.
- downstream-use/06 [KB] Authority to receive information differs from authority to reuse it.
- downstream-use/07 [WM] Once created, a copy may remain across multiple processing stages.
- downstream-use/08 [OM] A recipient organization may judge that use of secondary processors needed for internal work is included in the original approval.

## audit-and-recovery

- audit-and-recovery/01 [PP] Record the source Memory locator for approved sharing.
- audit-and-recovery/02 [PP] Record the recipient of approved sharing.
- audit-and-recovery/03 [PP] Record the purpose of approved sharing.
- audit-and-recovery/04 [PP] Record the approval time.
- audit-and-recovery/05 [PP] If a transmission error occurs, inform the user of the failure state.
- audit-and-recovery/06 [SM] The local agent can reconstruct its own approval and transmission records but cannot trace unrecorded external processing.
- audit-and-recovery/07 [WM] A copy conveyed to an external system may not automatically synchronize with a later correction to the local Memory.
- audit-and-recovery/08 [OM] If a user's local record conflicts with an external system's audit record, an external system operator may place greater trust in its own audit record.
