# Granted derivative ownership and multi-party consent

## Motivating scenario

A participant may compare two advisor grants, use campus-wiki material in a
participant draft, or apply one granted source into another authority-owned
Context. `READ` alone does not answer who may create the intermediate work,
whether sources may be mixed, whether a result may leave its source domain, or
who may keep the resulting analysis. Those are independent research and
ownership decisions.

## Capability contract

The grant vocabulary separates six derived-work decisions from ordinary
content mutation:

| Capability | Authority decision |
|---|---|
| `DERIVE` | The granted source may influence a new result. |
| `COMBINE` | The source may be analyzed with a different provenance or ownership domain. |
| `EXPORT` | A derived result may leave this exact granted resource. |
| `ACCEPT_DERIVED` | This authority-owned target may receive derived material from another domain. |
| `SAVE_BOUND_ANALYSIS` | A saved artifact remains usable only while its exact grants remain available. |
| `SAVE_ANALYSIS` | The grantee may permanently retain an analysis or intermediate artifact derived from the source. |

`QUERY` permits one provider-mediated result. It does not imply general
derivative, analysis, or transcript retention.

Permission dependencies fail closed. `DERIVE` and `ACCEPT_DERIVED` require
`READ`; `COMBINE`, `EXPORT`, `SAVE_BOUND_ANALYSIS`, and `SAVE_ANALYSIS`
require `DERIVE`; and
`ACCEPT_DERIVED` also requires at least one target mutation capability.

## Transfer and combination invariants

- A granted source used inside its exact grant resource requires `DERIVE`.
- Moving a result outside that resource additionally requires source `EXPORT`.
- Writing into a different granted target additionally requires target
  `ACCEPT_DERIVED` and the actual CREATE, UPDATE, or DELETE effects.
- Combining different domains requires `DERIVE + COMBINE` from every granted
  contributor. One permissive authority cannot waive another authority's
  restriction.
- A grant-bound analysis requires `DERIVE + SAVE_BOUND_ANALYSIS` from every
  granted contributor. A retained analysis requires `DERIVE + SAVE_ANALYSIS`
  from every contributor. Mixed sources use the weakest common mode: retained,
  then grant-bound, then not saved.

These checks are an intersection of all contributors' permissions. The number
of parties does not change the rule: every source must consent to derivation
and combination; every exporting source must consent to export; and the one
written target must consent to receipt and concrete mutation effects.

## Retained values and live relationships

Direct Copy and immutable Memory Reference are retained value transfers. An
exact granted Memory used by either operation requires the complete
`READ + DERIVE + EXPORT + SAVE_ANALYSIS` set; a Copy batch spanning ownership or
provenance domains also requires `COMBINE` from every granted contributor.
Apply freezes the exact Grant and authority Memory binding and holds its locks
through the local Target commit. A successful Copy becomes a fresh editable
local Memory, while a successful Reference remains an immutable local
snapshot. Both retain their creation-time authority provenance and remain
usable after later revocation because permanent retention was explicitly
authorized.

Context or Memory Embed is different. It requires `READ + EMBED`, stores no
authority content, and reauthorizes the exact Grant and Source binding on every
recursive load. Revocation therefore closes the live projection while leaving
the opaque relationship available for explicit repair or removal. `EMBED`
never implies derivation, export, or retention: a later Copy or Reference must
return to the underlying granted Source and independently satisfy its complete
retained-value permission contract.

Placing that live edge in a local Context does not make the local Context its
authority owner. Until a semantic operation can propagate each embedded
`GrantedMemorySource` or `GrantedContextLink` into its complete contributor set
and authorize the operation's provider disclosure, derivation, combination,
and retention, the shared semantic-disclosure preflight rejects the edge
before provider connection. Compare/Meld projection, Search candidate
collection, Update input collection, recursive Summarize, and recursive Sever
use this boundary. Ordinary recursive read, List, and Show remain valid under
`READ + EMBED`; the fail-closed rule applies specifically when content would
cross into semantic/provider work through a misleadingly local wrapper.
Even a currently observed `DERIVE`/`COMBINE` tuple does not waive this guard:
without the exact contributor binding in the request and retained result, the
operation cannot prove which Grant authorized that use or revalidate it later.
An explicitly selected granted root remains available to an operation adapter
that does freeze and authorize its `ContextAccess`.
Provider-facing Search, ordinary Query, and Summarize also load local roots
without the catalog's process-local attached-READ projection. That browsing
projection has no durable Grant marker inside its child Context, so admitting
it would bypass the same contributor check; the granted public name must be
selected as an explicit catalog root instead.

