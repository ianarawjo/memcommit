# Makemore model responsibility boundaries

## Status

Makemore preserves its request, provider, proposal, quality, and serialized
analysis behavior while assigning generation responsibilities to five named
modules. Existing imports from
`memcommit.application.operations.makemore.model` remain compatible for the
public model surface and the two historical provider entry points.

## Motivating problem

The former `makemore/model.py` combined immutable Rule, Case, Target, and
Analysis values with semantic budgeting, provider schema construction, prompt
authoring, JSON decoding, Target grounding checks, strict Conformance/Fit
judgments, and the live provider call. Its name therefore concealed most of
the file's behavior, and changes to independent safety boundaries accumulated
inside one 1,535-line module.

Keeping every extracted function under a `model` package was rejected because
provider execution and semantic validation are not model concerns. A single
`quality.py` was also rejected: Target grounding validation prevents copying
or inventing ambient evidence, while strict Case validation asks whether a
generated collection Conforms to and Fits its complete Source frame. They
have different inputs, dependencies, and failure meaning.

## Physical ownership

- `model.py` owns modes, typed Target context, Rule and Case proposals, the
  `MakemoreAnalysis` digest, input normalization, and retained-analysis
  validation.
- `provider_contract.py` owns the exact output schema, whole-frame semantic
  execution budget, and fail-before-provider plan validation.
- `proposal_grounding_validation.py` owns Target reference decoding, referenced
  ambient Memory selection, and rejection of proposals that merely restate an
  existing Target Memory.
- `case_validation.py` owns the optional strict collection-wide Conformance and
  Fit gate for generated Cases.
- `generation.py` owns prompt construction, the bounded provider call, strict
  JSON decoding, proposal assembly, and composition of the two independent
  validation boundaries.

The implementation dependency points from `generation.py` toward the four
narrower owners. `case_validation.py` may depend on Target grounding only to
materialize the exact ambient Memories cited by generated Cases.
`application.py` imports generation and provider planning from their canonical
owners. `model.py` exposes those two historical names lazily for compatibility;
the compatibility path contains no execution behavior.

## Preserved invariants

- Makemore remains `WHOLE_FRAME_ONLY`; crossing any input, output, or strict
  validation bound fails before provider construction.
- Goal-to-Rules and Rules-to-Cases keep their exact positive proposal counts,
  provider contract version, prompt text, JSON schema, and deterministic
  proposal identities.
- Query-only Target rows remain name-only, Target aliases remain exact, and an
  ambient Target Memory cannot be republished as a new proposal.
- Best-effort Cases retain no strict-validation claim. Strict Cases publish
  only after the complete generated collection Conforms to every Source Rule
  and Fits the complete Source frame.
- Prepared analysis matching, Add authority, Target revalidation, and durable
  publication remain outside this refactor in their existing application and
  runtime owners.

## Verification

Ownership tests pin every extracted responsibility to its named module and
require the application layer to use the canonical generation and provider
contract imports. Existing Makemore regression tests cover both directions,
exact counts and repetition, Target grounding, strict success and failure,
prepared reuse, public adapters, Ground integration, and atomic Add behavior.
