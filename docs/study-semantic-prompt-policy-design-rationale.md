# Study semantic prompt policy design rationale

## Motivation

The Study provider route uses `gpt-5.6-sol` with reasoning effort `none`, but
`none` removes only the optional reasoning-effort request. It does not turn the
model into a literal input copier or remove the model's ordinary inference cost.
Large authored calibration corpora therefore still consume input and can still
change latency and behavior.

Atomize made that cost visible because one Task-sized turn already contains 50
Memories, the complete 1,225-pair quality matrix, rules, and a strict output
schema. On the retained 50-Memory `facility-updates` frame, the general prompt
projection was 117,589 characters. Omitting only authored examples reduced it
to 101,409 characters while preserving all 50 Memories and 1,225 pairs. This
measurement demonstrates the prompt-size effect, not by itself the cause of any
one provider timeout; provider service and inference variance remain possible.

The Study is intended to measure operation behavior over the participant's
task evidence. Replaying the same developer-written demonstrations on every
turn is both a substantial fixed cost and an additional experimental influence.

## Decision

Every Profile with stable `init-study` provenance, for both `PARTICIPANT` and
`GRANTED_MEMORY` roles, uses prompt policy `study-rules-only-v1`. Ordinary
authoring and managed Profiles use `general-authored-examples-v1`.

The Study projection omits developer-authored demonstrations from these live
semantic operations:

- Atomize classification plus Ambiguity and Conflict quality scans;
- Compare's compact summary;
- Distill and Elaborate's bidirectional reference families;
- semantic redundancy, Ambiguity, and Conflict finders;
- ordinary Query answer synthesis;
- Resolve generation and verification.

The same normative rules, schemas, complete user request, frozen Memory or
Trace evidence, relation pairs, authority checks, and output validation remain.
Evaluation campaigns retain their explicitly selected calibration corpora;
they are measurement tools rather than ordinary Study task turns.

“Authored examples” has a narrow meaning here. It does not include a person's
Ground or Fit Example Memories, Cases supplied as Distill input, Rules supplied
to Elaborate, a request asking for examples, or evidence whose content happens
to contain the word “example”. Those are user-owned semantic input and removing
them would change the task rather than reduce prompt scaffolding.

## Runtime and cache identity

`memcommit.semantic_prompt_policy` is the single resolver. It classifies the
active Profile from validated Study provenance, never from an editable display
name. Each rules-only Study prompt carries the small policy identifier and an
explicit `OMITTED` record so captured provider input remains auditable. The
general projection adds no policy record, preserving its prior provider input
while retaining all authored cases. Operation adapters project their authored
fixture at construction time; they do not build a full prompt and then strip
matching strings.

Atomize can transparently reuse a saved analysis or an exact Study prewarm in
place of a provider turn, so its reusable identity must include this policy.
Study analyses use session schema 6 and retain `study-rules-only-v1`; legacy
schemas imply the general full-example policy. Runtime reuse requires the
current policy to match. Exact prewarm schema 2 also includes the policy in its
artifact and key. Schema-1 full-example artifacts remain readable for migration
diagnostics but are skipped rather than installed or reopened in a rules-only
Study.

Rationale's optional inference cache already hashes the complete provider
prompt and output schema, so changing its policy projection produces a cache
miss without another cache schema. The other affected results are explicit
operation or review sessions, not hidden provider substitutes; reopening one
continues that user-visible saved work, while starting a new analysis constructs
the current policy prompt.

## Validation observation

On 2026-08-23, a read-only live call over the same 50-Memory
`facility-updates` frame used the active Study `gpt-5.6-sol` / `none` route and
completed in 58.15 seconds. Its receipt retained
`prompt_policy_id=study-rules-only-v1`, covered all 50 inputs, and returned 49
`ATOMIC` plus one `COMPOSITE` classification. This is one operational check,
not a latency distribution or a quality promotion result.

A normal `mem impact atomize --refresh` on a 17-Memory participant Task frame
completed in 29.29 wall-clock seconds and saved schema-6 analysis
`6b594a25…`. Reopening the same exact command without `--refresh` took 0.45
seconds and reported that the provider was not called. The stored analysis
retained `study-rules-only-v1`; this confirms the new policy can be cached and
reused, while the policy-mismatch test confirms a general full-example
analysis is replaced rather than reused in Study.

## Alternatives and limitations

Removing examples globally was rejected because ordinary Profiles may value
their calibrated boundary behavior and were outside this Study change. Removing
only examples from Atomize was rejected because the same repeated fixed cost
exists in other Study semantic turns. Deleting arbitrary text containing
“example” was rejected because that would corrupt user evidence and normative
instructions. Changing the provider or reasoning tier was rejected as a
different experimental condition; provider routing and prompt projection remain
separate policies.

Rules-only prompting may change output quality as well as latency. That is an
intentional Study condition and must be evaluated rather than assumed to be an
unqualified improvement. Atomize also remains dominated by its quadratic pair
matrix at Task scale: removing authored examples reduces but does not eliminate
the one-shot workload. This policy does not authorize hidden batching,
truncation, relaxed schemas, or partial publication.

Rationale provenance is intentionally outside this rollout while its retained-
history and gap projection is being revised separately. It continues to use
the general authored calibration contract until that work has its own complete
CLI, test, and cache boundary.