Store-root selection is also separate from Grant-resolution authority. A
public client constructed with an explicit filesystem root keeps persisted
granted Memory and Context links opaque and never consults the host process's
active Profile registry. It can inspect the relationship metadata, but only an
active-Profile client may dereference the live authority content.

Granted Move remains outside this model. Moving authority-owned material would
delete from an authority Store and write another Store, requiring explicit
`DELETE` and a durable cross-Profile transaction journal. The supported path is
an authorized retained Copy followed by an ordinary local Move. Likewise, a
grantee cannot re-Grant a live view it does not own; it must first create an
authorized local value and then Grant that newly owned resource.

## Ownership and atomicity

Version 1 stores an exact Compare snapshot, analysis, and both frozen grant
bindings in the participant Profile. `GRANT_BOUND` artifacts remain on disk
but fail closed when a binding is revoked or changed. `RETAINED` artifacts may
be reopened after revocation because every source explicitly authorized
permanent retention at creation time. Neither mode automatically publishes the
artifact back into a contributing authority store.
The ordered comparison slot uses an analysis-UID compare-and-swap, so a slower
provider result cannot overwrite a newer saved analysis of the same pair.

Symmetric Meld can import either artifact into a local empty target. A
grant-bound Meld revalidates the sources whenever it resumes. A retained Meld
uses the retained exact snapshots and can resume after source revocation;
applying its proposal still writes only the participant target.

A granted-to-granted Update is safe without a multi-store write transaction
when all sources are read-only and exactly one authority target is mutated.
Mem freezes and revalidates both grant bindings, locks all source and target
Contexts, writes only the target, and rolls that target back on failure. Any
future operation that mutates two or more authority stores must remain blocked
until it has a durable cross-store transaction journal and recovery protocol.

## Study profile defaults

New `init-study` runs upgrade copied baseline templates rather than mutating
the baseline. Task 1 campus-wiki permits derivation, combination, export,
acceptance, grant-bound analysis, and retained analysis in addition to its
existing content effects.
Task 2 advisor grants and Task 3 official healthcare guidance permit source-side
derivation, combination, export, grant-bound analysis, and retained analysis.
Task 3 guardrails are participant-owned local data, not a grant. Query-only
sources remain `QUERY`; they do not silently become READ or derivative grants.

## `mem ls` disclosure

The ordinary list surface exposes the boundary at the point where a person is
reading the material. Listing a granted Context shows its authority Profile,
short grant identity and revision, complete permission set, and separate
source (`DERIVE`, `COMBINE`, `EXPORT`) and target/artifact
(`ACCEPT_DERIVED`, `SAVE_BOUND_ANALYSIS`, `SAVE_ANALYSIS`) decisions. Listing a local attachment
shows the same details for every attached authority view, including blocked
capabilities on query-only or read-only grants.

These lines are display metadata, not Memory content. `mem ls --copy` keeps its
canonical content-only clipboard representation; the separate `mem copy`
operation freezes and revalidates its Grant provenance at publication, then
produces an independently retained local value.

## Rejected alternatives and limits

- Treating READ as permission for every derivative use collapses visibility,
  reuse, redistribution, and retention into one irreversible choice.
- Assigning mixed output automatically to either the first source or the
  target hides multi-party consent and creates accidental co-ownership.
- Preventing every cross-grant operation is safe but unnecessarily blocks the
  case where all sources consent and only one explicitly accepting target is
  written.
- Mem cannot prevent manual transcription or photography of visible content.
  The enforceable boundary is that Mem does not itself create, retain, or
  transfer an artifact outside the declared grant capabilities.
