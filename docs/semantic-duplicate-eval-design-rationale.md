# Provider-neutral duplicate relation evaluation

## Decision

Duplicate evaluation is the second bounded semantic operation in the shared
campaign harness. It classifies one reviewed two-Memory pair at a time under
six relations:

- `EXACT`;
- `SURFACE_EQUIVALENT`;
- `SEMANTIC_EQUIVALENT`;
- `OVERLAP`;
- `UNKNOWN`; and
- `DISTINCT`.

The operation deliberately does not ask a model to rediscover deterministic
relations. Byte-identical content is `EXACT`. The production finder's
conservative NFC, line-ending, outer-space, and horizontal-space comparison
key decides `SURFACE_EQUIVALENT`. These two stages make no provider call.

Only the remaining four relations reach the configured semantic provider.
This host-first split is a semantic invariant and a cost boundary, not a prompt
optimization: a provider cannot override a deterministic exact or surface
result.

## Semantic stage contract

The semantic stage receives one scenario, exactly two UID/content Memories,
and reviewed leave-one-out calibration examples. The held target's expected
relation and rationale are projected out. Mechanical `EXACT` and
`SURFACE_EQUIVALENT` examples are also excluded because those labels are not
available to the provider stage.

The strict output schema contains only one relation:

```json
{"relation":"SEMANTIC_EQUIVALENT|OVERLAP|UNKNOWN|DISTINCT"}
```

`SEMANTIC_EQUIVALENT` requires mutual substitution without losing scope or
operational effect. `OVERLAP` preserves at least one unique claim.
`UNKNOWN` is reserved for an unresolved ordinary referent or scope choice that
changes equivalence; it is not model confidence. `DISTINCT` means the claims
remain independently revisable or govern different predicates.

The parser rejects prose, fences, duplicate keys, missing or extra fields, and
unknown relations. Provider failure is retained as failure; there is no Sol,
OpenRouter, or secondary-model repair.

## Campaign and timing

`mem eval semantic run duplicate` uses the same atomic per-attempt ledger and
repetition gate as ambiguity evaluation. The scoreboard separates
`find-duplicates` from `find-ambiguities` by operation, corpus digest, pipeline,
provider/model identity, reasoning/thinking mode, and repetition count.

Timing is reported for all attempts and separately by execution stage:

- `HOST_EXACT`;
- `HOST_SURFACE_EQUIVALENT`; and
- `SEMANTIC_RELATION`.

The overall mean intentionally includes the near-zero host decisions. The
stage mean shows the provider cost without pretending every relation needed a
completion.

## Observed calibration baseline on 2026-08-03

The current `duplicates.json` fixture has one case for each relation. It is a
small reviewed leave-one-out calibration set, not an independent holdout.

| Provider condition | Repetitions | Case gate | Exact attempts | Semantic-stage mean/p95 | Total elapsed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6 35B-a3b, thinking `off` | 3 | 6/6 | 18/18 | 1.185/9.062 s | 14.268 s |
| Luna-low | 3 | 6/6 | 18/18 | 3.622/5.676 s | 43.542 s |
| Sol, high reasoning | 1 | 6/6 | 6/6 | 4.027/5.254 s | 16.173 s |

For each three-repetition campaign, 6 of 18 attempts were host-only and 12
called the provider. Qwen's first semantic completion took 9.062 seconds; its
later semantic completions were mostly below one second. The ledger keeps that
cold-start maximum rather than smoothing it away.

These results establish that the decomposed schema is executable by Luna and
the local Qwen condition on the current calibration. They do not establish
pair-discovery coverage, grouping of more than two Memories, or independent
generalization.

## Boundaries and next step

- This campaign scores a supplied pair. It does not enumerate or retrieve
  candidate pairs from a large Context.
- Production duplicate grouping still owns representative selection,
  disjoint-group validation, ordering, and projection into `DuplicateReport`.
- `OVERLAP`, `UNKNOWN`, and `DISTINCT` are evaluation relations. The current
  production finder returns only positive duplicate findings.
- Raw responses are retained only because the fixture is public repository
  calibration text. A user-data campaign needs a different retention policy.
- The six cases are too small to select a production default by themselves.

Before changing the duplicate prompt from observed errors, the next step is a
separately reviewed and digest-locked duplicate holdout. It should include
scope changes, modality and exception differences, asymmetric entailment,
multilingual paraphrase, formatting near-misses, and adversarial instructions
inside Memory content. A pipeline revised after seeing that holdout requires a
new untouched holdout for another generalization claim.
