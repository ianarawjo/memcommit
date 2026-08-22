# Semantic provider policy design rationale

## Motivation

Provider settings previously had one user configuration file but several
independent effective-policy sites. Most operations inherited
`~/.mem/config.json`; Find, Query, Help, and Forget pinned different Codex
models or reasoning efforts; Compare and Meld raised a timeout by mutating a
connected provider; Study prewarm compatibility rebuilt provider identity from
`Config`; and some Study generation scripts defaulted silently to `medium`
reasoning. Reading the configuration file alone could not answer which policy
an operation would actually use.

## One resolution plane

`memcommit.infrastructure.providers.policy` is now the sole authored source
for effective provider identity. It resolves provider ID, model, Codex
reasoning effort, transport timeout, policy source, mode, version, and digest.

`Config` remains the sole persisted user-default store. Operation rules are
version-controlled code because they are evaluated product constraints, not
personal preferences. Unknown or ordinary operations explicitly inherit the
global default through the same resolver; the shared
`connect_semantic_provider()` path now resolves `semantic_default` instead of
opening `Config` independently.

The current exceptions are:

| Operation | Effective exception |
| --- | --- |
| Find (`search`) | Codex `gpt-5.6-terra`, reasoning `low` |
| Query (`query`) | Codex `gpt-5.6-sol`, reasoning `none` |
| Help (`help`) | Codex `gpt-5.6-sol`, reasoning `none` |
| Forget (`forget`) | Codex `gpt-5.6-sol`, reasoning `none` |
| deep Compare (`compare_contexts`) | inherited identity, timeout at least 900 seconds |
| Meld (`meld_contexts`) | inherited identity, timeout at least 900 seconds |

All other production operations, including lightweight Compare, Summarize,
Rationale, Atomize, Update, Sever, Distill, Elaborate, Resolve, Translate, and
semantic quality reports, inherit the configured provider and model. For
Codex, an omitted configured reasoning effort resolves explicitly to `none`.
This is a reproducible latency baseline, not a claim that higher reasoning is
never useful; an evaluated operation pin or explicit evaluation campaign may
select another tier.

`mem provider status --operation OPERATION` prints the complete effective
policy without contacting a provider. `--study` resolves the participant-Study
mode and exposes its policy digest. The ordinary `mem provider status` output
continues to show the stored global defaults.

## Production, participant Study, and evaluation

Production and `STUDY_PARTICIPANT` use identical effective provider, model,
reasoning, and timeout values. Study prewarm identity checks for Compare,
Summarize, Atomize, Update, Sever, and directional Meld now call the resolver
with their real provider operation names. A prepared artifact therefore cannot
silently use a different default than the participant-facing operation whose
latency it is intended to remove.

`EVALUATION` is the only mode that accepts a process-local override. An
override never writes global configuration. The shared semantic-eval connector
and Study artifact generation utilities resolve their explicit provider,
model, reasoning, and timeout through this mode and record the resulting
identity in their existing campaign or artifact receipts. Former implicit
`medium` defaults were removed; omitting the flag now inherits the central
Codex baseline.

The policy digest includes the operation, mode, effective values, source, and
policy version. Production and participant Study have different mode labels
but must resolve the same execution identity; artifacts continue to key on the
provider/model/reasoning tuple required by their existing schemas.

## Connection and timeout boundary

`connect_operation_provider()` consumes one resolved policy and is the common
provider-neutral connector for new operation adapters. It records connection
events under the semantic operation and returns the immutable policy receipt
beside the provider. Existing compatibility-named command factories remain in
place for test and API stability, but their authored pin or inherited default
now resolves centrally.

Timeout remains an independent policy axis. Raising the deep Compare/Meld
transport window does not raise semantic input budgets or authorize prompt
splitting. Lightweight Compare inherits the ordinary configured timeout
because it does not promise exhaustive ledger completion.

## Alternatives and limitations

Moving every exception into `~/.mem/config.json` was rejected because it would
turn tested operation contracts into hidden machine-local state. Making one
global model mandatory for every operation was rejected because the measured
Find and Query policies deliberately optimize different tasks. Inferring
reasoning effort from model names was rejected because model selection and
reasoning are independent, observable policy axes.

This policy layer does not choose semantic execution strategy, prompt size,
schema, retry, or batching. Those remain operation contracts under
`memcommit.semantic_execution`. Historical standalone research scripts outside
the participant Study setup may retain their explicit benchmark flags; they
are evaluation artifacts rather than production or participant runtime.
