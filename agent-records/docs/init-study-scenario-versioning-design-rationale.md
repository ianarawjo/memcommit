# Init-study scenario versioning design rationale

## Motivation

The original three-task Study deliberately used different, large data domains.
Pilot participants reported fatigue from repeatedly learning a new corpus, and
that load obscured the memory-management behavior the Study intended to elicit.
The revised design keeps one continuous Coffee workspace while still
escalating the operation: participants form a customer perspective, extend it
with operational perspectives, and then curate advice for a friend's concrete
café conditions.

The original corpus is also an important regression world. Long-running debug
and world sessions have used its exact Context, Grant, query, endpoint, and
prewarm topology to expose bugs. Replacing that data in place would make later
fixes impossible to compare with the earlier runs. Study iteration and bug
reproduction therefore need separate, explicitly versioned inputs.

## Command contract

`mem init-study` and `mem init-study NAME` initialize the built-in
`coffee-v1` scenario. The ordinary participant path has no setup choice and
does not require an imported `study-baseline` Profile.

The preserved debugging route is explicit:

```text
mem init-study --scenario legacy-v1
mem init-study NAME --scenario legacy-v1
```

`--from-profile BASELINE` remains the editable legacy escape hatch. Supplying
it without `--scenario` implies `legacy-v1`, preserving existing custom-baseline
scripts. Combining it with `coffee-v1` fails before publishing a Profile.
Unknown scenario names also fail closed; a mutable alias such as `latest` would
make a recorded command non-reproducible.

Existing initialized Study runs are unaffected. Both routes copy their source
into isolated participant and authority stores at initialization; no run reads
future scenario changes dynamically.

## Coffee topology

The participant owns the fixed rehearsal packs and writable Task roots at setup:

```text
practice                         empty direct inventory; initial Context
└── coffee
    ├── chunk-atomize-summarize             1 deliberately repetitive transcript
    ├── compare-merge-meld-update
    │   ├── a                               4 preference Memories
    │   └── b                               4 contrasting preference Memories
    └── search-find-sever-forget            5 review Memories
task-1                          empty participant-authored perspective target
task-2                          empty Meld result target
task-3                          empty Sever/share-draft target
```

The run-private authority Profile owns the fixed external inputs:

```text
task-1/customer-perspectives
├── woohooovertime              8 Memories
├── saycheesecake               8 Memories
└── strollersnackpack           8 Memories
task-2/operational-perspectives
├── coffeewithtaylor            8 Memories
├── morrowcoffee-official       8 Memories
└── consulting-newwavecafeculture  8 Memories
task-3/friend-cafe
└── conditions                  8 Memories
```

Task 1 and Task 2 expose recursive READ/EMBED/DERIVE/COMBINE/EXPORT and
analysis-save views below their local Task roots. Task 3 exposes `conditions`
as an exact readable source and `task-3/friend-cafe` separately as an exact,
non-recursive SHARE endpoint. The endpoint does not make receiver contents
readable. This split lets participants inspect the friend's conditions and
later deliver a curated result without conflating reading with transfer
authority.

The initialized participant therefore has ten local Contexts containing
fourteen fixed practice Memories, plus nine effective READ-granted Contexts
containing 56 Memories. The authority store has thirteen Contexts after
structural parents are included. Task instructions remain facilitator speech
rather than durable Memories, so the experiment does not accidentally merge
instructions into semantic Source frames.

## Data and language invariants

English is canonical durable `Memory.content`. Every authored Korean row is an
IMPORTED same-UID translation-catalog entry. Switching display language does
not duplicate a Memory or alter the scenario fingerprint. Designer labels
such as KB, PP, SM, UM, WM, and OM remain source annotations in the scenario
specification rather than prefixes in participant-visible content.

Context and Memory UIDs are deterministic within `coffee-v1`. The scenario
digest covers the complete bilingual content, Context placement, purpose
annotations, and Grant declarations. Each created Study pair records the
stable virtual-baseline UID, scenario name, and digest in the existing Study
provenance fields. The virtual baseline is deliberately not published as a
mutable Profile: a researcher cannot unknowingly edit `coffee-v1` between two
runs. Any material data change must be introduced under a new scenario name,
such as `coffee-v2`, rather than silently changing the meaning of `coffee-v1`.

## Workflow intent

The data supports the planned escalation without encoding the facilitator's
script as Memory:

1. Use the three packs below `practice/coffee` to contrast Chunk, Atomize, and
   Summarize; Compare, Merge, Meld, and Update; and Find, Search, Sever, and
   Forget. The pack contents are durable inputs, while the order and exact
   instructions remain facilitator speech.
2. Collect and Atomize the participant's own café experiences into direct
   Memories on `task-1`.
3. Use the 24 customer-agent Memories to Update that perspective.
4. Meld the resulting customer perspective with the 24 operational Memories
   into direct Memories on `task-2`.
5. Use the eight friend-café conditions to Sever or otherwise curate a
   context-specific result on `task-3`, then Share it to
   `task-3/friend-cafe`.

The three empty Task roots are intentional. They preserve exact-versus-
descendant targeting, provide stable result locations, and let participant
authorship grow the store progressively instead of preloading a supposed
personal viewpoint.

## Prewarm and debugging boundary

`legacy-v1` retains the editable baseline, exact prewarm declarations,
compatibility checks, regeneration, and shared-bundle attachment used by
existing debug sessions. It remains the route for reproducing the old Task 1,
Task 2, Task 3, and world-session failures.

`coffee-v1` attaches no shared semantic prewarm and does not emit prewarm
compatibility progress. Its measured Update, Meld, and Sever frames depend on
participant-authored Memories, so a fixed exact semantic artifact would not be
portable across participants. This does not disable ordinary operation
sessions, checkpoints, Undo/Redo, or run-local caches; it excludes only the
cross-run exact Study prewarm bundle.

The legacy fixture sources, generated bundles, tests, and baseline import
commands remain in the repository. They are not hidden fallback data for the
new default and are not rewritten by Coffee scenario changes.

## Limitations

Scenario selection currently covers `coffee-v1` and `legacy-v1`; it is not a
general plugin registry. The Coffee scenario stores purpose annotations in
Python source rather than the generated legacy manifest format because it has
no editable baseline or build step. If future studies require researcher-
editable Coffee data, that work should add a validated scenario build and
atomic version publication instead of making the versioned built-in data
mutable.
