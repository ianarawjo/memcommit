# Elaborate best-effort reconstruction · 2026-08-25

## Outcome

This record reconstructs the `mem elaborate` attempts in the active Study
`study-20260825T110027Z-59cb6a29` and the immediately preceding Study
`study-20260824T170446Z-585b70f0` against the new execution policy:

- default Elaborate stops after one structurally valid, exact-count generation
  turn and publishes the proposed collection as `BEST_EFFORT`, `SUGGESTED`, and
  `UNVERIFIED`;
- `--strict` preserves the former post-generation collection Conformance and
  Fit gates;
- the default does not run those gates and suppress their result;
- decoding, exact cardinality, proposal uniqueness, frozen Source/Target
  identity, Target-prefix restatement rejection, authority checks, and atomic
  Add remain mandatory in both modes.

The reconstruction uses the immutable command-attempt and Study-action ledgers
plus successful Add checkpoints. A provider turn marked complete immediately
before `check_context_conformance` proves that generation, schema decoding, and
the operation's pre-validation checks completed. It does not prove that the
generated claims are true or conforming.

## Blocking failures

| Study | Attempt | Command | Former path | Best-effort reconstruction | Observed time saved |
| --- | --- | --- | --- | --- | ---: |
| current | `c39a3cc7` | `mem elaborate --to practice -n 10` | Generated 10; Rule 3 was later `PARTIALLY_CONFORMS`; all 10 were discarded | Stop after the completed generation turn and make the 10 structurally accepted candidates eligible for atomic Add; no Conformance/Fit result | 7.628 s |
| previous | `bcba5025` | `mem elaborate --from practice/fibonacci -n 40` | Generated 40; later collection Conformance rejected the set; all 40 were discarded | Stop after the completed generation turn and make the 40 structurally accepted candidates eligible for atomic Add | 14.904 s |
| previous | `857a8687` | `mem elaborate --from practice/fibonacci -n 10` | Generated 10; later collection Conformance rejected the set; all 10 were discarded | Stop after the completed generation turn and make the 10 structurally accepted candidates eligible for atomic Add | 7.645 s |

Across those three blocking attempts, the new default would preserve 60
generated candidates at the publication boundary and skip three rejecting
judgment turns. The exact 60 candidate strings cannot be recovered: failed
attempts intentionally have no Add checkpoint, while their ledgers retain only
provider operation names, elapsed time, and input/output character counts. A
new provider run would produce a new sample, not reconstruct the historical
sample, so this record does not fabricate one.

The current Study attempt `c6f44b45` is unaffected. Its combined `--from`,
`--to`, and `--goal` operands failed before provider connection, so changing
post-generation quality policy cannot make that invalid request executable.

## Completed-result counterfactuals

For completed attempts, the Add checkpoint retains the actual generated
collection. Holding that first provider response constant, best-effort would
apply the same Memories but omit strict validation objects and finish at the
generation boundary:

| Study | Attempt | Count | Former total | Generation boundary | Avoided time | Avoided turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| current | `84d81066` | 10 | 43.427 s | 25.326 s | 18.100 s | 2 |
| current | `443b2e15` | 10 | 40.681 s | 27.713 s | 12.968 s | 2 |
| previous | `f6695595` | 3 | 38.936 s | 13.338 s | 25.597 s | 2 |
| previous | `5b6e46f1` | 23 | 73.914 s | 42.711 s | 31.203 s | 2 |
| previous | `6a32ffd5` | 100 | 259.160 s | 154.358 s | 104.802 s | 2 |

The active Study's replayed suffix was:

`n is needle`, `o is oven`, `p is papaya`, `q is quilt`, `r is river`,
`s is strawberry`, `t is tunnel`, `u is umbrella`, `v is voavanga`, and
`w is window`.

Under the new default, the content is unchanged for that recorded generation
turn, but the receipt shape changes from version 3 with implicit mandatory
validation to version 4 with `quality_policy: BEST_EFFORT`,
`case_validation: NOT_RUN`, and `validation: null` on every proposal. Running
the command with `--strict` instead retains the former three-turn acceptance
path and populated validation records.

## Aggregate timing interpretation

Across the eight substantive Elaborate attempts in these two Studies, replay at
the recorded generation boundary removes 13 provider judgment turns and about
222.847 seconds of observed post-generation elapsed time. This is a historical
counterfactual, not a latency guarantee: provider time varies, and local atomic
publication still adds a small amount of work after generation.

Machine-readable attempt metadata and the exact retained contents of all five
completed results are in `report.json` beside this file.
