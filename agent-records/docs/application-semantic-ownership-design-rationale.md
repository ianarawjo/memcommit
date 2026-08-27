# Application semantic ownership

## Decision

The shared semantic package is owned by `memcommit.application.semantic`.
This relocation keeps its existing classification pipelines, provider-facing
contracts, shared semantic values, prompt policy, and legacy helpers together
while preserving behavior.

## Motivation

The former top-level `memcommit.semantic` package was not an independent
architectural layer. Its main consumers are application operations and their
adapters, and several of its modules already depend on application execution,
review, Profile policy, persistence, or provider contracts. Its present center
is therefore shared application behavior rather than a dependency-free domain
model or an external provider adapter.

Moving the package intact establishes that coarse ownership before assigning
every mixed module a narrower home. This keeps the structural change separate
from changes to prompt, decoding, classification, authority, and persistence
behavior.

## Compatibility boundary

Internal callers, tests, evaluation tooling, study prewarms, and generated
legacy-module targets use `memcommit.application.semantic` directly. There is
no `memcommit.semantic` compatibility package: retaining a second package path
would obscure the selected owner and there is no required external consumer
for the old path.

## Deferred decomposition

This move intentionally leaves internal responsibilities unchanged. A later
review may move the concrete `llm.py` client toward providers and may extract
dependency-free values such as understanding or Goal-focus models into core.
Those moves should happen only after their imports and public contracts are
reviewed independently; they are not inferred merely from filename or type
shape here.
