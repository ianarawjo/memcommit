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

`SESSION_LOG` remains narrower: it permits saving provider-mediated query
turns for a QUERY grant. It does not imply general derivative or analysis
retention.

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
Task 2 advisor grants and Task 3 guardrails permit source-side derivation,
combination, export, grant-bound analysis, and retained analysis. Query-only sources remain
`QUERY + SESSION_LOG`; they do not silently become READ or derivative grants.

## `mem ls` disclosure

The ordinary list surface exposes the boundary at the point where a person is
reading the material. Listing a granted Context shows its authority Profile,
short grant identity and revision, complete permission set, and separate
source (`DERIVE`, `COMBINE`, `EXPORT`) and target/artifact
(`ACCEPT_DERIVED`, `SAVE_BOUND_ANALYSIS`, `SAVE_ANALYSIS`) decisions. Listing a local attachment
shows the same details for every attached authority view, including blocked
capabilities on query-only or read-only grants.

These lines are display metadata, not Memory content. `mem ls --copy` keeps its
canonical content-only clipboard representation, while a granted copy remains
bound to the existing redacted receipt and live grant revalidation path.

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
