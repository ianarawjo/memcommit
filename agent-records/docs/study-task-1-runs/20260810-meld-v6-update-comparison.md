# Task 1 preservation-first Meld and Update comparison

## Purpose

This run checked whether Task 1 construction updates remain independently
revisable when the same 75-Memory incoming subtree is combined with the
300-Memory campus-wiki subtree. It compared symmetric Meld schema v3,
directional Meld schema v6, and Update schema v6. Counts alone were not treated
as semantic proof; the audit also checked exact content preservation, unique
source coverage, source cardinality per result, owner routing, and command-unit
Undo/Redo.

The original `task-1` Profile was not modified. It was copied into the local
managed Profile `task1-meld-update-v6-20260810`, whose initial six campus-wiki
children each contained 50 Memories.

## Recovery boundary found in the earlier split Study

The earlier applied schema-v5 directional Meld remained in
`study-20260810T010815Z-meld-a-b`. `mem undo` in its Participant Profile returned
`There is no recorded Context command to undo` because the six target owners
belong to the separate Grant authority Profile. Running `mem revert CHECKPOINT
--keep` on each authority child restored the state recorded by each Meld
checkpoint, which was the already-applied 51-Memory state rather than a
pre-Meld image. Each child therefore remained at 51 Memories. The `--keep`
attempts retained recovery checkpoints and did not discard prior history.

This is a separate cross-Profile recovery limitation. The controlled comparison
therefore used the local clone, where command-unit Undo/Redo can cover every
target owner.

## Symmetric Meld v3

Commands:

```text
mem compare --from participant/construction-updates --to campus-wiki \
  --reference-descendants --compared-descendants --snapshot
mem meld participant/construction-updates campus-wiki \
  --left-descendants --right-descendants \
  --to experiments/task1/symmetric-v3
mem switch experiments/task1/symmetric-v3
mem meld participant/construction-updates campus-wiki \
  --left-descendants --right-descendants --preserve-all
mem meld participant/construction-updates campus-wiki \
  --left-descendants --right-descendants --accept
```

Compare produced 51 primary relations: 2 `EQUIVALENT`, 6 `COMPATIBLE`, 23
`SCOPED`, 20 `DISTINCT`, and no conflicts or unclear relations. Provider-free
preservation then produced:

- 375/375 unique Source Memories represented;
- 368 result Memories: 366 exact `PRESERVE` and 2 `COALESCE`;
- zero `SYNTHESIZE` and zero cross-relation results;
- only two multi-source results, the two equivalent groups, with 3 and 6 Source
  members;
- maximum result length 317 characters, including the projected owner prefix;
- 74 result groups representing all 75 incoming Memories because one equivalent
  coalescence covered two incoming representations.

The first acceptance attempt exposed a false-stale bug: storage compared a
projected descendant-subtree digest to the physical root `context.json` digest.
The application path was corrected to freeze and lock every physical source
owner, recheck the aggregate projection, and retain those locks through target
CAS. The exact run then applied successfully.

Command-unit recovery was exact:

```text
applied  368
undo       0
redo     368
```

## Directional Meld v6

Command:

```text
mem meld participant/construction-updates --left-descendants \
  --into campus-wiki --right-descendants
```

The single provider turn returned the same six broad `SCOPED` analysis
relations seen in the earlier v5 run, but v6 kept relation grouping independent
from materialization. The result contained:

- 75 `PRESERVE ADD` operations and zero `SYNTHESIZE` operations;
- exact source content in 75/75 results;
- 75/75 unique incoming Memories represented exactly once;
- one incoming Source per result, maximum;
- maximum result length 266 characters;
- owner routing of 11 building-access, 10 event-relocations, 15
  temporary-parking, 13 shop-updates, 17 facility-updates, and 9 route-changes.

The target changed from 300 to 375 Memories. Command-unit recovery across all
six owners was exact:

```text
applied  375
undo     300
redo     375
undo     300
```

## Update v6

The same source and target scopes were opened in a real 120x40 TTY:

```text
mem update --from participant/construction-updates --to campus-wiki \
  --source-descendants --target-descendants
```

The provider plan took approximately 108 seconds and staged 63 target
operations. The effective terminal path was Viewer, `Tab`, Items, `Tab`, To Do,
`Enter` to open review, lowercase `a` to reopen the final review after returning,
`Down` to focus Apply, and `Enter` to apply. Intermediate Enter and uppercase
`A` attempts returned or had no effect while the review summary, rather than
Apply, owned focus.

The applied plan contained:

- 52 EDIT and 11 ADD operations, with no removals;
- all 75 unique incoming Memories cited, across 84 total source-reference
  occurrences;
- 14 multi-source operations and a maximum of 6 Sources in one result;
- maximum result length 421 characters;
- zero output contents exactly equal to a Source Memory and zero complete Source
  contents retained verbatim as an output substring;
- owner operations of 9 building-access, 9 event-relocations, 13
  temporary-parking, 10 shop-updates, 13 facility-updates, and 9 route-changes.

The final target count was 311 because edits retain target identities and only
the 11 additions increase cardinality. The largest aggregation was a 326-character
facility ADD citing six restroom-related Source Memories. Some edits naturally
form one scoped default-plus-exception rule, but the multi-fact additions show
that provenance coverage alone still does not prove independently revisable
result atomicity.

Command-unit recovery was exact:

```text
applied  311
undo     300
redo     311
undo     300
```

After the final Undo, the campus-wiki root and all six child Context UIDs and
digests exactly matched the untouched original `task-1` Profile.

## Comparison

| Operation | Input basis | Result or change count | Unique incoming coverage | Multi-source results | Exact incoming content |
| --- | ---: | ---: | ---: | ---: | ---: |
| Symmetric Meld v3 | 75 + 300 peers | 368 target Memories | 75/75 | 2 equivalent coalescences | preservation copy, except equivalent deduplication |
| Directional Meld v6 | 75 into 300 baseline | 75 ADD changes; final 375 | 75/75 | 0 | 75/75 |
| Update v6 | 75 into 300 target | 63 operations; final 311 | 75/75 | 14 | 0/75 verbatim |

The comparable quantity is not the raw final count: symmetric Meld must also
materialize the 300 baseline Memories in its new target. Its incoming-derived
delta and directional v6 are nevertheless aligned: every independent incoming
fact remains represented, while only semantic equivalence removes duplicate
representations. Update intentionally rewrites existing target Memories, but
its broad multi-source operations require a separate atomicity decision rather
than being assumed equivalent to preservation-first Meld.
